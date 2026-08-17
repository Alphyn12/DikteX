"""Testlerde kullanılan sahte sağlayıcılar.

Ağa çıkmadan boru hattının davranışını sınamak için. Gerçek sağlayıcıların
sözleşmesini birebir karşılarlar; biri değişirse burası da değişmeli.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip
from omnivoice_engine.llm.base import Prompt
from omnivoice_engine.providers import (
    Completion,
    PrivacyClass,
    ProviderError,
    ProviderInfo,
    Transcript,
    Usage,
)


def speech_clip(seconds: float = 2.0, amplitude: int = 9000) -> AudioClip:
    """Konuşma benzeri sinyal — sessizlik denetimini geçer."""
    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    return AudioClip(
        samples=(np.sin(2 * np.pi * 180 * t) * amplitude).astype(np.int16),
        sample_rate=SAMPLE_RATE,
    )


def silent_clip(seconds: float = 2.0) -> AudioClip:
    return AudioClip(
        samples=np.zeros(int(SAMPLE_RATE * seconds), dtype=np.int16),
        sample_rate=SAMPLE_RATE,
    )


class FakeMic:
    """Sabit bir klip döndüren mikrofon."""

    def __init__(self, clip: AudioClip | None = None) -> None:
        self.clip = clip if clip is not None else speech_clip()
        self.cancelled = False

    def start_stream(self) -> None: ...
    def stop_stream(self) -> None: ...

    @property
    def is_streaming(self) -> bool:
        return True

    def start_recording(self) -> float:
        return 1.0

    def stop_recording(self) -> AudioClip:
        return self.clip

    def cancel_recording(self) -> None:
        self.cancelled = True

    @property
    def is_paused(self) -> bool:
        # Duraklatma (Faz 7.4) seviye döngüsünde okunuyor.
        return False

    @property
    def level(self) -> float:
        return 0.5

    @property
    def recorded_seconds(self) -> float:
        return self.clip.duration_seconds


class FakeStt:
    def __init__(
        self,
        text: str = "eee bu bir test",
        *,
        fail: bool = False,
        language: str = "Turkish",
    ) -> None:
        self.text = text
        self.fail = fail
        self.language = language
        self.calls = 0

    async def transcribe(self, clip: AudioClip, **_: Any) -> Transcript:
        self.calls += 1
        if self.fail:
            raise ProviderError("fakestt", "sağlayıcı düştü")
        return Transcript(
            text=self.text,
            language=self.language,
            model="fake-whisper",
            provider="fake",
            usage=Usage(latency_ms=100, cost_usd=None, audio_seconds=clip.duration_seconds),
        )


class FakeLlm:
    def __init__(
        self,
        *,
        available: bool = True,
        fail: bool = False,
        reply: str = "Bu bir test.",
    ) -> None:
        self.available = available
        self.fail = fail
        self.reply = reply
        self.last_prompt: Prompt | None = None
        self.calls = 0

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="fake", privacy=PrivacyClass.PRIVATE)

    def is_available(self) -> bool:
        return self.available

    async def complete(self, prompt: Prompt, *, model: str | None = None) -> Completion:
        self.calls += 1
        self.last_prompt = prompt
        if self.fail:
            raise ProviderError("fakellm", "kota doldu", retryable=True)
        return Completion(
            text=self.reply,
            model=model or "fake-llm",
            provider="fake",
            usage=Usage(latency_ms=200, cost_usd=0.000123, input_tokens=10, output_tokens=5),
        )
