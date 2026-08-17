"""Canlı model kataloğu (Faz 3.15).

Model listesi OpenRouter'dan **çalışma zamanında** çekiliyor, koda gömülmüyor.
Sebebi bu projenin kendi geçmişinde: geliştirme sırasında `claude-3.5-haiku`
ortadan kalktı ve `gemini-3.5-flash-lite` ortaya çıktı. Gömülü bir liste o
anlarda yalan söyler — kullanıcıya artık var olmayan bir modeli sunar ve hata
ancak dikte sırasında görünür.

Katalog **önbelleğe alınıyor**: liste yüzlerce model içeriyor ve her ayar
ekranı açılışında yeniden çekmek hem yavaş hem gereksiz.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from omnivoice_engine.config import get_settings
from omnivoice_engine.providers import ProviderError

log = logging.getLogger(__name__)

MODELS_URL = "https://openrouter.ai/api/v1/models"
TIMEOUT_SECONDS = 15.0

#: Katalog bu süre boyunca yeniden çekilmiyor. Modeller günlerde değişiyor,
#: dakikalarda değil.
CACHE_SECONDS = 3600.0


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Kataloğdan gelen bir model."""

    id: str
    name: str
    #: 1M girdi jetonu başına dolar. Bilinmiyorsa `None` — arayüzde tahmin
    #: uydurulmuyor.
    input_price: float | None
    output_price: float | None
    context_length: int | None
    #: Görsel girdi kabul ediyor mu — ekran gözü modu bunu gerektiriyor.
    supports_images: bool
    #: Model kimliğindeki `:` ekinden gelen varyant — `free`, `batch`,
    #: `thinking` ya da `None`.
    variant: str | None

    @property
    def interactive(self) -> bool:
        """Dikte gibi anlık işler için kullanılabilir mi?

        `:batch` varyantları **eşzamansız toplu işleme** uç noktaları: istek
        kuyruğa alınıyor ve yanıt saatler sonra gelebiliyor. Katalogda 61 tane
        var ve adları normal modellerden yalnız iki nokta ile ayrılıyor —
        kullanıcının yanlışlıkla seçmesi çok kolay. Seçerse dikte hiç
        dönmez ve sebebi hiçbir yerde yazmaz.
        """
        return self.variant != "batch"

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "inputPrice": self.input_price,
            "outputPrice": self.output_price,
            "contextLength": self.context_length,
            "supportsImages": self.supports_images,
            "variant": self.variant,
            "interactive": self.interactive,
        }


def _price(value: object) -> float | None:
    """OpenRouter fiyatları jeton başına dize olarak veriyor; 1M'e çeviriyoruz."""
    try:
        per_token = float(str(value))
    except (TypeError, ValueError):
        return None
    # 0 gerçek bir değer (ücretsiz katman), None ise "bilinmiyor".
    return round(per_token * 1_000_000, 4)


def _parse(entry: dict[str, object]) -> ModelInfo | None:
    model_id = str(entry.get("id", "")).strip()
    if not model_id:
        return None

    pricing = entry.get("pricing") or {}
    architecture = entry.get("architecture") or {}
    modalities = []
    if isinstance(architecture, dict):
        raw = architecture.get("input_modalities") or architecture.get("modality") or ""
        modalities = raw if isinstance(raw, list) else [str(raw)]

    context = entry.get("context_length")
    return ModelInfo(
        id=model_id,
        name=str(entry.get("name") or model_id),
        input_price=_price(pricing.get("prompt")) if isinstance(pricing, dict) else None,
        output_price=_price(pricing.get("completion")) if isinstance(pricing, dict) else None,
        context_length=int(context) if isinstance(context, (int, float)) else None,
        supports_images=any("image" in str(m).lower() for m in modalities),
        variant=model_id.split(":", 1)[1] if ":" in model_id else None,
    )


class ModelCatalog:
    """OpenRouter model listesi, önbellekli."""

    def __init__(self) -> None:
        self._models: list[ModelInfo] = []
        self._fetched_at = 0.0

    @property
    def is_stale(self) -> bool:
        return (time.time() - self._fetched_at) > CACHE_SECONDS

    async def models(self, *, force: bool = False) -> list[ModelInfo]:
        """Katalog. Önbellek tazeyse ağa çıkılmaz."""
        if self._models and not force and not self.is_stale:
            return self._models

        try:
            fetched = await self._fetch()
        except ProviderError:
            # Ağ yoksa elimizdeki eski listeyi vermek, boş liste vermekten
            # iyi: kullanıcı en azından mevcut seçimini görebiliyor.
            if self._models:
                log.warning("Model kataloğu tazelenemedi, önbellek kullanılıyor")
                return self._models
            raise

        self._models = fetched
        self._fetched_at = time.time()
        return self._models

    async def _fetch(self) -> list[ModelInfo]:
        settings = get_settings()
        headers = {}
        # Anahtar zorunlu değil — `/models` herkese açık. Varsa gönderiyoruz ki
        # hesaba özel kullanılabilirlik bilgisi doğru gelsin.
        if settings.openrouter_api_key:
            headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(MODELS_URL, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError("openrouter", "model listesi zaman aşımı", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("openrouter", f"ağ hatası: {exc}", retryable=True) from exc

        if response.status_code >= 400:
            raise ProviderError(
                "openrouter",
                f"model listesi alınamadı ({response.status_code})",
                retryable=response.status_code >= 500,
            )

        payload = response.json()
        entries = payload.get("data", []) if isinstance(payload, dict) else []
        models = [m for m in (_parse(e) for e in entries if isinstance(e, dict)) if m]
        log.info("Model kataloğu alındı: %d model", len(models))
        return sorted(models, key=lambda m: m.id)
