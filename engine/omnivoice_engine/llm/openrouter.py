"""OpenRouter LLM istemcisi.

Kullanıcı içeriğinin geçtiği ana yol. OpenRouter gönderilen veriyi model
eğitiminde kullanmaz ve her yanıtta gerçek maliyeti bildirir — harcama takibi
(Faz 2.12) bu değere dayanır, tahmine değil.
"""

from __future__ import annotations

import logging
import time

import httpx

from omnivoice_engine.config import get_settings
from omnivoice_engine.llm.base import Prompt
from omnivoice_engine.providers import (
    Completion,
    PrivacyClass,
    ProviderError,
    ProviderInfo,
    Usage,
)
from omnivoice_engine.vault import get_key

log = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SECONDS = 90.0

#: OpenRouter sıralamalarında uygulamayı tanıtan başlıklar. Zorunlu değil ama
#: sağlayıcı tarafında isteğin kaynağını görünür kılar.
ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/Alphyn12/omnivoice",
    "X-Title": "OmniVoice",
}


class OpenRouterLlm:
    """OpenRouter sohbet tamamlama istemcisi."""

    def __init__(self, default_model: str | None = None) -> None:
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        return self._default_model or get_settings().llm_model

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="openrouter",
            privacy=PrivacyClass.PRIVATE,
            models=[
                "anthropic/claude-3.5-haiku",
                "anthropic/claude-3.5-sonnet",
                "deepseek/deepseek-chat",
                "openai/gpt-4o-mini",
                "meta-llama/llama-3.3-70b-instruct",
            ],
        )

    def is_available(self) -> bool:
        return get_key("openrouter") is not None

    async def complete(self, prompt: Prompt, *, model: str | None = None) -> Completion:
        key = get_key("openrouter")
        if key is None:
            raise ProviderError("openrouter", "API anahtarı yok")

        chosen = model or self.default_model
        body = {
            "model": chosen,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": prompt.temperature,
            "max_tokens": prompt.max_tokens,
            # Gerçek maliyeti yanıtta istiyoruz; harcama takibi buna dayanıyor.
            "usage": {"include": True},
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    BASE_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        **ATTRIBUTION_HEADERS,
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
                f"HTTP {response.status_code}: {response.text[:300]}",
                retryable=retryable,
            )

        payload = response.json()

        # OpenRouter üst sağlayıcıdan gelen hatayı 200 gövdesinde de dönebilir.
        if "error" in payload:
            message = payload["error"].get("message", "bilinmeyen hata")
            raise ProviderError("openrouter", str(message))

        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError("openrouter", "yanıt boş döndü")

        text = str(choices[0].get("message", {}).get("content", "")).strip()
        usage = payload.get("usage") or {}

        return Completion(
            text=text,
            model=payload.get("model", chosen),
            provider="openrouter",
            usage=Usage(
                latency_ms=latency_ms,
                cost_usd=usage.get("cost"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            ),
        )
