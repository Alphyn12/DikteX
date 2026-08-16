"""Panelde gösterilen "gecikme" değerinin ne ölçtüğü.

Kullanıcı açısından gecikme, konuşmayı bitirdikten sonra beklediği süredir.
`total_ms` kaydın **başından** ölçer, yani konuşma süresini de içerir; onu
gecikme diye göstermek 12 saniyelik bir kaydı "12.174 ms gecikme" olarak
sunuyordu. Panel artık işleme süresini (STT + LLM) gösteriyor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omnivoice_engine.storage.db import Database, DictationRecord


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    yield database
    database.close()


def test_gecikme_konusma_suresini_icermez(db: Database) -> None:
    # 30 saniye konuşulmuş, işleme 2 saniye sürmüş bir dikte.
    db.add_dictation(
        DictationRecord(
            raw_text="uzun bir konuşma",
            final_text="Uzun bir konuşma.",
            audio_seconds=30.0,
            stt_ms=1200,
            llm_ms=800,
            total_ms=32_000,
        )
    )

    stats = db.today_stats()
    assert stats["avg_ms"] == pytest.approx(2000), "gecikme STT + LLM olmalı"
    assert stats["avg_total_ms"] == pytest.approx(32_000), "toplam süre ayrıca korunmalı"


def test_ortalama_birden_fazla_kayitta(db: Database) -> None:
    for stt, llm in ((1000, 500), (2000, 500)):
        db.add_dictation(
            DictationRecord(
                raw_text="x",
                final_text="x",
                stt_ms=stt,
                llm_ms=llm,
                total_ms=stt + llm + 5000,
            )
        )

    assert db.today_stats()["avg_ms"] == pytest.approx(2000)


def test_llm_atlandiginda_sadece_stt_sayilir(db: Database) -> None:
    db.add_dictation(
        DictationRecord(raw_text="x", final_text="x", stt_ms=900, llm_ms=0, total_ms=4000)
    )
    assert db.today_stats()["avg_ms"] == pytest.approx(900)
