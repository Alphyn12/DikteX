"""Dikte boru hattı — kısayoldan yapıştırmaya kadar tüm akış.

Durum makinesi:

    idle ──start──▶ listening ──stop──▶ processing ──▶ preflight
      ▲                  │                   │             │
      └──────cancel──────┴───────────────────┴──── paste ──┘

Her aşama arayüze bir olay yayar; HUD bu olaylara göre üç durumundan birini
gösterir (mockup 1c).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from omnivoice_engine.audio.capture import MicrophoneCapture
from omnivoice_engine.context.apps import AppProfile, profile_for
from omnivoice_engine.context.selection import read_selection, truncate_selection
from omnivoice_engine.context.variables import VariableContext, inject, mentions_selection
from omnivoice_engine.integrations.git import read_context_for_window
from omnivoice_engine.integrations.screen import Region, ScreenCaptureError, capture_region
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.output.formats import PasteFormat, apply_format, detect_format
from omnivoice_engine.output.paste import PasteError, paste_text, read_clipboard_text
from omnivoice_engine.output.window import WindowInfo, get_foreground_window
from omnivoice_engine.pipeline.fillers import strip_fillers
from omnivoice_engine.pipeline.modes import Mode, ModeId, get_mode
from omnivoice_engine.pipeline.prompts import build_prompt, sanitize_output
from omnivoice_engine.pipeline.vision_prompts import screen_question_prompt
from omnivoice_engine.providers import ProviderError
from omnivoice_engine.storage.db import Database, DictationRecord
from omnivoice_engine.storage.snippets import SnippetLibrary
from omnivoice_engine.storage.vocabulary import Vocabulary
from omnivoice_engine.stt.router import SttRouter

log = logging.getLogger(__name__)

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

#: Ses seviyesi arayüze bu sıklıkta gönderilir. 20 Hz dalga formu için akıcı,
#: WebSocket için hafif.
_LEVEL_INTERVAL = 0.05


class DictationState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    PREFLIGHT = "preflight"
    SILENT = "silent"
    """Kayıtta konuşma yoktu. Hata değil ama sessizce geçilmemeli."""
    ERROR = "error"


@dataclass
class DictationResult:
    """Pre-flight'ta kullanıcıya gösterilen sonuç."""

    raw_text: str
    final_text: str
    fillers_removed: int
    language: str | None
    stt_provider: str
    stt_model: str
    stt_ms: int
    llm_provider: str | None
    llm_model: str | None
    llm_ms: int
    total_ms: int
    cost_usd: float
    audio_seconds: float
    target: WindowInfo | None = None
    record_id: int | None = None
    mode: str = "quick"
    profile: str = "plain"
    app_display_name: str | None = None
    #: Seçili metnin uzunluğu — arayüzde rozet olarak gösterilir.
    selection_chars: int = 0
    #: Doldurulan dinamik değişkenler.
    variables: tuple[str, ...] = ()
    #: Kullanıcının sesle istediği yapıştırma biçimi (Properties V.7).
    paste_format: PasteFormat | None = None
    #: Tetiklenen snippet'in adı — arayüzde rozet olarak gösterilir.
    #:
    #: Göstermek şart: eşleşme bulanık olduğu için yanlış şablon tetiklenebilir
    #: ve kullanıcı bunu ancak çıktıya bakınca anlar. Adı pre-flight'ta
    #: görürse hatayı yapıştırmadan önce yakalar.
    snippet: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "rawText": self.raw_text,
            "finalText": self.final_text,
            "fillersRemoved": self.fillers_removed,
            "language": self.language,
            "sttProvider": self.stt_provider,
            "sttModel": self.stt_model,
            "sttMs": self.stt_ms,
            "llmProvider": self.llm_provider,
            "llmModel": self.llm_model,
            "llmMs": self.llm_ms,
            "totalMs": self.total_ms,
            "costUsd": self.cost_usd,
            "audioSeconds": round(self.audio_seconds, 2),
            "appName": self.app_display_name
            or (self.target.app_name if self.target else None),
            "windowTitle": self.target.title if self.target else None,
            "recordId": self.record_id,
            "mode": self.mode,
            "profile": self.profile,
            "selectionChars": self.selection_chars,
            "variables": list(self.variables),
            "pasteFormat": self.paste_format.value if self.paste_format else None,
            "snippet": self.snippet,
        }


