"""Panoda kalan metni yeniden yapıştırma (Faz 7.16).

En sinsi tuzak: kullanıcı HUD'daki metni düzenlemek için tıkladığında ön
plandaki pencere **bizim** penceremiz olur. Yeniden yapıştırma o an hedefi
tazelerse metin OmniVoice'un kendi penceresine gider ve kullanıcı hiçbir şey
olmadığını görür.

Bu yüzden yeniden deneme global kısayolla yapılıyor ve motor ayrıca kendi
penceresini reddediyor.
"""

from __future__ import annotations

from typing import Any

import pytest

from omnivoice_engine.output.window import WindowInfo
from omnivoice_engine.pipeline import dictation as module
from omnivoice_engine.pipeline.dictation import (
    DictationPipeline,
    DictationResult,
    DictationState,
    _is_own_window,
)
from fakes import FakeMic

METIN = "Yapıştırılamayan metin"


class TestKendiPenceremiz:
    @pytest.mark.parametrize(
        "ad", ["electron.exe", "Electron.exe", "DikteX.exe", "OmniVoice.exe"]
    )
    def test_kendi_pencerelerimiz_taninir(self, ad: str) -> None:
        assert _is_own_window(WindowInfo(handle=1, title="x", process_name=ad))

    @pytest.mark.parametrize("ad", ["Code.exe", "notepad.exe", "chrome.exe"])
    def test_baska_uygulamalar_taninmaz(self, ad: str) -> None:
        assert not _is_own_window(WindowInfo(handle=1, title="x", process_name=ad))


def _pipeline(monkeypatch: pytest.MonkeyPatch, *, focused: str) -> DictationPipeline:
    monkeypatch.setattr(
        module,
        "get_foreground_window",
        lambda: WindowInfo(handle=7, title="pencere", process_name=focused),
    )

    events: list[dict[str, Any]] = []

    async def emit(message: dict[str, Any]) -> None:
        events.append(message)

    pipeline = DictationPipeline(
        mic=FakeMic(),
        stt=None,  # type: ignore[arg-type]
        llm=None,  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
        emit=emit,
    )
    pipeline.events = events  # type: ignore[attr-defined]
    pipeline.state = DictationState.CLIPBOARD
    pipeline._result = DictationResult(  # noqa: SLF001
        raw_text=METIN,
        final_text=METIN,
        fillers_removed=0,
        language="tr",
        stt_provider="t",
        stt_model="t",
        stt_ms=1,
        llm_provider=None,
        llm_model=None,
        llm_ms=0,
        total_ms=1,
        cost_usd=0.0,
        audio_seconds=1.0,
    )
    return pipeline


class TestYenidenYapistirma:
    @pytest.mark.asyncio
    async def test_KENDI_PENCEREMIZE_yapistirmaz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """En önemli test.

        Kullanıcı metni düzenlemek için HUD'a tıkladıysa ön planda biz varız.
        Oraya yapıştırmak metni kendi penceremize göndermek olurdu ve
        kullanıcı hiçbir şey olmadığını görürdü.
        """
        pipeline = _pipeline(monkeypatch, focused="electron.exe")
        pasted: list[str] = []
        monkeypatch.setattr(
            module, "paste_text", lambda text, **_kw: pasted.append(text)
        )

        await pipeline.paste()

        assert pasted == []
        # Kullanıcı ne yapması gerektiğini öğrenmeli.
        uyarilar = [e for e in pipeline.events if e.get("type") == "dictation:warning"]  # type: ignore[attr-defined]
        assert uyarilar
        assert "tıklayın" in uyarilar[-1]["message"]

    @pytest.mark.asyncio
    async def test_baska_pencerede_yapistirir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipeline = _pipeline(monkeypatch, focused="notepad.exe")

        class _Outcome:
            method = type("M", (), {"value": "direct"})()
            reason = None
            needs_manual_paste = False

        monkeypatch.setattr(module, "paste_text", lambda _text, **_kw: _Outcome())

        class _Db:
            def mark_pasted(self, _id: int) -> None:
                return None

        pipeline._db = _Db()  # type: ignore[assignment]  # noqa: SLF001
        await pipeline.paste()
        assert pipeline.state is DictationState.IDLE

    @pytest.mark.asyncio
    async def test_duzenlenmis_metin_kullanilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipeline = _pipeline(monkeypatch, focused="notepad.exe")
        gonderilen: list[str] = []

        class _Outcome:
            method = type("M", (), {"value": "direct"})()
            reason = None
            needs_manual_paste = False

        def fake_paste(text: str, **_kw: Any) -> Any:
            gonderilen.append(text)
            return _Outcome()

        monkeypatch.setattr(module, "paste_text", fake_paste)

        class _Db:
            def mark_pasted(self, _id: int) -> None:
                return None

        pipeline._db = _Db()  # type: ignore[assignment]  # noqa: SLF001
        await pipeline.paste("KULLANICININ DÜZENLEDİĞİ HÂLİ")
        assert gonderilen == ["KULLANICININ DÜZENLEDİĞİ HÂLİ"]

    @pytest.mark.asyncio
    async def test_baska_durumda_calismaz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pipeline = _pipeline(monkeypatch, focused="notepad.exe")
        pipeline.state = DictationState.LISTENING
        pasted: list[str] = []
        monkeypatch.setattr(
            module, "paste_text", lambda text, **_kw: pasted.append(text)
        )
        await pipeline.paste()
        assert pasted == []
