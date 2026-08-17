"""Kayıt duraklatma (Faz 7.4).

Duraklatmanın tek işi var: **duraklamada geçen süre kayda girmemeli.** Telefon
konuşması transkripte karışırsa özellik zarar veriyor demektir.

İkinci kural: duraklatmak kaydı bitirmemeli. `_recording` bayrağını kapatmak
en kolay yol olurdu ama `stop()` ile ayırt edilemezdi.
"""

from __future__ import annotations

import numpy as np
import pytest

from omnivoice_engine.audio.capture import DTYPE, MicrophoneCapture


@pytest.fixture
def mic() -> MicrophoneCapture:
    capture = MicrophoneCapture(pre_roll_seconds=0.0)
    # Gerçek aygıt açmadan geri çağrımı besleyebilmek için akış hızını
    # elle sabitliyoruz.
    capture._stream_rate = 16_000  # noqa: SLF001
    return capture


def feed(mic: MicrophoneCapture, blocks: int, *, amplitude: int = 5000) -> None:
    """Ses geri çağrımını taklit eder; her blok 100 ms."""
    block = np.full(1600, amplitude, dtype=DTYPE).reshape(-1, 1)
    for _ in range(blocks):
        mic._on_block(block, 1600, None, None)  # noqa: SLF001


class TestDuraklatma:
    def test_duraklamada_ses_EKLENMEZ(self, mic: MicrophoneCapture) -> None:
        """Bu testin bozulması, telefon konuşmanızın transkripte girmesi demek."""
        mic.start_recording()
        feed(mic, 5)  # 0.5 sn
        before = mic.recorded_seconds

        assert mic.pause_recording()
        feed(mic, 20)  # duraklamada 2 sn geçti

        assert mic.recorded_seconds == pytest.approx(before)

    def test_devam_edince_yeniden_eklenir(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        feed(mic, 5)
        mic.pause_recording()
        feed(mic, 20)
        assert mic.resume_recording()
        feed(mic, 5)

        assert mic.recorded_seconds == pytest.approx(1.0, abs=0.01)

    def test_duraklatmak_kaydi_BITIRMEZ(self, mic: MicrophoneCapture) -> None:
        """`_recording = False` yapmak `stop()` ile ayırt edilemezdi."""
        mic.start_recording()
        mic.pause_recording()
        assert mic.is_recording
        assert mic.is_paused

    def test_biriken_ses_korunur(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        feed(mic, 10)
        mic.pause_recording()
        clip = mic.stop_recording()
        assert clip.duration_seconds == pytest.approx(1.0, abs=0.01)


class TestGecersizGecisler:
    def test_kayit_yokken_duraklatilmaz(self, mic: MicrophoneCapture) -> None:
        assert not mic.pause_recording()

    def test_iki_kez_duraklatilmaz(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        assert mic.pause_recording()
        assert not mic.pause_recording()

    def test_duraklatilmamis_kayit_surdurulemez(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        assert not mic.resume_recording()


class TestBayrakTemizligi:
    """Duraklama bayrağı sızarsa sonraki kayıt sessiz başlar — sinsi bir hata."""

    def test_stop_bayragi_temizler(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        mic.pause_recording()
        mic.stop_recording()
        assert not mic.is_paused

    def test_cancel_bayragi_temizler(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        mic.pause_recording()
        mic.cancel_recording()
        assert not mic.is_paused

    def test_yeni_kayit_duraklatilmamis_baslar(self, mic: MicrophoneCapture) -> None:
        mic.start_recording()
        mic.pause_recording()
        mic.cancel_recording()

        mic.start_recording()
        assert not mic.is_paused
        feed(mic, 5)
        assert mic.recorded_seconds > 0
