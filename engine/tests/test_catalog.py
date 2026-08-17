"""Canlı model kataloğu (Faz 3.15).

Katalog OpenRouter'dan çalışma zamanında geliyor. Ayrıştırma **gerçek yanıta
karşı ölçülerek** yazıldı; buradaki testler o şekli sabitliyor ki API değişince
sessizce bozulmasın.

Ölçülen gerçek değerler (17 Ağustos 2026, 414 model):

    google/gemini-3.5-flash-lite
      pricing.prompt      "0.0000003"  → 0.3  $/1M
      pricing.completion  "0.0000025"  → 2.5  $/1M
      context_length      1048576
      input_modalities    [text, image, video, file, audio]
"""

from __future__ import annotations

import pytest

from omnivoice_engine.llm.catalog import ModelCatalog, _parse, _price


class TestFiyatCevrimi:
    def test_jeton_basina_fiyat_1m_e_cevrilir(self) -> None:
        assert _price("0.0000003") == 0.3
        assert _price("0.0000025") == 2.5

    def test_sifir_gercek_bir_deger(self) -> None:
        """Ücretsiz katman 0; `None` ile karıştırılmamalı."""
        assert _price("0") == 0.0

    @pytest.mark.parametrize("deger", [None, "", "bedava", {}])
    def test_bilinmeyen_fiyat_none(self, deger: object) -> None:
        """Arayüzde tahmin uydurulmuyor."""
        assert _price(deger) is None


class TestAyristirma:
    def test_gercek_yanit_sekli(self) -> None:
        model = _parse(
            {
                "id": "google/gemini-3.5-flash-lite",
                "name": "Google: Gemini 3.5 Flash Lite",
                "context_length": 1048576,
                "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
                "architecture": {
                    "input_modalities": ["text", "image", "video", "file", "audio"],
                    "output_modalities": ["text"],
                },
            }
        )
        assert model is not None
        assert model.id == "google/gemini-3.5-flash-lite"
        assert model.input_price == 0.3
        assert model.output_price == 2.5
        assert model.context_length == 1048576
        assert model.supports_images
        assert model.variant is None
        assert model.interactive

    def test_kimliksiz_kayit_atlanir(self) -> None:
        assert _parse({"name": "adı var kimliği yok"}) is None

    def test_eksik_alanlar_cokertmez(self) -> None:
        model = _parse({"id": "bir/model"})
        assert model is not None
        assert model.input_price is None
        assert model.context_length is None
        assert not model.supports_images

    def test_metin_modalite_dizesi(self) -> None:
        """Bazı kayıtlarda `modality` tek dize olarak geliyor."""
        model = _parse({"id": "a/b", "architecture": {"modality": "text+image->text"}})
        assert model is not None
        assert model.supports_images


class TestVaryantlar:
    def test_batch_ETKILESIMLI_DEGIL(self) -> None:
        """Katalogda 61 `:batch` modeli var ve adları normalden yalnız iki
        nokta ile ayrılıyor.

        `:batch` eşzamansız toplu işleme uç noktası: istek kuyruğa alınıyor,
        yanıt saatler sonra gelebiliyor. Kullanıcı dikte için seçerse hiçbir
        şey dönmez ve sebebi hiçbir yerde yazmaz.
        """
        model = _parse({"id": "google/gemini-3.5-flash-lite:batch"})
        assert model is not None
        assert model.variant == "batch"
        assert not model.interactive

    def test_free_varyanti_isaretlenir(self) -> None:
        model = _parse({"id": "liquid/lfm-2.5-2.6b:free"})
        assert model is not None
        assert model.variant == "free"
        # Ücretsiz katman etkileşimli çalışıyor; yalnız işaretleniyor.
        assert model.interactive

    def test_normal_model_varyantsiz(self) -> None:
        model = _parse({"id": "openai/gpt-4o-mini"})
        assert model is not None
        assert model.variant is None


class TestOnbellek:
    @pytest.mark.asyncio
    async def test_taze_onbellek_aga_cikmaz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        catalog = ModelCatalog()
        calls = 0

        async def fake_fetch() -> list:
            nonlocal calls
            calls += 1
            return [_parse({"id": "a/b"})]

        monkeypatch.setattr(catalog, "_fetch", fake_fetch)
        await catalog.models()
        await catalog.models()
        assert calls == 1

    @pytest.mark.asyncio
    async def test_force_yeniden_ceker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        catalog = ModelCatalog()
        calls = 0

        async def fake_fetch() -> list:
            nonlocal calls
            calls += 1
            return [_parse({"id": "a/b"})]

        monkeypatch.setattr(catalog, "_fetch", fake_fetch)
        await catalog.models()
        await catalog.models(force=True)
        assert calls == 2

    @pytest.mark.asyncio
    async def test_ag_yoksa_ESKI_LISTE_verilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Boş liste vermek, kullanıcının mevcut seçimini de gizlerdi."""
        from omnivoice_engine.providers import ProviderError

        catalog = ModelCatalog()

        async def ok_fetch() -> list:
            return [_parse({"id": "a/b"})]

        monkeypatch.setattr(catalog, "_fetch", ok_fetch)
        await catalog.models()

        async def failing_fetch() -> list:
            raise ProviderError("openrouter", "ağ yok", retryable=True)

        monkeypatch.setattr(catalog, "_fetch", failing_fetch)
        models = await catalog.models(force=True)
        assert [m.id for m in models] == ["a/b"]

    @pytest.mark.asyncio
    async def test_ilk_cekim_basarisizsa_hata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Elde hiçbir şey yoksa sessizce boş dönmek yanıltıcı olurdu."""
        from omnivoice_engine.providers import ProviderError

        catalog = ModelCatalog()

        async def failing_fetch() -> list:
            raise ProviderError("openrouter", "ağ yok", retryable=True)

        monkeypatch.setattr(catalog, "_fetch", failing_fetch)
        with pytest.raises(ProviderError):
            await catalog.models()
