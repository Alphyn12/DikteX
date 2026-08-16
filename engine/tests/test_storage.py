"""Depolama katmanı: arama, günlük sayımlar ve harcama özeti.

"Bugün" sayımı zaman dilimine duyarlıdır: kayıtlar UTC saklanır ama kullanıcı
kendi gününü sorar. İkisini düz metin olarak karşılaştırmak (eski hâli) gece
yarısı civarında yanlış sayardı — Türkiye'de yerel 01:00, UTC'de hâlâ önceki
gündür.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omnivoice_engine.storage.db import Database, DictationRecord


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    yield database
    database.close()


def kayit(text: str = "deneme", app: str = "VS Code") -> DictationRecord:
    return DictationRecord(
        raw_text=text,
        final_text=text,
        app_name=app,
        fillers_removed=2,
        audio_seconds=3.0,
        total_ms=1500,
        cost_usd=0.0001,
    )


class TestGunlukSayim:
    def test_bugunku_kayit_sayilir(self, db: Database) -> None:
        db.add_dictation(kayit())
        assert db.today_stats()["dictations"] == 1

    def test_gece_yarisindan_hemen_sonraki_kayit_bugune_sayilir(self, db: Database) -> None:
        """Yerel gün başladıktan 5 dakika sonra eklenen kayıt bugüne aittir.

        UTC tarihiyle karşılaştıran eski sürüm bunu düne sayardı.
        """
        local_midnight = datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        moment = (local_midnight + timedelta(minutes=5)).astimezone(UTC).isoformat()

        db.add_dictation(kayit())
        with db._lock:
            db._conn.execute("UPDATE dictations SET created_at = ?", (moment,))
            db._conn.commit()

        assert db.today_stats()["dictations"] == 1

    def test_dunku_kayit_sayilmaz(self, db: Database) -> None:
        db.add_dictation(kayit())
        yesterday = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        with db._lock:
            db._conn.execute("UPDATE dictations SET created_at = ?", (yesterday,))
            db._conn.commit()

        assert db.today_stats()["dictations"] == 0

    def test_farkli_uygulamalar_sayilir(self, db: Database) -> None:
        db.add_dictation(kayit(app="VS Code"))
        db.add_dictation(kayit(app="Slack"))
        db.add_dictation(kayit(app="Slack"))
        stats = db.today_stats()
        assert stats["dictations"] == 3
        assert stats["apps"] == 2
        assert stats["fillers"] == 6


class TestArama:
    def test_tam_metin_arama(self, db: Database) -> None:
        db.add_dictation(kayit("pazartesi sabahı toplantı"))
        db.add_dictation(kayit("kod incelemesi yapılacak"))

        assert len(db.search_dictations("pazartesi")) == 1
        assert len(db.search_dictations("kod")) == 1
        assert len(db.search_dictations("bulunmayan")) == 0

    def test_onek_eslesmesi(self, db: Database) -> None:
        db.add_dictation(kayit("diarization terimi"))
        assert len(db.search_dictations("diar")) == 1

    def test_bos_sorgu_son_kayitlari_verir(self, db: Database) -> None:
        db.add_dictation(kayit("bir"))
        db.add_dictation(kayit("iki"))
        assert len(db.search_dictations("")) == 2

    def test_bozuk_ifade_cokertmez(self, db: Database) -> None:
        """FTS5 özel karakterleri kullanıcı metninde geçebilir."""
        db.add_dictation(kayit("normal kayıt"))
        for query in ['"', "*", "AND OR", "((", 'a" OR "b']:
            db.search_dictations(query)  # hata yükseltmemeli

    def test_silinen_kayit_aramadan_dusar(self, db: Database) -> None:
        row_id = db.add_dictation(kayit("silinecek kayıt"))
        with db._lock:
            db._conn.execute("DELETE FROM dictations WHERE id = ?", (row_id,))
            db._conn.commit()
        assert db.search_dictations("silinecek") == []


class TestHarcama:
    def test_bildirilmeyen_maliyet_sifir_yazilir(self, db: Database) -> None:
        """Groq ücretsiz katmanda maliyet bildirmiyor; tahmin uydurulmaz."""
        db.add_spend(provider="groq", model="whisper", kind="stt", cost_usd=None, latency_ms=100)
        assert db.spend_summary().total_usd == 0.0
        assert db.spend_summary().call_count == 1

    def test_toplam_ve_gunluk(self, db: Database) -> None:
        db.add_spend(provider="a", model="m", kind="llm", cost_usd=0.001, latency_ms=10)
        db.add_spend(provider="a", model="m", kind="llm", cost_usd=0.002, latency_ms=10)
        summary = db.spend_summary()
        assert summary.total_usd == pytest.approx(0.003)
        assert summary.today_usd == pytest.approx(0.003)
        assert summary.call_count == 2

    def test_gecmis_aydaki_harcama_bu_aya_sayilmaz(self, db: Database) -> None:
        db.add_spend(provider="a", model="m", kind="llm", cost_usd=5.0, latency_ms=10)
        old = (datetime.now(UTC) - timedelta(days=70)).isoformat()
        with db._lock:
            db._conn.execute("UPDATE spend SET created_at = ?", (old,))
            db._conn.commit()

        summary = db.spend_summary()
        assert summary.month_usd == 0.0
        assert summary.total_usd == pytest.approx(5.0)


class TestYapistirmaIsareti:
    def test_yapistirilan_kayit_isaretlenir(self, db: Database) -> None:
        row_id = db.add_dictation(kayit())
        assert db.recent_dictations()[0]["pasted"] == 0
        db.mark_pasted(row_id)
        assert db.recent_dictations()[0]["pasted"] == 1
