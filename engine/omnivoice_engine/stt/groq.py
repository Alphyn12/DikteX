"""Groq üzerinden konuşma tanıma.

Varsayılan STT sağlayıcısı: `whisper-large-v3-turbo` gerçek zamanlının çok
üzerinde hızda çalışır ve ücretsiz katmanı cömerttir. Groq gönderilen veriyi
model eğitiminde kullanmaz.
"""

from __future__ import annotations

import logging
import time

import httpx

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.providers import (
    PrivacyClass,
    ProviderError,
    ProviderInfo,
    Transcript,
    Usage,
)
from omnivoice_engine.vault import get_key

log = logging.getLogger(__name__)

BASE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"
TIMEOUT_SECONDS = 60.0

#: Groq'un ücretsiz katmanı süre bazlı ücretlendirilmediği için maliyet
#: bildirilmez. Uydurma bir rakam yazmak yerine `None` bırakıyoruz.
COST_UNKNOWN = None


class GroqStt:
    """Groq Whisper istemcisi."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="groq",
            privacy=PrivacyClass.PRIVATE,
            models=["whisper-large-v3-turbo", "whisper-large-v3"],
        )

    def is_available(self) -> bool:
        return get_key("groq") is not None

    async def transcribe(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
    ) -> Transcript:
        key = get_key("groq")
        if key is None:
            raise ProviderError("groq", "API anahtarı yok")

        data: dict[str, str] = {
            "model": self.model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language
        if vocabulary:
            # Whisper `prompt` alanını bir bağlam ipucu olarak kullanır; özel
            # terimleri buraya koymak yazımlarının korunma olasılığını artırır.
            data["prompt"] = ", ".join(vocabulary[:100])

        files = {"file": ("audio.wav", clip.to_wav_bytes(), "audio/wav")}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    BASE_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    data=data,
                    files=files,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("groq", "istek zaman aşımına uğradı", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("groq", f"ağ hatası: {exc}", retryable=True) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code != 200:
            # 429 (kota) ve 5xx yeniden denenebilir; yönlendirici bu bilgiyle
            # bir sonraki sağlayıcıya geçer.
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ProviderError(
                "groq",
                f"HTTP {response.status_code}: {response.text[:200]}",
                retryable=retryable,
            )

        payload = response.json()
        return Transcript(
            text=str(payload.get("text", "")).strip(),
            language=payload.get("language"),
            model=self.model,
            provider="groq",
            usage=Usage(
                latency_ms=latency_ms,
                cost_usd=COST_UNKNOWN,
                audio_seconds=clip.duration_seconds,
            ),
        )
