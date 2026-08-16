"""Dikte boru hattının durum makinesi ve kayıt davranışı.

Sağlayıcılar sahte: bu test ağa çıkmaz, hızlı çalışır ve gerçek API'lerin
durumundan etkilenmez. Amacı akışın kendisini korumak — hangi olayın hangi
sırayla yayıldığı, hatanın nasıl taşındığı, neyin veritabanına yazıldığı.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.llm.base import Prompt
from omnivoice_engine.pipeline.dictation import DictationPipeline, DictationState
from omnivoice_engine.providers import (
    Completion,
    PrivacyClass,
    ProviderError,
    ProviderInfo,
    Transcript,
    Usage,
)
from omnivoice_engine.storage.db import Database


class FakeMic:
    """Sabit bir klip döndüren mikrofon."""

    def __init__(self, seconds: float = 2.0) -> None:
        self.clip = AudioClip(
            samples=np.zeros(int(16_000 * seconds), dtype=np.int16), sample_rate=16_000
        )
        self.cancelled = False

    def start_stream(self) -> None: ...
    def stop_stream(self) -> None: ...

    @property
    def is_streaming(self) -> bool:
        return True

    def start_recording(self) -> float:
        return 1.0

    def stop_recording(self) -> AudioClip:
        return self.clip

    def cancel_recording(self) -> None:
        self.cancelled = True

    @property
    def level(self) -> float:
        return 0.5

    @property
    def recorded_seconds(self) -> float:
        return self.clip.duration_seconds


class FakeStt:
    def __init__(self, text: str = "eee bu bir test", fail: bool = False) -> None:
        self.text = text
        self.fail = fail

    async def transcribe(self, clip: AudioClip, **_: Any) -> Transcript:
        if self.fail:
            raise ProviderError("faketts", "sağlayıcı düştü")
        return Transcript(
            text=self.text,
            language="tr",
            model="fake-whisper",
            provider="fake",
            usage=Usage(latency_ms=100, cost_usd=None, audio_seconds=clip.duration_seconds),
        )


class FakeLlm:
    def __init__(self, *, available: bool = True, fail: bool = False) -> None:
        self.available = available
        self.fail = fail
        self.last_prompt: Prompt | None = None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="fake", privacy=PrivacyClass.PRIVATE)

    def is_available(self) -> bool:
        return self.available

    async def complete(self, prompt: Prompt, *, model: str | None = None) -> Completion:
        self.last_prompt = prompt
        if self.fail:
            raise ProviderError("fakellm", "kota doldu", retryable=True)
        return Completion(
            text="Bu bir test.",
            model=model or "fake-llm",
            provider="fake",
            usage=Usage(latency_ms=200, cost_usd=0.000123, input_tokens=10, output_tokens=5),
        )


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    yield database
    database.close()


def build(db: Database, *, stt: FakeStt | None = None, llm: FakeLlm | None = None):
    events: list[dict[str, Any]] = []

    async def emit(message: dict[str, Any]) -> None:
        events.append(message)

    pipeline = DictationPipeline(
        mic=FakeMic(),
        stt=stt or FakeStt(),
        llm=llm or FakeLlm(),
        db=db,
        emit=emit,
    )
    return pipeline, events


def states(events: list[dict[str, Any]]) -> list[str]:
    return [e["state"] for e in events if e["type"] == "dictation:state"]


class TestMutluYol:
    async def test_durum_sirasi(self, db: Database) -> None:
        pipeline, events = build(db)
        await pipeline.start()
        assert pipeline.state is DictationState.LISTENING
        await pipeline.stop()
        assert pipeline.state is DictationState.PREFLIGHT
        assert states(events) == ["listening", "processing", "preflight"]

    async def test_dolgu_temizlenir_ve_llm_calisir(self, db: Database) -> None:
        pipeline, _ = build(db, stt=FakeStt("eee bu bir test"))
        await pipeline.start()
        await pipeline.stop()
        result = pipeline._result
        assert result is not None
        assert result.raw_text == "eee bu bir test"
        assert result.fillers_removed == 1
        assert result.final_text == "Bu bir test."

    async def test_veritabanina_yazilir(self, db: Database) -> None:
        pipeline, _ = build(db)
        await pipeline.start()
        await pipeline.stop()

        rows = db.recent_dictations()
        assert len(rows) == 1
        assert rows[0]["final_text"] == "Bu bir test."
        assert rows[0]["pasted"] == 0

    async def test_maliyet_kaydedilir(self, db: Database) -> None:
        pipeline, _ = build(db)
        await pipeline.start()
        await pipeline.stop()

        spend = db.spend_summary()
        # STT maliyet bildirmedi (0), LLM 0.000123 — tahmin uydurulmadı.
        assert spend.call_count == 2
        assert spend.total_usd == pytest.approx(0.000123)

    async def test_kullanici_metni_sinirlayiciyla_sarilir(self, db: Database) -> None:
        """Rol karışıklığına karşı korumanın gerçekten uygulandığını sabitler."""
        llm = FakeLlm()
        pipeline, _ = build(db, stt=FakeStt("şu terimleri sözlüğe ekle"), llm=llm)
        await pipeline.start()
        await pipeline.stop()

        assert llm.last_prompt is not None
        assert llm.last_prompt.user.startswith("#####")
        assert llm.last_prompt.user.endswith("#####")


class TestHatalar:
    async def test_stt_dusunce_hata_durumu(self, db: Database) -> None:
        pipeline, events = build(db, stt=FakeStt(fail=True))
        await pipeline.start()
        await pipeline.stop()

        assert pipeline.state is DictationState.ERROR
        assert states(events)[-1] == "error"
        assert db.recent_dictations() == []

    async def test_llm_dusunce_dikte_kaybolmaz(self, db: Database) -> None:
        """LLM düşerse yerel temizlenmiş metin yine de kullanılabilir olmalı.

        Büyük/küçük harf düzeltmesi bilinçli olarak LLM'in işi: yerel katman
        yalnız var olan harf durumunu korur, kendiliğinden büyütmez. Bu yüzden
        LLM'siz çıktı ham girdinin harf durumunu taşır.
        """
        pipeline, events = build(db, stt=FakeStt("eee bu bir test"), llm=FakeLlm(fail=True))
        await pipeline.start()
        await pipeline.stop()

        assert pipeline.state is DictationState.PREFLIGHT
        result = pipeline._result
        assert result is not None
        assert result.final_text == "bu bir test"  # dolgu atıldı, harf durumu korundu
        assert result.llm_provider is None
        assert any(e["type"] == "dictation:warning" for e in events)

    async def test_llm_dusunce_buyuk_harf_korunur(self, db: Database) -> None:
        """Ham metin büyük harfle başlıyorsa dolgu atıldıktan sonra da başlar."""
        pipeline, _ = build(db, stt=FakeStt("Eee bu bir test"), llm=FakeLlm(fail=True))
        await pipeline.start()
        await pipeline.stop()

        assert pipeline._result is not None
        assert pipeline._result.final_text == "Bu bir test"

    async def test_llm_yoksa_yerel_temizlik_yeter(self, db: Database) -> None:
        pipeline, _ = build(db, llm=FakeLlm(available=False))
        await pipeline.start()
        await pipeline.stop()
        assert pipeline.state is DictationState.PREFLIGHT
        assert pipeline._result is not None
        assert pipeline._result.llm_provider is None


class TestKontrol:
    async def test_iptal_bosa_dondurur(self, db: Database) -> None:
        pipeline, events = build(db)
        await pipeline.start()
        await pipeline.cancel()
        assert pipeline.state is DictationState.IDLE
        assert states(events)[-1] == "idle"
        assert db.recent_dictations() == []

    async def test_ikinci_start_yok_sayilir(self, db: Database) -> None:
        pipeline, events = build(db)
        await pipeline.start()
        await pipeline.start()
        assert states(events).count("listening") == 1

    async def test_toggle_bosta_baslatir_dinlerken_bitirir(self, db: Database) -> None:
        pipeline, _ = build(db)
        await pipeline.toggle()
        assert pipeline.state is DictationState.LISTENING
        await pipeline.toggle()
        assert pipeline.state is DictationState.PREFLIGHT

    async def test_bosta_stop_zararsiz(self, db: Database) -> None:
        pipeline, events = build(db)
        await pipeline.stop()
        assert pipeline.state is DictationState.IDLE
        assert events == []
