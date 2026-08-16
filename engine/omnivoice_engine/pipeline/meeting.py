"""Toplantı boru hattı (Faz 4).

Akış:

    idle ──start──▶ recording ──stop──▶ transcribing ──▶ summarizing ──▶ done
                        │                    │                │            │
                        └────────cancel──────┴────────────────┴────────────┘

Mikrofon ve sistem sesi ayrı kanallar olarak kaydedilir, ayrı ayrı metne
çevrilir ve etiketlenerek birleştirilir. Böylece konuşmacı ayrımı servisi
olmadan "ben / diğerleri" ayrımı elde edilir.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from omnivoice_engine.audio.capture import MicrophoneCapture
from omnivoice_engine.audio.loopback import MeetingRecorder, MeetingRecording
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.pipeline.meeting_prompts import (
    action_items_prompt,
    label_channels,
    summary_prompt,
)
from omnivoice_engine.pipeline.prompts import sanitize_output
from omnivoice_engine.privacy.masking import MaskResult, mask
from omnivoice_engine.providers import ProviderError
from omnivoice_engine.storage.db import Database
from omnivoice_engine.stt.router import SttRouter

log = logging.getLogger(__name__)

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

#: Süre ve seviye arayüze bu sıklıkta gönderilir. Toplantı uzun sürdüğü için
#: dikteden seyrek: saniyede iki kez yeterli, WebSocket'i yormaya gerek yok.
_TICK_INTERVAL = 0.5


class MeetingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    DONE = "done"
    ERROR = "error"


@dataclass
class ActionItem:
    task: str
    owner: str | None = None
    due: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {"task": self.task, "owner": self.owner, "due": self.due}


@dataclass
class MeetingResult:
    """Bitmiş bir toplantının çıktısı."""

    transcript: str
    summary: str
    action_items: list[ActionItem]
    duration_seconds: float
    language: str | None
    #: Hangi kanalların ses içerdiği — arayüzde rozetle gösterilir.
    had_microphone: bool
    had_system_audio: bool
    stt_ms: int
    llm_ms: int
    cost_usd: float
    record_id: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "transcript": self.transcript,
            "summary": self.summary,
            "actionItems": [item.to_payload() for item in self.action_items],
            "durationSeconds": round(self.duration_seconds, 1),
            "language": self.language,
            "hadMicrophone": self.had_microphone,
            "hadSystemAudio": self.had_system_audio,
            "sttMs": self.stt_ms,
            "llmMs": self.llm_ms,
            "costUsd": self.cost_usd,
            "recordId": self.record_id,
        }


@dataclass
class _Session:
    started_at: float
    tick_task: asyncio.Task[None] | None = field(default=None, repr=False)


class MeetingPipeline:
    """Toplantı kaydını ve işlenmesini yönetir."""

    def __init__(
        self,
        *,
        mic: MicrophoneCapture,
        stt: SttRouter,
        llm: OpenRouterLlm,
        db: Database,
        emit: EventSink,
        mask_pii: bool = True,
    ) -> None:
        self._mic = mic
        self._stt = stt
        self._llm = llm
        self._db = db
        self._emit = emit
        self._mask_pii = mask_pii

        self._recorder = MeetingRecorder()
        self.state = MeetingState.IDLE
        self._session: _Session | None = None
        self._result: MeetingResult | None = None
        self._lock = asyncio.Lock()

    # ── Gizlilik ──────────────────────────────────────────────────────────

    @property
    def pii_masking(self) -> bool:
        """Hassas veri maskeleme açık mı (Properties VI.1)."""
        return self._mask_pii

    def set_pii_masking(self, enabled: bool) -> None:
        self._mask_pii = enabled

    # ── Durum ─────────────────────────────────────────────────────────────

    async def _set_state(self, state: MeetingState, **extra: Any) -> None:
        self.state = state
        await self._emit({"type": "meeting:state", "state": state.value, **extra})

    def get_result(self) -> MeetingResult | None:
        return self._result

    # ── Kayıt ─────────────────────────────────────────────────────────────

    async def start(self, *, system_device: str | None = None) -> None:
        """Toplantı kaydını başlatır."""
        async with self._lock:
            if self.state in {
                MeetingState.RECORDING,
                MeetingState.TRANSCRIBING,
                MeetingState.SUMMARIZING,
            }:
                return

            if not self._mic.is_streaming:
                self._mic.start_stream()

            self._mic.start_recording()
            self._recorder.start(system_device)
            self._session = _Session(started_at=time.perf_counter())
            self._result = None

            await self._set_state(MeetingState.RECORDING, seconds=0)
            self._session.tick_task = asyncio.create_task(self._tick())
            log.info("Toplantı kaydı başladı")

    async def _tick(self) -> None:
        """Süre ve seviyeleri arayüze akıtır."""
        try:
            while self.state is MeetingState.RECORDING:
                await self._emit(
                    {
                        "type": "meeting:tick",
                        "seconds": round(self._recorder.elapsed_seconds, 1),
                        "micLevel": round(self._mic.level, 4),
                        "systemLevel": round(self._recorder.system_level, 4),
                    }
                )
                await asyncio.sleep(_TICK_INTERVAL)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Kaydı bitirir, dökümü ve özeti üretir."""
        async with self._lock:
            if self.state is not MeetingState.RECORDING or self._session is None:
                return
            session = self._session
            if session.tick_task:
                session.tick_task.cancel()

            mic_clip = self._mic.stop_recording()
            recording = self._recorder.stop(mic_clip)
            await self._set_state(MeetingState.TRANSCRIBING)

        try:
            result = await self._process(recording)
        except ProviderError as exc:
            log.error("Toplantı işlenemedi: %s", exc)
            self._session = None
            await self._set_state(MeetingState.ERROR, message=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("Toplantı boru hattında beklenmedik hata")
            self._session = None
            await self._set_state(MeetingState.ERROR, message=str(exc))
            return

        self._result = result
        self._session = None
        await self._set_state(MeetingState.DONE, result=result.to_payload())

    async def _process(self, recording: MeetingRecording) -> MeetingResult:
        if not recording.has_audio:
            raise ProviderError("meeting", "Kayıtta konuşma yok")

        stt_ms = 0
        cost = 0.0
        texts: dict[str, str] = {}
        language: str | None = None

        # İki kanal ayrı ayrı çevriliyor; hangi metnin kimden geldiğini
        # böylece biliyoruz.
        channels = [
            ("mine", recording.microphone),
            ("theirs", recording.system),
        ]
        for name, clip in channels:
            if clip is None or clip.is_silent():
                texts[name] = ""
                continue

            async def progress(done: int, total: int, channel: str = name) -> None:
                await self._emit(
                    {
                        "type": "meeting:progress",
                        "step": "stt",
                        "channel": channel,
                        "chunk": done,
                        "chunks": total,
                    }
                )

            transcript = await self._stt.transcribe(
                clip, language=language, on_progress=progress
            )
            texts[name] = transcript.text
            stt_ms += transcript.usage.latency_ms
            cost += transcript.usage.cost_usd or 0.0
            language = language or transcript.language

            self._db.add_spend(
                provider=transcript.provider,
                model=transcript.model,
                kind="stt",
                cost_usd=transcript.usage.cost_usd,
                latency_ms=transcript.usage.latency_ms,
                meta={"channel": name, "audioSeconds": round(clip.duration_seconds, 1)},
            )

        combined = label_channels(texts.get("mine", ""), texts.get("theirs", ""))
        if not combined.strip():
            raise ProviderError("meeting", "Döküm boş çıktı")

        await self._set_state(MeetingState.SUMMARIZING)

        summary, items, llm_ms, llm_cost = await self._summarize(combined, language)
        cost += llm_cost

        result = MeetingResult(
            transcript=combined,
            summary=summary,
            action_items=items,
            duration_seconds=recording.duration_seconds,
            language=language,
            had_microphone=bool(texts.get("mine", "").strip()),
            had_system_audio=bool(texts.get("theirs", "").strip()),
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            cost_usd=cost,
        )
        result.record_id = self._db.add_meeting(
            transcript=result.transcript,
            summary=result.summary,
            action_items=[item.to_payload() for item in result.action_items],
            duration_seconds=result.duration_seconds,
            language=result.language,
            cost_usd=result.cost_usd,
        )
        return result

    async def _summarize(
        self, transcript: str, language: str | None
    ) -> tuple[str, list[ActionItem], int, float]:
        """Özet ve eylem maddelerini üretir.

        LLM düşerse dökümü kaybetmiyoruz: özet boş kalır ama ham metin durur.
        """
        if not self._llm.is_available():
            return "", [], 0, 0.0

        llm_ms = 0
        cost = 0.0
        summary = ""
        items: list[ActionItem] = []

        # PII maskeleme (Properties VI.1). Toplantı dökümü dikte metninden
        # daha riskli: uzun, kullanıcının denetlemediği ve karşı taraf da
        # konuşuyor. Birinin sesli okuduğu bir IBAN veya hesap numarası
        # buradan geçer.
        masked = mask(transcript) if self._mask_pii else MaskResult(text=transcript)
        if masked.masked_count:
            log.info("Toplantı dökümünde PII maskelendi: %d değer", masked.masked_count)

        try:
            completion = await self._llm.complete(
                summary_prompt(masked.text, language=language)
            )
            summary = masked.unmask(sanitize_output(completion.text))
            llm_ms += completion.usage.latency_ms
            cost += completion.usage.cost_usd or 0.0
            self._db.add_spend(
                provider=completion.provider,
                model=completion.model,
                kind="llm",
                cost_usd=completion.usage.cost_usd,
                latency_ms=completion.usage.latency_ms,
                meta={"kind": "meeting_summary"},
            )
        except ProviderError as exc:
            log.warning("Toplantı özeti atlandı: %s", exc)
            await self._emit({"type": "meeting:warning", "message": f"Özet atlandı: {exc}"})

        try:
            completion = await self._llm.complete(
                action_items_prompt(masked.text, language=language)
            )
            items = _parse_action_items(masked.unmask(completion.text))
            llm_ms += completion.usage.latency_ms
            cost += completion.usage.cost_usd or 0.0
            self._db.add_spend(
                provider=completion.provider,
                model=completion.model,
                kind="llm",
                cost_usd=completion.usage.cost_usd,
                latency_ms=completion.usage.latency_ms,
                meta={"kind": "action_items"},
            )
        except ProviderError as exc:
            log.warning("Eylem maddeleri atlandı: %s", exc)

        return summary, items, llm_ms, cost

    async def cancel(self) -> None:
        """Kaydı atar."""
        async with self._lock:
            if self._session and self._session.tick_task:
                self._session.tick_task.cancel()
            self._mic.cancel_recording()
            self._recorder.stop(None)
            self._session = None
            self._result = None
            await self._set_state(MeetingState.IDLE, cancelled=True)

    async def dismiss(self) -> None:
        """Sonucu kapatır."""
        self._result = None
        await self._set_state(MeetingState.IDLE)

    async def toggle(self, *, system_device: str | None = None) -> None:
        if self.state is MeetingState.RECORDING:
            await self.stop()
        elif self.state in {MeetingState.IDLE, MeetingState.DONE, MeetingState.ERROR}:
            await self.start(system_device=system_device)


def _parse_action_items(raw: str) -> list[ActionItem]:
    """Modelin JSON çıktısını ayrıştırır.

    Model kurallara rağmen ``` ile sarabilir veya araya cümle koyabilir; bu
    yüzden önce temizliyor, sonra ilk JSON dizisini arıyoruz. Ayrıştırma
    başarısız olursa boş liste döner — uydurma bir görev listesi göstermek,
    hiç göstermemekten kötüdür.
    """
    cleaned = sanitize_output(raw)

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        log.warning("Eylem maddesi JSON'u bulunamadı: %r", cleaned[:120])
        return []

    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        log.warning("Eylem maddesi JSON'u çözümlenemedi: %r", cleaned[:120])
        return []

    if not isinstance(data, list):
        return []

    items: list[ActionItem] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        task = str(entry.get("task", "")).strip()
        if not task:
            continue
        owner = entry.get("owner")
        due = entry.get("due")
        items.append(
            ActionItem(
                task=task,
                owner=str(owner).strip() if owner else None,
                due=str(due).strip() if due else None,
            )
        )
    return items
