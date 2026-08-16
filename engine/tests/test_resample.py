"""Örnekleme hızı dönüşümünün doğruluğu.

Gerekliliği canlı testte ortaya çıktı: Realtek mikrofonu WASAPI paylaşımlı
kipte 16 kHz'de açılamıyor (`Invalid sample rate [PaErrorCode -9997]`), yalnız
kendi doğal hızını kabul ediyor. Aygıtı doğal hızında açıp sesi biz indiriyoruz;
bu dönüşüm bozulursa konuşma tanıma sessizce kötüleşir — o yüzden testle
sabitleniyor.
"""

from __future__ import annotations

import numpy as np
import pytest

from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip, resample


def tone(frequency: float, seconds: float, rate: int, amplitude: int = 10_000) -> np.ndarray:
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    return (np.sin(2 * np.pi * frequency * t) * amplitude).astype(np.int16)


def dominant_frequency(samples: np.ndarray, rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(samples.astype(np.float64)))
    return float(np.fft.rfftfreq(len(samples), 1 / rate)[int(np.argmax(spectrum))])


class TestSure:
    @pytest.mark.parametrize("source_rate", [44_100, 48_000, 22_050])
    def test_sure_korunur(self, source_rate: int) -> None:
        samples = tone(440, 2.0, source_rate)
        out = resample(samples, source_rate, SAMPLE_RATE)
        assert len(out) / SAMPLE_RATE == pytest.approx(2.0, abs=0.01)

    def test_ayni_hizda_dokunulmaz(self) -> None:
        samples = tone(440, 0.5, SAMPLE_RATE)
        assert resample(samples, SAMPLE_RATE, SAMPLE_RATE) is samples

    def test_bos_dizi(self) -> None:
        assert len(resample(np.zeros(0, dtype=np.int16), 44_100, SAMPLE_RATE)) == 0


class TestSinyalKalitesi:
    @pytest.mark.parametrize("frequency", [200, 440, 1000, 3000])
    def test_frekans_korunur(self, frequency: int) -> None:
        """Konuşma bandındaki tonlar dönüşümden sonra da aynı frekansta olmalı."""
        samples = tone(frequency, 1.0, 44_100)
        out = resample(samples, 44_100, SAMPLE_RATE)
        assert dominant_frequency(out, SAMPLE_RATE) == pytest.approx(frequency, rel=0.02)

    def test_genlik_makul_kalir(self) -> None:
        samples = tone(440, 1.0, 44_100, amplitude=10_000)
        out = resample(samples, 44_100, SAMPLE_RATE)
        peak = int(np.max(np.abs(out)))
        # Süzgeç bir miktar zayıflatır ama sinyali yok etmemeli.
        assert 7_000 < peak < 12_000

    def test_nyquist_ustu_katlanmaz(self) -> None:
        """12 kHz'lik bir ton 16 kHz'e inerken sahte bir alçak frekans üretmemeli.

        Süzgeç olmasaydı 12 kHz, 16 kHz örneklemede 4 kHz'e katlanır ve
        konuşmanın üstüne cızırtı olarak binerdi.

        Ölçüm kenarları dışlıyor: FIR süzgeci dizinin ilk ve son birkaç
        milisaniyesinde geçici tepki üretir. Bu kaydın en başına denk gelir ve
        orada zaten 1 saniyelik pre-roll sessizliği vardır; konuşmayı etkilemez.
        """
        samples = tone(12_000, 1.0, 44_100)
        out = resample(samples, 44_100, SAMPLE_RATE)

        edge = SAMPLE_RATE // 20  # 50 ms
        steady = out[edge:-edge]
        assert int(np.max(np.abs(steady))) < 1_500, "süzgeç 12 kHz'i yeterince bastırmıyor"

    def test_konusma_bandinda_zayiflama_az(self) -> None:
        """Süzgeç 12 kHz'i keserken 1 kHz'lik konuşmayı da kesmemeli."""
        samples = tone(1_000, 1.0, 44_100, amplitude=10_000)
        out = resample(samples, 44_100, SAMPLE_RATE)
        edge = SAMPLE_RATE // 20
        steady = out[edge:-edge]
        assert int(np.max(np.abs(steady))) > 9_000

    def test_veri_tipi_int16(self) -> None:
        out = resample(tone(440, 0.5, 48_000), 48_000, SAMPLE_RATE)
        assert out.dtype == np.int16


class TestKlipEntegrasyonu:
    def test_indirilen_ses_konusma_sayilir(self) -> None:
        """Dönüşüm sonrası sessizlik denetimi yanlış karar vermemeli."""
        samples = tone(200, 1.5, 44_100, amplitude=9_000)
        out = resample(samples, 44_100, SAMPLE_RATE)
        clip = AudioClip(samples=out, sample_rate=SAMPLE_RATE)
        assert not clip.is_silent()
        assert clip.duration_seconds == pytest.approx(1.5, abs=0.02)
