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
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.output.paste import PasteError, paste_text
from omnivoice_engine.output.window import WindowInfo, get_foreground_window
from omnivoice_engine.pipeline.fillers import strip_fillers
from omnivoice_engine.pipeline.prompts import dictation_prompt, sanitize_output
from omnivoice_engine.providers import ProviderError
from omnivoice_engine.storage.db import Database, DictationRecord
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
            "appName": self.target.app_name if self.target else None,
            "windowTitle": self.target.title if self.target else None,
            "recordId": self.record_id,
        }


@dataclass
class _Session:
    """Tek bir dikte oturumunun geçici durumu."""

    started_at: float
    target: WindowInfo | None
    pre_roll_seconds: float
    level_task: asyncio.Task[None] | None = field(default=None, repr=False)


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
    ) -> None:
        self._mic = mic
        self._stt = stt
        self._llm = llm
        self._db = db
        self._emit = emit

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

    async def start(self) -> None:
        """Kaydı başlatır. Zaten kayıttaysa yok sayar."""
        async with self._lock:
            if self.state is not DictationState.IDLE:
                log.debug("start() yok sayıldı, durum: %s", self.state)
                return

            # Hedef pencereyi kayıt başlarken yakalıyoruz: kullanıcı konuşurken
            # başka bir pencereye geçerse metin yine doğru yere gitmeli.
            target = get_foreground_window()
            if not self._mic.is_streaming:
                self._mic.start_stream()

            pre_roll = self._mic.start_recording()
            self._session = _Session(
                started_at=time.perf_counter(),
                target=target,
                pre_roll_seconds=pre_roll,
            )
            self._result = None

            await self._set_state(
                DictationState.LISTENING,
                preRollSeconds=round(pre_roll, 2),
                appName=target.app_name if target else None,
                windowTitle=target.title if target else None,
            )
            self._session.level_task = asyncio.create_task(self._stream_level())
            log.info(
                "Dikte başladı (pre-roll %.2f sn, hedef: %s)",
                pre_roll,
                target.app_name if target else "bilinmiyor",
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

        # 1) Konuşma → metin
        transcript = await self._stt.transcribe(clip, language=None)
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

        await self._emit(
            {
                "type": "dictation:progress",
                "step": "llm",
                "rawText": transcript.text,
                "fillersRemoved": local.removed_count,
                "sttMs": transcript.usage.latency_ms,
            }
        )

        # 3) LLM ile bağlama duyarlı temizlik
        llm_provider: str | None = None
        llm_model: str | None = None
        llm_ms = 0
        llm_cost = 0.0
        final_text = local.text

        if self._llm.is_available() and local.text:
            try:
                completion = await self._llm.complete(dictation_prompt(local.text))
                final_text = sanitize_output(completion.text) or local.text
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
        )

        result.record_id = self._db.add_dictation(
            DictationRecord(
                raw_text=result.raw_text,
                final_text=result.final_text,
                app_name=session.target.app_name if session.target else None,
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
        return result

    async def paste(self, text: str | None = None) -> None:
        """Pre-flight'taki metni hedef pencereye yapıştırır."""
        result = self._result
        if self.state is not DictationState.PREFLIGHT or result is None:
            return

        # Kullanıcı önizlemede düzenlemiş olabilir.
        content = text if text is not None else result.final_text

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

    async def toggle(self) -> None:
        """Kısayolun davranışı: boştaysa başlat, dinliyorsa bitir."""
        if self.state is DictationState.IDLE:
            await self.start()
        elif self.state is DictationState.LISTENING:
            await self.stop()
        # İşleme veya pre-flight sırasında kısayol yok sayılır; kullanıcı
        # Enter veya Esc ile karar verir.