@dataclass
class _Session:
    """Tek bir dikte oturumunun geçici durumu."""

    started_at: float
    target: WindowInfo | None
    pre_roll_seconds: float
    mode: Mode
    profile: AppProfile
    level_task: asyncio.Task[None] | None = field(default=None, repr=False)
    #: Ekran modunda kaydedilen bölge görüntüsü (data URL).
    #:
    #: Görüntü kayıt BAŞLARKEN alınır, bitince değil: kullanıcı konuşurken
    #: ekran değişmiş olabilir ve o zaman sorduğu şeyin resmi elde kalmaz.
    screen_image: str | None = None
    screen_size: tuple[int, int] | None = None


class DictationPipeline:
    """Dikte akışını yöneten orkestratör."""

    def __init__(
        self,
        *,
        mic: MicrophoneCapture,
        stt: SttRouter,
        llm: OpenRouterLlm,
        db: Database,
        emit: EventSink,
        vocabulary: Vocabulary | None = None,
        snippets: SnippetLibrary | None = None,
    ) -> None:
        self._mic = mic
        self._stt = stt
        self._llm = llm
        self._db = db
        self._emit = emit
        self._vocabulary = vocabulary
        self._snippets = snippets

        self.state = DictationState.IDLE
        self._session: _Session | None = None
        self._result: DictationResult | None = None
        #: Aynı anda tek dikte; kısayola iki kez basılırsa yarış olmasın.
        self._lock = asyncio.Lock()

    # ── Durum yayını ──────────────────────────────────────────────────────

    async def _set_state(self, state: DictationState, **extra: Any) -> None:
        self.state = state
        await self._emit({"type": "dictation:state", "state": state.value, **extra})

    # ── Akış ──────────────────────────────────────────────────────────────

    async def start(
        self,
        mode: ModeId | str = ModeId.QUICK,
        *,
        region: dict[str, int] | None = None,
    ) -> None:
        """Kaydı başlatır. Zaten kayıttaysa yok sayar.

        `region` yalnız ekran modunda gelir; kaplamada seçilen dikdörtgen.
        """
        async with self._lock:
            if self.state in {
                DictationState.LISTENING,
                DictationState.PROCESSING,
                DictationState.PREFLIGHT,
            }:
                log.debug("start() yok sayıldı, durum: %s", self.state)
                return

            # Hedef pencereyi kayıt başlarken yakalıyoruz: kullanıcı konuşurken
            # başka bir pencereye geçerse metin yine doğru yere gitmeli.
            target = get_foreground_window()
            resolved_mode = get_mode(mode)
            profile = profile_for(target.process_name if target else "")

            # Ekran görüntüsü kayıttan ÖNCE alınır: kullanıcı konuşurken ekran
            # değişebilir ve sorduğu şeyin resmi elde kalmaz.
            screen_image: str | None = None
            screen_size: tuple[int, int] | None = None
            if resolved_mode.uses_screen_region and region:
                try:
                    capture = await asyncio.to_thread(
                        capture_region,
                        Region(
                            x=int(region["x"]),
                            y=int(region["y"]),
                            width=int(region["width"]),
                            height=int(region["height"]),
                        ),
                    )
                    screen_image = capture.to_data_url()
                    screen_size = (capture.width, capture.height)
                    log.info("Ekran bölgesi yakalandı: %dx%d", capture.width, capture.height)
                except ScreenCaptureError as exc:
                    await self._set_state(DictationState.ERROR, message=str(exc))
                    return

            if not self._mic.is_streaming:
                self._mic.start_stream()

            pre_roll = self._mic.start_recording()
            self._session = _Session(
                started_at=time.perf_counter(),
                target=target,
                pre_roll_seconds=pre_roll,
                mode=resolved_mode,
                profile=profile,
                screen_image=screen_image,
                screen_size=screen_size,
            )
            self._result = None

            await self._set_state(
                DictationState.LISTENING,
                preRollSeconds=round(pre_roll, 2),
                appName=profile.display_name or (target.app_name if target else None),
                windowTitle=target.title if target else None,
                mode=resolved_mode.id.value,
                profile=profile.profile.value,
            )
            self._session.level_task = asyncio.create_task(self._stream_level())
            log.info(
                "Dikte başladı (mod: %s, pre-roll %.2f sn, hedef: %s / %s)",
                resolved_mode.id.value,
                pre_roll,
                profile.display_name or "bilinmiyor",
                profile.profile.value,
            )

    async def _stream_level(self) -> None:
        """Ses seviyesini ve süreyi arayüze akıtır — dalga formu bunu kullanır."""
        try:
            while self.state is DictationState.LISTENING:
                await self._emit(
                    {
                        "type": "dictation:level",
                        "level": round(self._mic.level, 4),
                        "seconds": round(self._mic.recorded_seconds, 2),
                    }
                )
                await asyncio.sleep(_LEVEL_INTERVAL)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Kaydı bitirir ve işlemeye geçer."""
        async with self._lock:
            if self.state is not DictationState.LISTENING or self._session is None:
                return
            session = self._session
            if session.level_task:
                session.level_task.cancel()

            clip = self._mic.stop_recording()

            # Sessiz kaydı sağlayıcıya göndermiyoruz: Whisper boş sese metin
            # uydurur ("Thank you.", "Altyazı M.K."). Kullanıcı kısayola yanlışlıkla
            # basmış olabilir; ona uydurma bir cümle yapıştırmak yerine sessizce
            # boşa dönüyoruz.
            if clip.is_silent():
                log.info(
                    "Kayıt sessiz (tepe %.6f, rms %.6f) — sağlayıcıya gönderilmedi",
                    clip.peak,
                    clip.rms,
                )
                self._session = None
                # Sessizce boşa dönmek kullanıcıya uygulamanın çöktüğünü
                # düşündürüyordu. Mutlak sessizlik (tepe ≈ 0) mikrofonun ölü
                # olduğunu gösterir; sadece kısık olmasından ayırıyoruz ki
                # doğru çözümü söyleyebilelim.
                await self._set_state(
                    DictationState.SILENT,
                    peak=round(clip.peak, 6),
                    deadMicrophone=clip.peak < 0.0005,
                    seconds=round(clip.duration_seconds, 1),
                )
                return

            await self._set_state(DictationState.PROCESSING, step="stt")

        # Ağ işleri kilidin dışında; kullanıcı bu sırada iptal edebilmeli.
        try:
            result = await self._process(clip_seconds=clip.duration_seconds, clip=clip, session=session)
        except ProviderError as exc:
            log.error("Dikte işlenemedi: %s", exc)
            self._session = None
            await self._set_state(DictationState.ERROR, message=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - beklenmedik hata arayüze taşınmalı
            log.exception("Dikte boru hattında beklenmedik hata")
            self._session = None
            await self._set_state(DictationState.ERROR, message=str(exc))
            return

        self._result = result
        self._session = None
        await self._set_state(DictationState.PREFLIGHT, result=result.to_payload())

    async def _process(
        self, *, clip_seconds: float, clip: Any, session: _Session
    ) -> DictationResult:
        started = session.started_at
        mode = session.mode

        # 1) Konuşma → metin. Sözlük STT'ye bağlam ipucu olarak gider;
        #    ölçtük, tireli terimlerin yazımı böyle korunuyor.
        stt_terms = self._vocabulary.stt_terms() if self._vocabulary else None
        transcript = await self._stt.transcribe(clip, language=None, vocabulary=stt_terms)
        self._db.add_spend(
            provider=transcript.provider,
            model=transcript.model,
            kind="stt",
            cost_usd=transcript.usage.cost_usd,
            latency_ms=transcript.usage.latency_ms,
            meta={"audioSeconds": round(clip_seconds, 2)},
        )

        # 2) Yerel dolgu temizliği — anlık ve bedava
        local = strip_fillers(transcript.text)

        # 3) Bağlam: seçili metin ve dinamik değişkenler
        selection = ""
        wants_selection = mode.uses_selection or mentions_selection(local.text)
        if wants_selection and session.target:
            # Ctrl+C göndermek bloklayıcı Win32 çağrıları içeriyor.
            selection = await asyncio.to_thread(read_selection, session.target.handle)
            selection = truncate_selection(selection)
            if selection:
                log.info("Seçili metin okundu: %d karakter", len(selection))

        # Git bağlamı: kullanıcı ne değiştirdiğini anlatmak zorunda kalmasın
        # (Properties V.5). Depo bulunamazsa mod diff'siz çalışmaya devam eder.
        git_diff: str | None = None
        git_summary: str | None = None
        if mode.uses_git_diff and session.target:
            context = await asyncio.to_thread(
                read_context_for_window,
                session.target.title,
                session.target.process_name,
            )
            if context and not context.is_empty:
                git_diff = context.diff
                git_summary = context.summary_line()
                log.info("Git bağlamı okundu: %s", git_summary)
            else:
                await self._emit(
                    {"type": "dictation:warning", "message": "Bekleyen git değişikliği bulunamadı"}
                )

        # Snippet tetikleme (Properties V.3). HAM metinden değil, dolgu
        # temizlenmiş metinden aranıyor: "şey, kod inceleme yap" içindeki
        # "şey" eşleşme oranını gereksiz yere düşürürdü.
        snippet = self._snippets.find(local.text) if self._snippets else None
        if snippet is not None:
            log.info("Snippet tetiklendi: %s", snippet.name)

        variables = VariableContext(
            app_name=session.profile.display_name
            or (session.target.app_name if session.target else ""),
            window_title=session.target.title if session.target else "",
            selected_text=selection,
            clipboard=await asyncio.to_thread(read_clipboard_text) or "",
        )
        injected = inject(local.text, variables)

        await self._emit(
            {
                "type": "dictation:progress",
                "step": "llm",
                "rawText": transcript.text,
                "fillersRemoved": local.removed_count,
                "sttMs": transcript.usage.latency_ms,
                "selectionChars": len(selection),
                "variables": list(injected.used),
                "snippet": snippet.name if snippet else None,
            }
        )

        # 4) LLM ile moda ve ortama duyarlı işleme
        llm_provider: str | None = None
        llm_model: str | None = None
        llm_ms = 0
        llm_cost = 0.0
        final_text = injected.text

        if self._llm.is_available() and injected.text:
            try:
                if session.screen_image:
                    # Ekran modunun istemi ayrı: burada iş metni temizlemek
                    # değil, görüntüyü okuyup soruyu yanıtlamak.
                    prompt = screen_question_prompt(
                        injected.text,
                        session.screen_image,
                        language=transcript.language,
                    )
                else:
                    prompt = build_prompt(
                        injected.text,
                        mode=mode,
                        profile=session.profile.profile,
                        app_name=session.profile.display_name or None,
                        vocabulary=self._vocabulary.llm_terms() if self._vocabulary else None,
                        language=transcript.language,
                        selection=selection,
                        git_diff=git_diff,
                        git_summary=git_summary,
                        snippet=snippet.body if snippet else None,
                    )
                completion = await self._llm.complete(prompt, model=mode.model)
                final_text = sanitize_output(completion.text) or injected.text
                llm_provider = completion.provider
                llm_model = completion.model
                llm_ms = completion.usage.latency_ms
                llm_cost = completion.usage.cost_usd or 0.0
                self._db.add_spend(
                    provider=completion.provider,
                    model=completion.model,
                    kind="llm",
                    cost_usd=completion.usage.cost_usd,
                    latency_ms=completion.usage.latency_ms,
                    meta={
                        "inputTokens": completion.usage.input_tokens,
                        "outputTokens": completion.usage.output_tokens,
                    },
                )
            except ProviderError as exc:
                # LLM düşerse dikteyi kaybetmiyoruz: yerel olarak temizlenmiş
                # metin hâlâ kullanılabilir.
                log.warning("LLM katmanı atlandı: %s", exc)
                await self._emit(
                    {"type": "dictation:warning", "message": f"LLM atlandı: {exc}"}
                )

        total_ms = int((time.perf_counter() - started) * 1000)
        cost = (transcript.usage.cost_usd or 0.0) + llm_cost

        result = DictationResult(
            raw_text=transcript.text,
            final_text=final_text,
            fillers_removed=local.removed_count,
            language=transcript.language,
            stt_provider=transcript.provider,
            stt_model=transcript.model,
            stt_ms=transcript.usage.latency_ms,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_ms=llm_ms,
            total_ms=total_ms,
            cost_usd=cost,
            audio_seconds=clip_seconds,
            target=session.target,
            # Biçim isteği HAM metinden okunur: LLM temizlerken "json olarak"
            # ifadesini çıkarmış olabilir ama kullanıcı onu söylemişti.
            paste_format=detect_format(transcript.text),
            snippet=snippet.name if snippet else None,
            mode=mode.id.value,
            profile=session.profile.profile.value,
            app_display_name=session.profile.display_name or None,
            selection_chars=len(selection),
            variables=injected.used,
        )

        result.record_id = self._db.add_dictation(
            DictationRecord(
                raw_text=result.raw_text,
                final_text=result.final_text,
                mode=mode.id.value,
                app_name=session.profile.display_name
                or (session.target.app_name if session.target else None),
                window_title=session.target.title if session.target else None,
                language=result.language,
                stt_provider=result.stt_provider,
                stt_model=result.stt_model,
                llm_provider=result.llm_provider,
                llm_model=result.llm_model,
                audio_seconds=result.audio_seconds,
                fillers_removed=result.fillers_removed,
                stt_ms=result.stt_ms,
                llm_ms=result.llm_ms,
                total_ms=result.total_ms,
                cost_usd=result.cost_usd,
            )
        )

        if snippet is not None and self._snippets is not None:
            # Sayaç diske yazıyor; olay döngüsünü bekletmesin.
            await asyncio.to_thread(self._snippets.mark_used, snippet.name)

        return result

    async def paste(self, text: str | None = None) -> None:
        """Pre-flight'taki metni hedef pencereye yapıştırır."""
        result = self._result
        if self.state is not DictationState.PREFLIGHT or result is None:
            return

        # Kullanıcı önizlemede düzenlemiş olabilir.
        content = text if text is not None else result.final_text

        # Biçim dönüşümü yapıştırma anında uygulanır, üretim anında değil:
        # kullanıcı pre-flight'ta metni düzenlerse dönüşüm ona da uygulanmalı.
        if result.paste_format is not None:
            content = apply_format(content, result.paste_format)

        try:
            # Yapıştırma bloklayıcı Win32 çağrıları içeriyor; olay döngüsünü
            # kilitlememek için iş parçacığına alıyoruz.
            await asyncio.to_thread(
                paste_text,
                content,
                window_handle=result.target.handle if result.target else None,
            )
        except PasteError as exc:
            log.error("Yapıştırma başarısız: %s", exc)
            await self._set_state(DictationState.ERROR, message=str(exc))
            return

        if result.record_id:
            self._db.mark_pasted(result.record_id)

        self._result = None
        await self._set_state(DictationState.IDLE, pasted=True)
        log.info("Yapıştırıldı: %d karakter", len(content))

    async def cancel(self) -> None:
        """Akışı iptal eder — Esc."""
        async with self._lock:
            if self._session and self._session.level_task:
                self._session.level_task.cancel()
            self._mic.cancel_recording()
            self._session = None
            self._result = None
            await self._set_state(DictationState.IDLE, cancelled=True)

    async def toggle(
        self, mode: ModeId | str = ModeId.QUICK, *, region: dict[str, int] | None = None
    ) -> None:
        """Kısayolun davranışı: boştaysa başlat, dinliyorsa bitir."""
        # SILENT ve ERROR birer bilgilendirme durumu; kısayola tekrar basmak
        # yeni bir dikte başlatmalı, kullanıcıyı önce kapatmaya zorlamamalı.
        if self.state in {DictationState.IDLE, DictationState.SILENT, DictationState.ERROR}:
            await self.start(mode, region=region)
        elif self.state is DictationState.LISTENING:
            await self.stop()
        # İşleme veya pre-flight sırasında kısayol yok sayılır; kullanıcı
        # Enter veya Esc ile karar verir.
