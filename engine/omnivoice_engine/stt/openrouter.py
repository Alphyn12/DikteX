"""OpenRouter üzerinden konuşma tanıma — Groq yedeği.

Groq'un ücretsiz kotası dolduğunda veya servis yanıt vermediğinde devreye
girer. OpenRouter maliyeti yanıtta bildirdiği için harcama gerçek değerle
kaydedilir.
"""

from __future__ import annotations

import base64
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

BASE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
DEFAULT_MODEL = "openai/gpt-4o-mini-transcribe"
TIMEOUT_SECONDS = 60.0

#: OpenRouter'ın belgelenmiş sınırları. Bunları aşan ses parçalanmalıdır
#: (Faz 4.2 — uzun toplantı kayıtları).
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_REQUEST_SECONDS = 60


class OpenRouterStt:
    """OpenRouter transkripsiyon istemcisi."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="openrouter",
            privacy=PrivacyClass.PRIVATE,
            models=[
                "openai/gpt-4o-mini-transcribe",
                "openai/gpt-4o-transcribe",
                "mistralai/voxtral-mini-transcribe",
            ],
        )

    def is_available(self) -> bool:
        return get_key("openrouter") is not None

    async def transcribe(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
    ) -> Transcript:
        del vocabulary  # Bu uç nokta bağlam ipucu almıyor.

        key = get_key("openrouter")
        if key is None:
            raise ProviderError("openrouter", "API anahtarı yok")

        wav = clip.to_wav_bytes()
        if len(wav) > MAX_UPLOAD_BYTES:
            raise ProviderError(
                "openrouter",
                f"ses {len(wav) // 1024 // 1024} MB — sınır {MAX_UPLOAD_BYTES // 1024 // 1024} MB",
            )

        body: dict[str, object] = {
            "model": self.model,
            "input_audio": {
                "data": base64.b64encode(wav).decode("ascii"),
                "format": "wav",
            },
        }
        if language:
            body["language"] = language

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    BASE_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("openrouter", "istek zaman aşımına uğradı", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("openrouter", f"ağ hatası: {exc}", retryable=True) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code != 200:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ProviderError(
                "openrouter",
                f"HTTP {response.status_code}: {response.text[:200]}",
                retryable=retryable,
            )

        payload = response.json()
        usage = payload.get("usage") or {}
        return Transcript(
            text=str(payload.get("text", "")).strip(),
            language=language,
            model=self.model,
            provider="openrouter",
            usage=Usage(
                latency_ms=latency_ms,
                cost_usd=usage.get("cost"),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                audio_seconds=usage.get("seconds", clip.duration_seconds),
            ),
        )
