"""STT yedekleme zinciri (Faz 2.5).

Sağlayıcılar sırayla denenir. Bir sağlayıcı **yeniden denenebilir** bir hatayla
düşerse (kota, zaman aşımı, 5xx) bir sonrakine geçilir; anahtar hatası gibi
kalıcı sorunlarda o sağlayıcı zaten kullanılabilir sayılmaz.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.audio.chunking import Chunk, join_transcripts, split_for_upload
from omnivoice_engine.providers import ProviderError, Transcript, Usage
from omnivoice_engine.stt.base import SttProvider
from omnivoice_engine.stt.groq import GroqStt
from omnivoice_engine.stt.language import (
    DEFAULT_LANGUAGES,
    DISPLAY_NAMES,
    better,
    is_allowed,
    normalize,
)
from omnivoice_engine.stt.openrouter import OpenRouterStt

log = logging.getLogger(__name__)


class SttRouter:
    """Sırayla denenen STT sağlayıcıları."""

    def __init__(
        self,
        providers: list[SttProvider] | None = None,
        *,
        languages: tuple[str, ...] = DEFAULT_LANGUAGES,
    ) -> None:
        # Sıra bilinçli: Groq hem en hızlı hem ücretsiz katmanda; OpenRouter
        # kota dolduğunda devreye giren ücretli yedek.
        self.providers: list[SttProvider] = providers or [GroqStt(), OpenRouterStt()]
        #: Kullanıcının konuştuğu diller. Tespit bunun dışına düşerse
        #: düzeltiliyor (bkz. `stt/language.py`).
        self.languages: tuple[str, ...] = normalize(list(languages))

    def set_languages(self, languages: object) -> tuple[str, ...]:
        self.languages = normalize(languages)
        return self.languages

    def available_providers(self) -> list[str]:
        return [p.info.name for p in self.providers if p.is_available()]

    async def transcribe(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> Transcript:
        """Sesi metne çevirir; gerekiyorsa parçalara bölerek.

        `on_progress(tamamlanan, toplam)` uzun kayıtlarda arayüze ilerleme
        bildirir — bir saatlik toplantıda kullanıcı donmuş bir ekrana bakmasın.
        """
        if clip.duration_seconds < 0.2:
            raise ProviderError("stt", "kayıt çok kısa")

        chunks = split_for_upload(clip)
        if len(chunks) == 1:
            transcript = await self._transcribe_one(
                clip, language=language, vocabulary=vocabulary
            )
        else:
            transcript = await self._transcribe_chunks(
                chunks, language=language, vocabulary=vocabulary, on_progress=on_progress
            )

        # Dil çağıran tarafından verildiyse tespit yok, düzeltilecek bir şey
        # de yok.
        if language is not None:
            return transcript
        return await self._fix_language(clip, transcript, vocabulary=vocabulary)

    async def _fix_language(
        self,
        clip: AudioClip,
        transcript: Transcript,
        *,
        vocabulary: list[str] | None,
    ) -> Transcript:
        """Tespit edilen dil kullanıcının konuştuğu diller arasında değilse düzeltir.

        Ölçülen hata: kullanıcı Türkçe konuşurken Whisper dili **İzlandaca**
        sanıp metni öyle çözümledi. Çıktı okunamaz hâle geldi.

        Dili sabitlemek çözüm değil — kullanıcı hem Türkçe hem İngilizce
        dikte ediyor. Bunun yerine izin verilen her dil denenip en yüksek
        güven skoru seçiliyor. Ek çağrı **yalnız bu hata durumunda** yapılıyor;
        normal akışta hiçbir maliyet yok.
        """
        if is_allowed(transcript.language, self.languages):
            return transcript

        log.warning(
            "Tespit edilen dil (%s) konuşulan diller arasında değil; yeniden deneniyor: %s",
            transcript.language,
            ", ".join(DISPLAY_NAMES.get(k, k) for k in self.languages),
        )

        en_iyi = None
        for kod in self.languages:
            try:
                aday = await self._transcribe_one(
                    clip, language=kod, vocabulary=vocabulary
                )
            except ProviderError as exc:
                log.warning("Dil düzeltmesi %s ile başarısız: %s", kod, exc)
                continue
            if en_iyi is None or better(aday.confidence, en_iyi.confidence):
                en_iyi = aday

        if en_iyi is None:
            # Hiçbir deneme tutmadıysa elimizdekini veriyoruz: kötü bir metin,
            # hiç metin olmamasından iyidir.
            log.warning("Dil düzeltmesi sonuç vermedi, ilk çözümleme kullanılıyor")
            return transcript

        log.info(
            "Dil düzeltildi: %s → %s (güven %s)",
            transcript.language,
            en_iyi.language,
            f"{en_iyi.confidence:+.3f}" if en_iyi.confidence is not None else "bilinmiyor",
        )
        return en_iyi

    async def _transcribe_chunks(
        self,
        chunks: list[Chunk],
        *,
        language: str | None,
        vocabulary: list[str] | None,
        on_progress: Callable[[int, int], Awaitable[None]] | None,
    ) -> Transcript:
        """Parçaları sırayla çevirir ve tek bir transkripte birleştirir.

        Sırayla, paralel değil: sağlayıcıların hız sınırı var ve paralel
        istekler kotayı hızla tüketip 429 üretiyor.
        """
        texts: list[str] = []
        total_latency = 0
        total_cost = 0.0
        provider = ""
        model = ""
        detected_language = language

        for chunk in chunks:
            transcript = await self._transcribe_one(
                chunk.clip, language=detected_language, vocabulary=vocabulary
            )
            texts.append(transcript.text)
            total_latency += transcript.usage.latency_ms
            total_cost += transcript.usage.cost_usd or 0.0
            provider = transcript.provider
            model = transcript.model
            # İlk parçada dil belirlendikten sonra kalanlara onu bildiriyoruz;
            # aynı kaydın ortasında dil değiştirmesi hata olur.
            detected_language = detected_language or transcript.language

            if on_progress:
                await on_progress(chunk.index + 1, chunk.total)

        return Transcript(
            text=join_transcripts(texts),
            language=detected_language,
            model=model,
            provider=provider,
            usage=Usage(
                latency_ms=total_latency,
                cost_usd=total_cost or None,
                audio_seconds=sum(c.clip.duration_seconds for c in chunks),
            ),
        )

    async def _transcribe_one(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
    ) -> Transcript:
        errors: list[str] = []
        #: Zincirde geçici bir hata gördük mü?
        #:
        #: Bu bayrak birleşik hataya taşınmak zorunda. Taşınmazsa "internet
        #: kesik" ile "anahtar yanlış" aynı görünüyor ve kuyruk (Faz 7.2)
        #: yanlış karar veriyor: ya kurtarılabilir bir kaydı çöpe atıyor ya da
        #: asla başarılı olmayacak bir kaydı sonsuza kadar saklıyor.
        any_retryable = False

        for provider in self.providers:
            name = provider.info.name
            if not provider.is_available():
                errors.append(f"{name}: anahtar yok")
                continue

            try:
                transcript = await provider.transcribe(
                    clip, language=language, vocabulary=vocabulary
                )
            except ProviderError as exc:
                errors.append(str(exc))
                if exc.retryable:
                    any_retryable = True
                    log.warning("%s başarısız, yedeğe geçiliyor: %s", name, exc)
                    continue
                # Kalıcı hata: bu sağlayıcıyla tekrar denemenin anlamı yok,
                # ama zincirdeki diğerleri hâlâ işe yarayabilir.
                log.error("%s kalıcı hata verdi: %s", name, exc)
                continue

            if not transcript.text:
                errors.append(f"{name}: boş metin döndü")
                continue

            return transcript

        raise ProviderError(
            "stt",
            "hiçbir sağlayıcı yanıt vermedi — " + " | ".join(errors),
            retryable=any_retryable,
        )
