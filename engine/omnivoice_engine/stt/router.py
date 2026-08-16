"""STT yedekleme zinciri (Faz 2.5).

Sağlayıcılar sırayla denenir. Bir sağlayıcı **yeniden denenebilir** bir hatayla
düşerse (kota, zaman aşımı, 5xx) bir sonrakine geçilir; anahtar hatası gibi
kalıcı sorunlarda o sağlayıcı zaten kullanılabilir sayılmaz.
"""

from __future__ import annotations

import logging

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.providers import ProviderError, Transcript
from omnivoice_engine.stt.base import SttProvider
from omnivoice_engine.stt.groq import GroqStt
from omnivoice_engine.stt.openrouter import OpenRouterStt

log = logging.getLogger(__name__)


class SttRouter:
    """Sırayla denenen STT sağlayıcıları."""

    def __init__(self, providers: list[SttProvider] | None = None) -> None:
        # Sıra bilinçli: Groq hem en hızlı hem ücretsiz katmanda; OpenRouter
        # kota dolduğunda devreye giren ücretli yedek.
        self.providers: list[SttProvider] = providers or [GroqStt(), OpenRouterStt()]

    def available_providers(self) -> list[str]:
        return [p.info.name for p in self.providers if p.is_available()]

    async def transcribe(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
    ) -> Transcript:
        if clip.duration_seconds < 0.2:
            raise ProviderError("stt", "kayıt çok kısa")

        errors: list[str] = []

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

        raise ProviderError("stt", "hiçbir sağlayıcı yanıt vermedi — " + " | ".join(errors))
