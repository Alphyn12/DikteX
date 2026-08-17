"""Gemini LLM sağlayıcısı.

Bu sağlayıcının en önemli özelliği teknik değil: **gizlilik sınıfı farklı.**
AI Studio'nun ücretsiz katmanı gönderilen veriyi eğitimde kullanıyor, oysa
aynı model OpenRouter üzerinden eğitime kapalı. Sınıfın yanlış işaretlenmesi
kullanıcıya olmayan bir koruma vaat etmek olurdu.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.llm.gemini import DEFAULT_MODEL, GeminiLlm, _split_data_url
from omnivoice_engine.providers import PrivacyClass


class TestGizlilikSinifi:
    def test_egitime_ACIK_isaretli(self) -> None:
        """Ücretsiz katman veriyi eğitimde kullanıyor; bu gizlenemez."""
        assert GeminiLlm().info.privacy is PrivacyClass.TRAINS_ON_DATA

    def test_openrouter_ile_farkli(self) -> None:
        """Aynı model, iki sağlayıcı, iki gizlilik sınıfı."""
        from omnivoice_engine.llm.openrouter import OpenRouterLlm

        assert OpenRouterLlm().info.privacy is PrivacyClass.PRIVATE
        assert GeminiLlm().info.privacy is PrivacyClass.TRAINS_ON_DATA


class TestModelSecimi:
    def test_varsayilan(self) -> None:
        assert GeminiLlm().default_model == DEFAULT_MODEL

    def test_ozel_model(self) -> None:
        assert GeminiLlm("gemini-2.5-pro").default_model == "gemini-2.5-pro"

    def test_bos_dize_varsayilana_doner(self) -> None:
        """Arayüzden temizlenen alan geçersiz bir model kimliği üretmemeli."""
        llm = GeminiLlm("gemini-2.5-pro")
        llm.set_default_model("   ")
        assert llm.default_model == DEFAULT_MODEL


class TestGorselAyristirma:
    def test_data_url_cozulur(self) -> None:
        veri = _split_data_url("data:image/png;base64,aGVsbG8=")
        assert veri is not None
        mime, raw = veri
        assert mime == "image/png"
        assert raw == b"hello"

    @pytest.mark.parametrize("girdi", ["https://a.com/x.png", "bozuk", "data:yok"])
    def test_gecersiz_girdi_none(self, girdi: str) -> None:
        """Çözülemeyen görsel isteği çökertmemeli; atlanıyor."""
        assert _split_data_url(girdi) is None
