"""Kuyruğun dikte hattına bağlanması (Faz 7.2).

Buradaki kritik ayrım: **hangi hata kuyruğa alınır**. Yanlış karar iki yönde
de zarar veriyor:

* Geçici hatayı kuyruğa almamak → kullanıcının konuşması yok olur.
* Kalıcı hatayı kuyruğa almak → asla gönderilemeyecek bir ses diskte birikir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip
from omnivoice_engine.pipeline.dictation import DictationPipeline, DictationState
from omnivoice_engine.providers import ProviderError, Transcript, Usage
from omnivoice_engine.storage.queue import ClipQueue


class _FakeStt:
    """Sırayla verilen sonuçları döndüren sahte STT."""

    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.calls = 0

    async def transcribe(self, clip: AudioClip, **_kwargs: Any) -> Transcript:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


def _transcript(text: str = "merhaba") -> Transcript:
    return Transcript(
        text=text,
        language="tr",
        model="whisper-test",
        provider="test",
        usage=Usage(latency_ms=100, cost_usd=0.0001),
    )


def _clip(seconds: float = 1.0) -> AudioClip:
    # Sessiz olmayan bir sinyal: kuyruk yolunu sınıyoruz, VAD'ı değil.
    count = int(SAMPLE_RATE * seconds)
    tone = (np.sin(np.arange(count) * 0.2) * 8000).astype(np.int16)
    return AudioClip(samples=tone, sample_rate=SAMPLE_RATE)


class TestKuyrugaAlmaKarari:
    @pytest.mark.asyncio
    async def test_gecici_hata_kuyruga_alinir(self, tmp_path: Path) -> None:
        queue = ClipQueue(tmp_path / "q")
        assert queue.add(
            audio=_clip().to_upload_bytes()[0],
            suffix=".flac",
            mode="quick",
            duration_seconds=1.0,
            error="ağ hatası",
        )
        assert len(queue.items()) == 1

    def test_kalici_hata_bayragi_ayirt_edilir(self) -> None:
        """`retryable` yanlış olursa kuyruk yanlış karar verir."""
        gecici = ProviderError("groq", "ağ hatası", retryable=True)
        kalici = ProviderError("groq", "anahtar geçersiz")
        assert gecici.retryable
        assert not kalici.retryable


class TestYenidenGonderme:
    @pytest.mark.asyncio
    async def test_basarili_gonderim_kaydi_siler(self, tmp_path: Path) -> None:
        """Gönderilen kayıt diskte kalmamalı — gizlilik borcu birikmesin."""
        queue = ClipQueue(tmp_path / "q")
        data, _, _ = _clip().to_upload_bytes()
        item = queue.add(
            audio=data, suffix=".flac", mode="quick", duration_seconds=1.0, error="ağ"
        )
        assert item is not None

        pipeline = _pipeline(tmp_path, queue, _FakeStt([_transcript()]))
        stats = await pipeline.flush_queue()

        assert stats["sent"] == 1
        assert queue.items() == []
        assert not item.audio_path.exists()

    @pytest.mark.asyncio
    async def test_gecici_hatada_kayit_kalir(self, tmp_path: Path) -> None:
        queue = ClipQueue(tmp_path / "q")
        data, _, _ = _clip().to_upload_bytes()
        queue.add(audio=data, suffix=".flac", mode="quick", duration_seconds=1.0, error="ağ")

        stt = _FakeStt([ProviderError("stt", "ağ hatası", retryable=True)])
        stats = await _pipeline(tmp_path, queue, stt).flush_queue()

        assert stats["failed"] == 1
        assert len(queue.items()) == 1

    @pytest.mark.asyncio
    async def test_kalici_hatada_kayit_dusurulur(self, tmp_path: Path) -> None:
        """Asla başarılı olmayacak bir kaydı sonsuza kadar saklamak anlamsız."""
        queue = ClipQueue(tmp_path / "q")
        data, _, _ = _clip().to_upload_bytes()
        queue.add(audio=data, suffix=".flac", mode="quick", duration_seconds=1.0, error="ağ")

        stt = _FakeStt([ProviderError("stt", "anahtar geçersiz")])
        stats = await _pipeline(tmp_path, queue, stt).flush_queue()

        assert stats["dropped"] == 1
        assert queue.items() == []

    @pytest.mark.asyncio
    async def test_ag_kapaliysa_kalanlar_denenmez(self, tmp_path: Path) -> None:
        """Ağ kapalıysa sıradaki kayıtları denemek boşuna istek üretir."""
        queue = ClipQueue(tmp_path / "q")
        data, _, _ = _clip().to_upload_bytes()
        for _ in range(3):
            queue.add(
                audio=data, suffix=".flac", mode="quick", duration_seconds=1.0, error="ağ"
            )

        stt = _FakeStt([ProviderError("stt", "ağ hatası", retryable=True)])
        await _pipeline(tmp_path, queue, stt).flush_queue()

        assert stt.calls == 1
        assert len(queue.items()) == 3

    @pytest.mark.asyncio
    async def test_sonuc_YAPISTIRILMAZ_gecmise_yazilir(self, tmp_path: Path) -> None:
        """Kullanıcı çoktan başka işe geçmiş olabilir.

        Şu an odaktaki pencereye metin göndermek yanlış yere yazmak demek ve
        geri alınamaz. Sonuç yalnız geçmişe gidiyor.
        """
        queue = ClipQueue(tmp_path / "q")
        data, _, _ = _clip().to_upload_bytes()
        queue.add(audio=data, suffix=".flac", mode="quick", duration_seconds=1.0, error="ağ")

        pipeline = _pipeline(tmp_path, queue, _FakeStt([_transcript("kurtarılan metin")]))
        await pipeline.flush_queue()

        rows = pipeline._db.recent_dictations(limit=5)
        assert any("kurtarılan metin" in str(row) for row in rows)
        # Yapıştırma yapılmadığı için durum değişmemeli.
        assert pipeline.state is DictationState.IDLE


class TestSesiGeriOkuma:
    def test_flac_yeniden_okunabilir(self) -> None:
        """Kuyruk işe yaramaz olurdu: yazdığımızı geri okuyamazsak."""
        original = _clip(0.5)
        data, _, _ = original.to_upload_bytes()
        restored = AudioClip.from_encoded_bytes(data)

        assert restored.sample_rate == original.sample_rate
        assert len(restored.samples) == len(original.samples)
        # FLAC kayıpsız: örnekler birebir aynı olmalı.
        assert np.array_equal(restored.samples, original.samples)


def _pipeline(tmp_path: Path, queue: ClipQueue, stt: Any) -> DictationPipeline:
    from omnivoice_engine.storage.db import Database

    async def emit(_message: dict[str, Any]) -> None:
        return None

    class _NoLlm:
        def is_available(self) -> bool:
            return False

    return DictationPipeline(
        mic=None,  # type: ignore[arg-type]
        stt=stt,
        llm=_NoLlm(),  # type: ignore[arg-type]
        db=Database(tmp_path / "test.db"),
        emit=emit,
        queue=queue,
    )
