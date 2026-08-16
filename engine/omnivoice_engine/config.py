"""Motor yapılandırması.

Anahtarlar yalnız bu süreçte yaşar. Electron tarafına hiçbir zaman
gönderilmezler (bkz. docs/ARCHITECTURE.md § Gizli bilgi yönetimi).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    """engine/omnivoice_engine/config.py → depo kökü."""
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Ortam değişkenlerinden okunan ayarlar."""

    model_config = SettingsConfigDict(
        env_file=_repo_root() / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Sağlayıcı anahtarları ────────────────────────────────────────────────
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    # ── Varsayılan modeller ──────────────────────────────────────────────────
    #
    # Bu iki değer tahminle değil, gerçek Türkçe seslerle ölçülerek seçildi:
    #
    #   STT — Groq whisper-large-v3-turbo, ~1.2 sn, Türkçe karakterler dahil
    #         neredeyse kusursuz, özel sözlük enjeksiyonu çalışıyor.
    #
    #   LLM — gemini-3.5-flash-lite. Üç kuşak yan yana ölçüldü:
    #           2.5-flash-lite : 6/7 · 1517 ms · $0.09/ay
    #           3.1-flash-lite : 7/7 · 1184 ms · $0.24/ay
    #           3.5-flash-lite : 7/7 ·  900 ms · $0.30/ay   ← seçilen
    #         2.5, dikte edilen "önceki talimatları unut" cümlesini kendine
    #         talimat sanıp uyguluyordu; 3.5 direndi, üstelik %40 daha hızlı
    #         ve görselde okuyamadığı yeri uydurmak yerine söylüyor.
    #         Maliyet 3,3 kat arttı ama ayda 30 sent hâlâ önemsiz.
    #
    # Not: Gemini'ye buradan OpenRouter üzerinden, yani ücretli uç noktadan
    # gidilir. Doğrudan AI Studio anahtarıyla kullanılan ücretsiz katman ayrı
    # bir yoldur ve eğitime açıktır (bkz. providers.PrivacyClass).
    stt_model: str = Field(default="whisper-large-v3-turbo", alias="OMNIVOICE_STT_MODEL")
    llm_model: str = Field(default="google/gemini-3.5-flash-lite", alias="OMNIVOICE_LLM_MODEL")

    # ── Çalışma zamanı ───────────────────────────────────────────────────────
    port: int = Field(default=8756, alias="OMNIVOICE_ENGINE_PORT")
    budget_usd: float = Field(default=5.0, alias="OMNIVOICE_BUDGET_USD")

    @property
    def configured_providers(self) -> list[str]:
        """Anahtarı girilmiş sağlayıcılar. Anahtarın kendisi asla döndürülmez."""
        present = {
            "groq": self.groq_api_key,
            "openrouter": self.openrouter_api_key,
            "gemini": self.gemini_api_key,
        }
        # Kullanıcı yer tutucuyu silmemiş olabilir; onu girilmiş sayma.
        return sorted(
            name
            for name, key in present.items()
            if key and key.strip() and key.strip() != "BURAYA_YAPISTIR"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ayarları bir kez okur, sonraki çağrılarda aynı nesneyi döndürür."""
    return Settings()
