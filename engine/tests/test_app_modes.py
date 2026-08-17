"""Uygulama başına varsayılan mod (Faz 7.5).

Tek kritik kural: **açık seçim ezilmemeli.** Kullanıcı Ctrl+Alt+K ile kod
modunu bilerek seçtiyse, VS Code için tanımlı bir eşleme onu değiştirmemeli.
Ezersek kullanıcı neden başka bir modda çalıştığını hiçbir yerde göremez.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from omnivoice_engine.pipeline.dictation import DictationPipeline, DictationState
from omnivoice_engine.pipeline.modes import ModeId
from omnivoice_engine.storage.settings_store import SettingsStore
from fakes import FakeMic


class _Window:
    def __init__(self, process_name: str) -> None:
        self.process_name = process_name
        self.title = "pencere"
        self.handle = 1

    @property
    def app_name(self) -> str:
        return self.process_name.removesuffix(".exe")


def _pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app_modes: dict[str, str],
    focused: str | None,
) -> DictationPipeline:
    from omnivoice_engine.pipeline import dictation as module

    monkeypatch.setattr(
        module, "get_foreground_window", lambda: _Window(focused) if focused else None
    )

    async def emit(_message: dict[str, Any]) -> None:
        return None

    return DictationPipeline(
        mic=FakeMic(),
        stt=None,  # type: ignore[arg-type]
        llm=None,  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
        emit=emit,
        app_modes=app_modes,
    )


class TestEslesme:
    @pytest.mark.asyncio
    async def test_eslesen_uygulama_modu_uygular(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipeline = _pipeline(monkeypatch, app_modes={"code": "code"}, focused="Code.exe")
        await pipeline.start(ModeId.QUICK)
        assert pipeline._session is not None
        assert pipeline._session.mode.id is ModeId.CODE
        await pipeline.cancel()

    @pytest.mark.asyncio
    async def test_ACIK_SECIM_ezilmez(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """En önemli test.

        Kullanıcı Ctrl+Alt+E ile İngilizce modunu bilerek seçti; VS Code için
        tanımlı "kod" eşlemesi bunu değiştirmemeli.
        """
        pipeline = _pipeline(monkeypatch, app_modes={"code": "code"}, focused="Code.exe")
        await pipeline.start(ModeId.TRANSLATE_EN)
        assert pipeline._session is not None
        assert pipeline._session.mode.id is ModeId.TRANSLATE_EN
        await pipeline.cancel()

    @pytest.mark.asyncio
    async def test_eslesmeyen_uygulama_degistirmez(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipeline = _pipeline(
            monkeypatch, app_modes={"code": "code"}, focused="notepad.exe"
        )
        await pipeline.start(ModeId.QUICK)
        assert pipeline._session is not None
        assert pipeline._session.mode.id is ModeId.QUICK
        await pipeline.cancel()

    @pytest.mark.asyncio
    async def test_pencere_yoksa_cokmez(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pipeline = _pipeline(monkeypatch, app_modes={"code": "code"}, focused=None)
        await pipeline.start(ModeId.QUICK)
        assert pipeline._session is not None
        assert pipeline._session.mode.id is ModeId.QUICK
        await pipeline.cancel()

    @pytest.mark.asyncio
    async def test_bilinmeyen_mod_yok_sayilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bozuk bir ayar dikteyi durdurmamalı."""
        pipeline = _pipeline(
            monkeypatch, app_modes={"code": "olmayan_mod"}, focused="Code.exe"
        )
        await pipeline.start(ModeId.QUICK)
        assert pipeline._session is not None
        assert pipeline._session.mode.id is ModeId.QUICK
        await pipeline.cancel()


class TestNormallestirme:
    def test_anahtarlar_ayni_bicime_iner(self, tmp_path: Path) -> None:
        """Ayar deposu ile eşleştirme aynı normalleştirmeyi kullanmalı.

        Ayrışırlarsa "Code.exe" yazan bir kayıt hiç eşleşmez ve kullanıcı
        sebebini bulamaz.
        """
        store = SettingsStore.load(tmp_path / "s.json")
        store.update(app_modes={"Code.exe": "code", "  Slack  ": "quick"})
        assert store.settings.app_modes == {"code": "code", "slack": "quick"}

    def test_bos_kayitlar_atlanir(self, tmp_path: Path) -> None:
        store = SettingsStore.load(tmp_path / "s.json")
        store.update(app_modes={"": "code", "x": "  "})
        assert store.settings.app_modes == {}

    def test_eslemeler_kalici(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        SettingsStore.load(path).update(app_modes={"code": "code"})
        assert SettingsStore.load(path).settings.app_modes == {"code": "code"}
