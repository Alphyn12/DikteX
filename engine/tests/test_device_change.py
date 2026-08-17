"""Aygıt tak-çıkar davranışı (Faz 7.6).

Kritik kural: **kayıt sürerken aygıt değiştirilmez.** Kullanıcı konuşurken
mikrofonu değiştirmek kaydı ortadan böler ve söylediğinin yarısı kaybolur.

İkinci kural: tercih edilen aygıt geri geldiğinde ona dönülmeli. Kulaklığını
çıkarıp takan biri her seferinde ayarlara gitmek zorunda kalmamalı.
"""

from __future__ import annotations

from typing import Any

import pytest

from omnivoice_engine.audio.capture import AudioDeviceError
from omnivoice_engine.pipeline.dictation import DictationState
from omnivoice_engine.server import app as app_module


class _Mic:
    """Aygıt yönetimini kaydeden sahte mikrofon."""

    def __init__(self, *, device: int | None = None, resolves_to: int | None = None) -> None:
        self.device = device
        self._resolves_to = resolves_to
        self.is_streaming = True
        self.stopped = 0
        self.started = 0
        self.set_calls: list[int | None] = []
        self.fail_on: int | None = None

    def stop_stream(self) -> None:
        self.stopped += 1
        self.is_streaming = False

    def start_stream(self) -> None:
        if self.fail_on is not None and self.device == self.fail_on:
            raise AudioDeviceError("aygıt açılamadı")
        self.started += 1
        self.is_streaming = True

    def set_device(self, device: int | None) -> None:
        self.set_calls.append(device)
        self.device = device

    def resolve_device_by_name(self, _name: str) -> int | None:
        return self._resolves_to


class _Pipeline:
    def __init__(self, state: DictationState = DictationState.IDLE) -> None:
        self.state = state


class _Settings:
    def __init__(self, name: str | None) -> None:
        self.settings = type("S", (), {"microphone_name": name})()


class _Context:
    def __init__(self, mic: _Mic, *, preferred: str | None, state: DictationState) -> None:
        self.mic = mic
        self.pipeline = _Pipeline(state)
        self.user_settings = _Settings(preferred)
        self.broadcasts: list[dict[str, Any]] = []

    async def broadcast(self, message: dict[str, Any]) -> None:
        self.broadcasts.append(message)


@pytest.fixture(autouse=True)
def _quiet_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gerçek PortAudio'yu yeniden başlatmıyoruz."""
    monkeypatch.setattr(app_module, "refresh_devices", lambda: None)
    monkeypatch.setattr(app_module, "list_input_devices", lambda: [])


class TestKayitSirasinda:
    @pytest.mark.asyncio
    async def test_dikte_sirasinda_DEGISTIRILMEZ(self) -> None:
        """Konuşurken mikrofonu değiştirmek kaydı ortadan böler."""
        mic = _Mic(device=3)
        context = _Context(mic, preferred="Kulaklık", state=DictationState.LISTENING)

        result = await app_module._handle_device_change(context)  # type: ignore[arg-type]

        assert result["applied"] is False
        assert result["reason"] == "busy"
        assert mic.stopped == 0
        assert mic.set_calls == []

    @pytest.mark.asyncio
    async def test_preflight_sirasinda_da_beklenir(self) -> None:
        mic = _Mic(device=3)
        context = _Context(mic, preferred="Kulaklık", state=DictationState.PREFLIGHT)
        result = await app_module._handle_device_change(context)  # type: ignore[arg-type]
        assert result["applied"] is False


class TestTercihEdilenAygit:
    @pytest.mark.asyncio
    async def test_geri_gelen_aygita_donulur(self) -> None:
        """Kulaklığını takan biri ayarlara gitmek zorunda kalmamalı."""
        mic = _Mic(device=None, resolves_to=7)
        context = _Context(mic, preferred="Kulaklık", state=DictationState.IDLE)

        result = await app_module._handle_device_change(context)  # type: ignore[arg-type]

        assert result["applied"] is True
        assert mic.device == 7
        # Akış kapatılıp yeniden açıldı: PortAudio tazelemesi bunu gerektiriyor.
        assert mic.stopped == 1
        assert mic.started == 1

    @pytest.mark.asyncio
    async def test_aygit_hala_yoksa_varsayilana_duser(self) -> None:
        mic = _Mic(device=3, resolves_to=None)
        context = _Context(mic, preferred="Kulaklık", state=DictationState.IDLE)

        await app_module._handle_device_change(context)  # type: ignore[arg-type]
        assert mic.device is None

    @pytest.mark.asyncio
    async def test_degisiklik_yoksa_applied_false(self) -> None:
        mic = _Mic(device=7, resolves_to=7)
        context = _Context(mic, preferred="Kulaklık", state=DictationState.IDLE)

        result = await app_module._handle_device_change(context)  # type: ignore[arg-type]
        assert result["applied"] is False
        # Yayın yapılmamalı: değişmeyen bir şey için arayüzü rahatsız etmiyoruz.
        assert context.broadcasts == []

    @pytest.mark.asyncio
    async def test_tercih_yoksa_varsayilan(self) -> None:
        mic = _Mic(device=3)
        context = _Context(mic, preferred=None, state=DictationState.IDLE)
        await app_module._handle_device_change(context)  # type: ignore[arg-type]
        assert mic.device is None


class TestHataYolu:
    @pytest.mark.asyncio
    async def test_acilamayan_aygitta_MIKROFONSUZ_BIRAKILMAZ(self) -> None:
        """Hedef açılamıyorsa sistem varsayılanına düşülmeli.

        Aksi hâlde tek bir kötü aygıt kullanıcıyı mikrofonsuz bırakırdı ve
        bu ancak boş bir kayıtla fark edilirdi.
        """
        mic = _Mic(device=None, resolves_to=7)
        mic.fail_on = 7
        context = _Context(mic, preferred="Kulaklık", state=DictationState.IDLE)

        result = await app_module._handle_device_change(context)  # type: ignore[arg-type]

        assert result["applied"] is False
        assert mic.device is None
        assert mic.is_streaming
