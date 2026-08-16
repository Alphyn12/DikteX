"""Uzun kayıt işleme: FLAC sıkıştırma ve parçalama.

Bu bir özellik değil, var olan bir hatanın düzeltmesi: 16 kHz mono WAV
dakikada ~1,9 MB tutuyor ve sağlayıcı sınırı 25 MB. Yani 14 dakikadan uzun
her kayıt **sessizce** başarısız oluyordu.
"""

from __future__ import annotations

import numpy as np
import pytest

from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip
from omnivoice_engine.audio.chunking import (
    DEFAULT_CHUNK_SECONDS,
    join_transcripts,
    split_for_upload,
)


def tone(seconds: float, amplitude: int = 8000, frequency: float = 220) -> np.ndarray:
    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    return (np.sin(2 * np.pi * frequency * t) * amplitude).astype(np.int16)


def clip_of(seconds: float) -> AudioClip:
    return AudioClip(samples=tone(seconds), sample_rate=SAMPLE_RATE)


class TestFlac:
    def test_flac_wav_dan_kucuk(self) -> None:
        clip = clip_of(5.0)
        assert len(clip.to_flac_bytes()) < len(clip.to_wav_bytes())

    def test_flac_kayipsiz(self) -> None:
        """Kayıpsız demek: geri okununca örnekler birebir aynı olmalı."""
        import io

        import soundfile as sf

        clip = clip_of(2.0)
        data, rate = sf.read(io.BytesIO(clip.to_flac_bytes()), dtype="int16")
        assert rate == SAMPLE_RATE
        assert np.array_equal(data, clip.samples)

    def test_yukleme_bicimi_flac_tercih_eder(self) -> None:
        _data, filename, mime = clip_of(1.0).to_upload_bytes()
        assert filename.endswith(".flac")
        assert mime == "audio/flac"

    def test_sinir_iki_katina_cikti(self) -> None:
        """Ölçüm: FLAC ile 25 MB'a sığan süre WAV'ın en az 1,5 katı olmalı."""
        clip = clip_of(20.0)
        wav_per_second = len(clip.to_wav_bytes()) / clip.duration_seconds
        flac_per_second = len(clip.to_flac_bytes()) / clip.duration_seconds
        assert wav_per_second / flac_per_second > 1.5


class TestParcalama:
    def test_kisa_kayit_bolunmez(self) -> None:
        chunks = split_for_upload(clip_of(60.0))
        assert len(chunks) == 1
        assert chunks[0].is_only

    def test_uzun_kayit_bolunur(self) -> None:
        chunks = split_for_upload(clip_of(90.0), chunk_seconds=30.0)
        assert len(chunks) >= 3
        assert all(c.total == len(chunks) for c in chunks)

    def test_parcalarin_toplami_kaydi_kapsar(self) -> None:
        """Hiçbir saniye kaybolmamalı — bindirme yüzünden toplam biraz fazla olur."""
        clip = clip_of(90.0)
        chunks = split_for_upload(clip, chunk_seconds=30.0)
        total = sum(c.clip.duration_seconds for c in chunks)
        assert total >= clip.duration_seconds
        assert total < clip.duration_seconds + 5  # bindirme makul kalsın

    def test_parcalar_sirali(self) -> None:
        chunks = split_for_upload(clip_of(120.0), chunk_seconds=30.0)
        starts = [c.start_seconds for c in chunks]
        assert starts == sorted(starts)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_sessiz_noktadan_bolunur(self) -> None:
        """Kesim, hedefin çevresindeki sessizliğe denk gelmeli."""
        # 30 sn ses · 1 sn sessizlik · 30 sn ses
        samples = np.concatenate(
            [tone(30.0), np.zeros(SAMPLE_RATE, dtype=np.int16), tone(30.0)]
        )
        clip = AudioClip(samples=samples, sample_rate=SAMPLE_RATE)

        chunks = split_for_upload(clip, chunk_seconds=30.0)
        assert len(chunks) >= 2
        # İkinci parçanın başlangıcı sessizlik aralığına (30–31 sn) yakın olmalı.
        assert 29.0 <= chunks[1].start_seconds <= 32.0

    def test_varsayilan_parca_suresi_sinira_sigar(self) -> None:
        """10 dakikalık FLAC parçası 25 MB sınırının çok altında kalmalı."""
        clip = clip_of(20.0)
        bytes_per_second = len(clip.to_flac_bytes()) / clip.duration_seconds
        chunk_bytes = bytes_per_second * DEFAULT_CHUNK_SECONDS
        assert chunk_bytes < 25 * 1024 * 1024


class TestMetinBirlestirme:
    def test_basit_birlestirme(self) -> None:
        assert join_transcripts(["bir iki", "üç dört"]) == "bir iki üç dört"

    def test_bindirme_tekrari_ayiklanir(self) -> None:
        """Bindirme yüzünden sınırdaki kelimeler iki parçada da geçer."""
        result = join_transcripts(
            ["toplantı saat dörtte başlıyor", "saat dörtte başlıyor ve bir saat sürecek"]
        )
        assert result == "toplantı saat dörtte başlıyor ve bir saat sürecek"

    def test_noktalama_farki_tekrari_engellemez(self) -> None:
        result = join_transcripts(["bunu yapalım.", "Bunu yapalım sonra devam"])
        assert result.count("apalım") == 1

    def test_bos_parcalar_atlanir(self) -> None:
        assert join_transcripts(["", "metin", "   "]) == "metin"

    def test_hepsi_bos(self) -> None:
        assert join_transcripts(["", "  "]) == ""

    def test_gercek_tekrar_silinmez(self) -> None:
        """Kullanıcı gerçekten aynı şeyi iki kez söylediyse korunmalı.

        Ayıklama yalnız parça SINIRINDA çalışır; metnin ortasındaki tekrara
        dokunulmaz.
        """
        result = join_transcripts(["evet evet dedim", "başka bir konu"])
        assert result == "evet evet dedim başka bir konu"
