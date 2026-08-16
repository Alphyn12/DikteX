"""Sessiz kaydın sağlayıcıya gönderilmediğini sabitler.

Bu koruma canlı testte bulunan gerçek bir hatadan doğdu: kısayola basıp hiç
konuşmadan bırakınca Whisper sessizliğe "Thank you." uydurdu ve ekrana
"Teşekkürler." yapıştı. Whisper'ın sessizlikte halüsinasyon üretmesi bilinen
bir davranıştır, bu yüzden savunma STT'ye güvenmek yerine ondan önce durur.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fakes import FakeLlm, FakeMic, FakeStt, silent_clip, speech_clip
from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip
from omnivoice_engine.pipeline.dictation import DictationPipeline, DictationState
from omnivoice_engine.storage.db import Database


def clip_from(samples: np.ndarray) -> AudioClip:
    return AudioClip(samples=samples.astype(np.int16), sample_rate=SAMPLE_RATE)


def silence(seconds: float = 3.0) -> AudioClip:
    return silent_clip(seconds)


def faint_noise(seconds: float = 3.0, amplitude: int = 60) -> AudioClip:
    """Oda uğultusu düzeyinde gürültü — konuşma değil."""
    rng = np.random.default_rng(7)
    return clip_from(rng.integers(-amplitude, amplitude, int(SAMPLE_RATE * seconds)))


def speech(seconds: float = 3.0, amplitude: int = 9000) -> AudioClip:
    """Konuşma benzeri sinyal: belirgin genlikli bir ton."""
    return speech_clip(seconds, amplitude)


class TestSessizlikTespiti:
    def test_tam_sessizlik(self) -> None:
        assert silence().is_silent()

    def test_oda_ugultusu_sessiz_sayilir(self) -> None:
        assert faint_noise().is_silent()

    def test_konusma_sessiz_sayilmaz(self) -> None:
        assert not speech().is_silent()

    def test_tek_tikirti_konusma_sayilmaz(self) -> None:
        """Kapı çarpması: tepe yüksek ama yalnız birkaç kareyi dolduruyor."""
        samples = np.zeros(SAMPLE_RATE * 3)
        samples[1000:1050] = 20000  # ~3 ms'lik yüksek darbe
        clip = clip_from(samples)
        assert clip.voiced_seconds() < 0.1
        assert clip.is_silent()

    def test_kisa_soz_konusma_sayilir(self) -> None:
        """Yarım saniyelik bir "tamam" elenmemeli."""
        clip = speech(seconds=0.5)
        assert not clip.is_silent()

    def test_bos_klip(self) -> None:
        assert clip_from(np.zeros(0)).is_silent()

    def test_sessizlik_icindeki_konusma_yakalanir(self) -> None:
        """Uzun sessizliğin ortasında kısa bir cümle — ortalama düşük olsa da konuşma."""
        samples = np.zeros(SAMPLE_RATE * 10)
        speech_part = speech(seconds=1.0).samples
        samples[SAMPLE_RATE * 4 : SAMPLE_RATE * 4 + len(speech_part)] = speech_part
        clip = clip_from(samples)
        assert clip.voiced_seconds() >= 0.9
        assert not clip.is_silent()


class TestBoruHatti:
    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        database = Database(tmp_path / "test.sqlite")
        yield database
        database.close()

    async def test_sessiz_kayit_saglayiciya_gitmez(self, db: Database) -> None:
        events: list[dict] = []

        async def emit(message: dict) -> None:
            events.append(message)

        mic = FakeMic()
        mic.clip = silence()
        stt = FakeStt()
        pipeline = DictationPipeline(mic=mic, stt=stt, llm=FakeLlm(), db=db, emit=emit)

        await pipeline.start()
        await pipeline.stop()

        # Hiçbir kayıt ve hiçbir harcama olmamalı.
        assert db.recent_dictations() == []
        assert db.spend_summary().call_count == 0

        # Ama sessizce boşa DÖNMEMELİ: kullanıcı canlı testte HUD'un sessizce
        # kaybolmasını "uygulama çöktü" diye bildirdi. Durum ayrı ve görünür.
        assert pipeline.state is DictationState.SILENT
        last = [e for e in events if e["type"] == "dictation:state"][-1]
        assert last["state"] == "silent"
        assert last["deadMicrophone"] is True  # tam sessizlik = ölü mikrofon

    async def test_kisik_ses_olu_mikrofondan_ayrilir(self, db: Database) -> None:
        """Kısık konuşma ile hiç sinyal olmaması farklı sorunlar.

        Biri "daha yüksek konuş", diğeri "başka mikrofon seç" demek.
        """
        events: list[dict] = []

        async def emit(message: dict) -> None:
            events.append(message)

        mic = FakeMic()
        # Duyulabilir ama konuşma sayılmayacak kadar kısa/zayıf bir sinyal.
        mic.clip = speech(seconds=3.0, amplitude=300)
        pipeline = DictationPipeline(mic=mic, stt=FakeStt(), llm=FakeLlm(), db=db, emit=emit)

        await pipeline.start()
        await pipeline.stop()

        last = [e for e in events if e["type"] == "dictation:state"][-1]
        assert last["state"] == "silent"
        assert last["deadMicrophone"] is False  # sinyal var, sadece yetersiz

    async def test_sessiz_sonrasi_kisayol_yeni_dikte_baslatir(self, db: Database) -> None:
        """SILENT bir çıkmaz sokak olmamalı; kısayol yine çalışmalı."""

        async def emit(_message: dict) -> None: ...

        mic = FakeMic()
        mic.clip = silence()
        pipeline = DictationPipeline(mic=mic, stt=FakeStt(), llm=FakeLlm(), db=db, emit=emit)

        await pipeline.start()
        await pipeline.stop()
        assert pipeline.state is DictationState.SILENT

        mic.clip = speech()
        await pipeline.toggle()
        assert pipeline.state is DictationState.LISTENING

    async def test_konusma_iceren_kayit_islenir(self, db: Database) -> None:
        async def emit(_message: dict) -> None: ...

        mic = FakeMic()
        mic.clip = speech()
        pipeline = DictationPipeline(mic=mic, stt=FakeStt(), llm=FakeLlm(), db=db, emit=emit)

        await pipeline.start()
        await pipeline.stop()

        assert pipeline.state is DictationState.PREFLIGHT
        assert len(db.recent_dictations()) == 1


class TestDilKorunmasi:
    """İstem, STT'nin bulduğu dili modele açıkça bildirmeli."""

    def test_dil_isteme_yazilir(self) -> None:
        from omnivoice_engine.pipeline.prompts import dictation_prompt

        prompt = dictation_prompt("Thank you.", language="English")
        assert "English" in prompt.system
        assert "ÇEVİRME" in prompt.system

    def test_dil_yoksa_istem_bozulmaz(self) -> None:
        from omnivoice_engine.pipeline.prompts import dictation_prompt

        prompt = dictation_prompt("merhaba")
        assert "BU METNİN DİLİ" not in prompt.system
