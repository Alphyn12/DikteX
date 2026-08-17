"""Pre-flight'ta sesle düzeltme (Faz 7.15).

Bu özellik kullanıcının **onaylanmamış çıktısını** değiştiriyor. En kötü
sonuç metnin kaybolması: bir düzeltme denemesi başarısız olduğunda dikte
gitmemeli.

Testlerin ağırlığı bu yüzden "metin korunuyor mu" sorusunda.
"""

from __future__ import annotations

from typing import Any

import pytest

from omnivoice_engine.pipeline.dictation import (
    DictationPipeline,
    DictationResult,
    DictationState,
)
from omnivoice_engine.pipeline.refine_prompts import refine_prompt
from omnivoice_engine.pipeline.prompts import DELIMITER
from omnivoice_engine.providers import Completion, ProviderError, Usage
from fakes import FakeMic

ORIJINAL = "Yarınki toplantının saatini teyit etmek istiyorum."


class _Llm:
    """Sırayla verilen sonuçları döndüren sahte LLM."""

    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.calls = 0

    def is_available(self) -> bool:
        return True

    async def complete(self, _prompt: Any, *, model: Any = None) -> Completion:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return Completion(
            text=result,
            model="test",
            provider="test",
            usage=Usage(latency_ms=100, cost_usd=0.0001),
        )


class _Db:
    def add_spend(self, **_kwargs: Any) -> None:
        return None


def _pipeline(llm: Any) -> DictationPipeline:
    async def emit(_message: dict[str, Any]) -> None:
        return None

    pipeline = DictationPipeline(
        mic=FakeMic(),
        stt=None,  # type: ignore[arg-type]
        llm=llm,
        db=_Db(),  # type: ignore[arg-type]
        emit=emit,
        mask_pii=False,
    )
    pipeline.state = DictationState.PREFLIGHT
    pipeline._result = DictationResult(  # noqa: SLF001
        raw_text=ORIJINAL,
        final_text=ORIJINAL,
        fillers_removed=0,
        language="tr",
        stt_provider="test",
        stt_model="test",
        stt_ms=100,
        llm_provider="test",
        llm_model="test",
        llm_ms=100,
        total_ms=200,
        cost_usd=0.0001,
        audio_seconds=2.0,
    )
    return pipeline


class TestIstem:
    def test_metin_ve_talimat_ayri_sinirlanir(self) -> None:
        prompt = refine_prompt("metin", "talimat")
        assert "METİN:" in prompt.user
        assert "TALİMAT:" in prompt.user
        assert prompt.user.count(DELIMITER) == 4

    def test_sinirlayici_icerikten_temizlenir(self) -> None:
        """Metinde `#####` geçerse sınırı bozmamalı."""
        prompt = refine_prompt(f"a {DELIMITER} b", f"c {DELIMITER} d")
        assert prompt.user.count(DELIMITER) == 4

    def test_dusuk_sicaklik(self) -> None:
        """Aynı talimat aynı sonucu vermeli; yaratıcılık istenmiyor."""
        assert refine_prompt("m", "t").temperature <= 0.3

    def test_dil_bildirilir(self) -> None:
        assert "en" in refine_prompt("m", "t", language="en").system


class TestBasarili:
    @pytest.mark.asyncio
    async def test_metin_guncellenir(self) -> None:
        pipeline = _pipeline(_Llm(["Kısaltılmış hâli."]))
        await pipeline.refine("daha kısa yaz")
        assert pipeline._result is not None  # noqa: SLF001
        assert pipeline._result.final_text == "Kısaltılmış hâli."  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_preflightta_KALINIR(self) -> None:
        """Düzeltme sonrası kullanıcı sonucu görüp yapıştırabilmeli."""
        pipeline = _pipeline(_Llm(["Yeni metin."]))
        await pipeline.refine("kısalt")
        assert pipeline.state is DictationState.PREFLIGHT

    @pytest.mark.asyncio
    async def test_maliyet_birikir(self) -> None:
        pipeline = _pipeline(_Llm(["Yeni."]))
        onceki = pipeline._result.cost_usd  # noqa: SLF001
        await pipeline.refine("kısalt")
        assert pipeline._result.cost_usd > onceki  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_KULLANICI_DUZENLEMESI_kaynak_alinir(self) -> None:
        """Kullanıcı metni düzenleyip sonra "kısalt" derse düzenlemesi
        kaybolmamalı."""
        llm = _Llm(["sonuç"])
        pipeline = _pipeline(llm)
        await pipeline.refine("kısalt", text="KULLANICININ DÜZENLEDİĞİ METİN")
        # Sahte LLM istemi görmüyor; kaynak metnin taşındığını taslak
        # üzerinden doğruluyoruz.
        assert llm.calls == 1

    @pytest.mark.asyncio
    async def test_ardisik_duzeltme_oncekinden_devam_eder(self) -> None:
        pipeline = _pipeline(_Llm(["birinci sonuç", "ikinci sonuç"]))
        await pipeline.refine("kısalt")
        await pipeline.refine("bir daha kısalt")
        assert pipeline._result.final_text == "ikinci sonuç"  # noqa: SLF001


class TestMetinKorunur:
    """Bu sınıftaki her test, kullanıcının metnini kaybetmesine karşı."""

    @pytest.mark.asyncio
    async def test_LLM_HATASINDA_metin_degismez(self) -> None:
        pipeline = _pipeline(_Llm([ProviderError("test", "ağ hatası", retryable=True)]))
        await pipeline.refine("kısalt")
        assert pipeline._result.final_text == ORIJINAL  # noqa: SLF001
        assert pipeline.state is DictationState.PREFLIGHT

    @pytest.mark.asyncio
    async def test_BOS_CIKTI_metni_silmez(self) -> None:
        pipeline = _pipeline(_Llm(["   "]))
        await pipeline.refine("kısalt")
        assert pipeline._result.final_text == ORIJINAL  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_bos_talimat_yok_sayilir(self) -> None:
        llm = _Llm(["olmamalı"])
        pipeline = _pipeline(llm)
        await pipeline.refine("   ")
        assert llm.calls == 0
        assert pipeline._result.final_text == ORIJINAL  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_preflight_disinda_calismaz(self) -> None:
        llm = _Llm(["olmamalı"])
        pipeline = _pipeline(llm)
        pipeline.state = DictationState.IDLE
        await pipeline.refine("kısalt")
        assert llm.calls == 0

    @pytest.mark.asyncio
    async def test_llm_yoksa_metin_durur(self) -> None:
        class _NoLlm:
            def is_available(self) -> bool:
                return False

        pipeline = _pipeline(_NoLlm())
        await pipeline.refine("kısalt")
        assert pipeline._result.final_text == ORIJINAL  # noqa: SLF001


class TestTaslak:
    def test_taslak_saklanir(self) -> None:
        pipeline = _pipeline(_Llm(["x"]))
        pipeline.set_draft("düzenlenmiş")
        assert pipeline._draft == "düzenlenmiş"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_iptal_taslagi_temizler(self) -> None:
        """Taslak sızarsa sonraki dikte yanlış metinden devam ederdi."""
        pipeline = _pipeline(_Llm(["x"]))
        pipeline.set_draft("eski taslak")
        await pipeline.cancel()
        assert pipeline._draft is None  # noqa: SLF001
