"""Toplantı boru hattı: iki kanallı döküm, özet ve eylem maddeleri.

Loopback gerçek donanım gerektirdiği için sahtelenmiş; STT ve LLM de sahte.
Amaç akışın kendisini korumak: hangi kanalın kime ait olduğu, LLM düşerse
dökümün kaybolmaması ve modelin bozuk JSON'unun listeyi çökertmemesi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from fakes import FakeLlm, FakeMic, FakeStt, silent_clip, speech_clip
from omnivoice_engine.audio.capture import SAMPLE_RATE, AudioClip
from omnivoice_engine.audio.loopback import MeetingRecording
from omnivoice_engine.pipeline.meeting import (
    ActionItem,
    MeetingPipeline,
    MeetingState,
    _parse_action_items,
)
from omnivoice_engine.pipeline.meeting_prompts import label_channels
from omnivoice_engine.storage.db import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    yield database
    database.close()


class FakeRecorder:
    """Loopback yerine hazır bir kayıt döndürür."""

    def __init__(self, system_clip: AudioClip | None = None) -> None:
        self.system_clip = system_clip
        self._recording = False
        self.started_with: str | None = None

    def start(self, device_name: str | None = None) -> None:
        self._recording = True
        self.started_with = device_name

    def stop(self, microphone_clip: AudioClip | None = None) -> MeetingRecording:
        self._recording = False
        return MeetingRecording(
            microphone=microphone_clip,
            system=self.system_clip,
            duration_seconds=12.0,
        )

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        return 12.0

    @property
    def system_level(self) -> float:
        return 0.3


def build(
    db: Database,
    *,
    mic_clip: AudioClip | None = None,
    system_clip: AudioClip | None = None,
    stt: FakeStt | None = None,
    llm: FakeLlm | None = None,
):
    events: list[dict[str, Any]] = []

    async def emit(message: dict[str, Any]) -> None:
        events.append(message)

    mic = FakeMic(mic_clip if mic_clip is not None else speech_clip())
    pipeline = MeetingPipeline(
        mic=mic,
        stt=stt or FakeStt("bu bir toplantı"),
        llm=llm or FakeLlm(reply="## Özet\nToplantı yapıldı."),
        db=db,
        emit=emit,
    )
    pipeline._recorder = FakeRecorder(system_clip)  # noqa: SLF001
    return pipeline, events


def states(events: list[dict[str, Any]]) -> list[str]:
    return [e["state"] for e in events if e["type"] == "meeting:state"]


class TestAkis:
    async def test_durum_sirasi(self, db: Database) -> None:
        pipeline, events = build(db, system_clip=speech_clip())
        await pipeline.start()
        assert pipeline.state is MeetingState.RECORDING
        await pipeline.stop()
        assert pipeline.state is MeetingState.DONE
        assert states(events) == ["recording", "transcribing", "summarizing", "done"]

    async def test_iki_kanal_da_cevrilir(self, db: Database) -> None:
        stt = FakeStt("konuşma")
        pipeline, _ = build(db, system_clip=speech_clip(), stt=stt)
        await pipeline.start()
        await pipeline.stop()

        assert stt.calls == 2, "mikrofon ve sistem sesi ayrı ayrı çevrilmeli"
        result = pipeline.get_result()
        assert result is not None
        assert result.had_microphone
        assert result.had_system_audio

    async def test_sadece_mikrofon_varsa_tek_kanal(self, db: Database) -> None:
        stt = FakeStt("yalnız ben")
        pipeline, _ = build(db, system_clip=silent_clip(), stt=stt)
        await pipeline.start()
        await pipeline.stop()

        assert stt.calls == 1
        result = pipeline.get_result()
        assert result is not None
        assert result.had_microphone
        assert not result.had_system_audio

    async def test_hic_ses_yoksa_hata(self, db: Database) -> None:
        pipeline, events = build(db, mic_clip=silent_clip(), system_clip=silent_clip())
        await pipeline.start()
        await pipeline.stop()

        assert pipeline.state is MeetingState.ERROR
        assert states(events)[-1] == "error"

    async def test_veritabanina_yazilir(self, db: Database) -> None:
        pipeline, _ = build(db, system_clip=speech_clip())
        await pipeline.start()
        await pipeline.stop()

        meetings = db.recent_meetings()
        assert len(meetings) == 1
        assert meetings[0]["duration_seconds"] == pytest.approx(12.0)
        assert isinstance(meetings[0]["action_items"], list)

    async def test_iptal_kayit_birakmaz(self, db: Database) -> None:
        pipeline, _ = build(db, system_clip=speech_clip())
        await pipeline.start()
        await pipeline.cancel()
        assert pipeline.state is MeetingState.IDLE
        assert db.recent_meetings() == []


class TestKanalEtiketleme:
    def test_iki_kanal_etiketlenir(self) -> None:
        combined = label_channels("benim sözüm", "onların sözü")
        assert "[BEN]" in combined
        assert "[DİĞER KATILIMCILAR]" in combined
        assert combined.index("[BEN]") < combined.index("[DİĞER KATILIMCILAR]")

    def test_bos_kanal_etiketlenmez(self) -> None:
        assert "[DİĞER KATILIMCILAR]" not in label_channels("sadece ben", "")
        assert "[BEN]" not in label_channels("", "sadece onlar")

    def test_ikisi_de_bossa_bos_doner(self) -> None:
        assert label_channels("", "   ") == ""


class TestLlmDayaniklilik:
    async def test_llm_dusunce_dokum_kaybolmaz(self, db: Database) -> None:
        """Özet üretilemese bile ham döküm korunmalı."""
        pipeline, _ = build(db, system_clip=speech_clip(), llm=FakeLlm(fail=True))
        await pipeline.start()
        await pipeline.stop()

        assert pipeline.state is MeetingState.DONE
        result = pipeline.get_result()
        assert result is not None
        assert result.transcript.strip()
        assert result.summary == ""

    async def test_llm_yoksa_dokum_yine_uretilir(self, db: Database) -> None:
        pipeline, _ = build(db, system_clip=speech_clip(), llm=FakeLlm(available=False))
        await pipeline.start()
        await pipeline.stop()
        assert pipeline.state is MeetingState.DONE
        assert pipeline.get_result() is not None


class TestEylemMaddesiAyristirma:
    """Model JSON kurallarına her zaman uymaz; liste bundan çökmemeli."""

    def test_duz_json(self) -> None:
        items = _parse_action_items('[{"task":"raporu gönder","owner":"Ali","due":"çar"}]')
        assert items == [ActionItem(task="raporu gönder", owner="Ali", due="çar")]

    def test_kod_blogu_sarmali_soyulur(self) -> None:
        items = _parse_action_items('```json\n[{"task":"testi yaz"}]\n```')
        assert [i.task for i in items] == ["testi yaz"]

    def test_metin_arasindaki_json_bulunur(self) -> None:
        raw = 'İşte liste:\n[{"task":"a"},{"task":"b"}]\nUmarım yardımcı olur.'
        assert [i.task for i in _parse_action_items(raw)] == ["a", "b"]

    def test_bos_dizi(self) -> None:
        assert _parse_action_items("[]") == []

    def test_bozuk_cikti_bos_liste(self) -> None:
        """Uydurma bir görev listesi göstermek, hiç göstermemekten kötüdür."""
        assert _parse_action_items("bugün toplantıda şunlar konuşuldu") == []
        assert _parse_action_items("[{bozuk json") == []

    def test_gorevsiz_madde_atlanir(self) -> None:
        assert _parse_action_items('[{"owner":"Ali","due":"çar"}]') == []

    def test_null_alanlar_none_olur(self) -> None:
        items = _parse_action_items('[{"task":"iş","owner":null,"due":null}]')
        assert items[0].owner is None
        assert items[0].due is None


class TestKarisim:
    def test_iki_kanal_karisir(self) -> None:
        mic = speech_clip(seconds=2.0)
        system = speech_clip(seconds=2.0)
        recording = MeetingRecording(microphone=mic, system=system, duration_seconds=2.0)
        mixed = recording.mixed()
        assert mixed.sample_rate == SAMPLE_RATE
        # Ortalama alındığı için kırpma olmamalı.
        assert int(np.max(np.abs(mixed.samples))) <= 32767

    def test_tek_kanal_oldugu_gibi_doner(self) -> None:
        mic = speech_clip(seconds=1.0)
        recording = MeetingRecording(microphone=mic, system=None, duration_seconds=1.0)
        assert recording.mixed() is mic

    def test_farkli_uzunluklar(self) -> None:
        recording = MeetingRecording(
            microphone=speech_clip(seconds=1.0),
            system=speech_clip(seconds=3.0),
            duration_seconds=3.0,
        )
        assert recording.mixed().duration_seconds == pytest.approx(3.0, abs=0.05)
