"""Gemini LLM sağlayıcısı — doğrudan Google AI Studio uç noktası.

OpenRouter'a alternatif. Kullanıcının kendi Gemini anahtarını kullanıyor ve
OpenRouter bakiyesinden harcamıyor.

## Gizlilik — bu sağlayıcının bilinmesi gereken tarafı

AI Studio'nun **ücretsiz katmanı gönderilen veriyi model eğitiminde
kullanıyor.** OpenRouter üzerinden giden Gemini ise ücretli uç nokta ve
eğitime kapalı. Yani aynı model, iki farklı gizlilik sınıfı.

Bu yüzden sağlayıcı `TRAINS_ON_DATA` olarak işaretli ve arayüzde rozetle
gösteriliyor. Seçim kullanıcının, ama bilerek yapması gerekiyor.

## API şekli ölçülerek yazıldı

    systemInstruction : {"parts": [{"text": ...}]}
    contents          : [{"role": "user", "parts": [...]}]
    generationConfig  : {"temperature", "maxOutputTokens"}
    yanıt             : candidates[0].content.parts[0].text
    kullanım          : usageMetadata.promptTokenCount / candidatesTokenCount

Ölçülen gecikme: ~1.2 sn (gemini-3.5-flash-lite, kısa metin).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

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

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_SECONDS = 60.0

#: Varsayılan model. Ölçüldü: 1.2 sn, Türkçe temizlik doğru.
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def _split_data_url(data_url: str) -> tuple[str, bytes] | None:
    """`data:image/png;base64,...` biçimini MIME + bayt olarak ayırır."""
    if not data_url.startswith("data:"):
        return None
    try:
        header, payload = data_url.split(",", 1)
        mime = header[5:].split(";", 1)[0] or "image/png"
        return mime, base64.b64decode(payload)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None


class GeminiLlm:
    """Google AI Studio sohbet istemcisi."""

    def __init__(self, default_model: str | None = None) -> None:
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        return self._default_model or DEFAULT_MODEL

    def set_default_model(self, model: str | None) -> None:
        self._default_model = (model or "").strip() or None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="gemini",
            # Ücretsiz katman eğitime açık. Bu, aynı modelin OpenRouter
            # üzerinden gelen hâlinden FARKLI bir gizlilik sınıfı.
            privacy=PrivacyClass.TRAINS_ON_DATA,
            models=[DEFAULT_MODEL, "gemini-2.5-flash", "gemini-2.5-pro"],
        )

    def is_available(self) -> bool:
        return get_key("gemini") is not None

    async def complete(self, prompt: Prompt, *, model: str | None = None) -> Completion:
        key = get_key("gemini")
        if key is None:
            raise ProviderError("gemini", "API anahtarı yok")

        chosen = model or self.default_model

        parts: list[dict[str, Any]] = [{"text": prompt.user}]
        for image in prompt.images:
            split = _split_data_url(image)
            if split is None:
                log.warning("Görsel çözümlenemedi, atlandı")
                continue
            mime, raw = split
            parts.append(
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}
            )

        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": prompt.temperature,
                "maxOutputTokens": prompt.max_tokens,
            },
        }
        if prompt.system:
            body["systemInstruction"] = {"parts": [{"text": prompt.system}]}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{BASE_URL}/{chosen}:generateContent",
                    params={"key": key},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("gemini", "istek zaman aşımına uğradı", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("gemini", f"ağ hatası: {exc}", retryable=True) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= 400:
            # 429 kota, 5xx geçici; ikisi de yeniden denenebilir ve kuyruk
            # (Faz 7.2) bu bayrağa bakıyor.
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ProviderError(
                "gemini",
                f"{response.status_code}: {_error_message(response)}",
                retryable=retryable,
            )

        payload = response.json()
        text = _first_text(payload)
        if not text:
            # Güvenlik süzgeci yanıtı engellemiş olabilir; sebebi söylemek
            # "boş döndü" demekten çok daha yararlı.
            raise ProviderError("gemini", f"boş yanıt ({_finish_reason(payload)})")

        usage = payload.get("usageMetadata") or {}
        return Completion(
            text=text,
            model=chosen,
            provider="gemini",
            usage=Usage(
                latency_ms=latency_ms,
                # Ücretsiz katmanda maliyet bildirilmiyor. Uydurma bir rakam
                # yazmak yerine `None` bırakıyoruz; arayüz tahmin göstermiyor.
                cost_usd=None,
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            ),
        )


def _first_text(payload: dict[str, Any]) -> str:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    return "".join(str(p.get("text", "")) for p in parts).strip()


def _finish_reason(payload: dict[str, Any]) -> str:
    try:
        return str(payload["candidates"][0].get("finishReason", "sebep bilinmiyor"))
    except (KeyError, IndexError, TypeError):
        return "sebep bilinmiyor"


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])[:200]
    except Exception:  # noqa: BLE001
        return response.text[:200]
