"""Geçmiş araması ve şema göçü (Faz 6.2).

İki şey sınanıyor:

1. **Türkçe arama gerçekten çalışıyor mu.** FTS5'in `remove_diacritics 2`
   ayarı ö/ü/ç/ş/ğ'yi katlıyor ama **ı** ayrı bir harf; Unicode onu i'ye
   katlamıyor. Ölçtük: "veritabanı" kayıtlıyken "veritabani" araması 0 sonuç
   veriyordu ve Türkçe klavyesi olmayan biri tam da öyle yazar.

2. **Var olan veritabanı göçte bozulmuyor mu.** Kullanıcının geçmişi burada;
   başarısız bir göç veri kaybı demek.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from omnivoice_engine.storage.db import (
    Database,
    DictationRecord,
    build_fts_query,
    search_fold,
)


def kaydet(db: Database, metin: str, *, app: str = "Test", mode: str = "quick") -> int:
    return db.add_dictation(
        DictationRecord(
            raw_text=metin,
            final_text=metin,
            mode=mode,
            app_name=app,
            window_title=None,
            language="tr",
            stt_provider="test",
            stt_model="test",
            llm_provider=None,
            llm_model=None,
            audio_seconds=1.0,
            fillers_removed=0,
            stt_ms=1,
            llm_ms=0,
            total_ms=1,
            cost_usd=0.0,
        )
    )


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    kaydet(database, "PostgreSQL veritabanı migration'ı yaptık")
    kaydet(database, "Sözlük kelimesini aradım ve buldum")
    kaydet(database, "Toplantıda şirket stratejisi konuşuldu")
    kaydet(database, "Docker container ayarlarını değiştirdim", app="Terminal")
    yield database
    database.close()


class TestKatlama:
    def test_noktasiz_i_katlanir(self) -> None:
        assert search_fold("veritabanı") == "veritabani"

    def test_buyuk_I_katlanir(self) -> None:
        """Türkçe İ küçültülünce i + birleşen nokta veriyor."""
        assert search_fold("VERİTABANI") == "veritabani"

    def test_aksanlar_TOKENIZER_A_birakiliyor(self) -> None:
        """ö/ü/ç/ş/ğ'yi FTS5 kendisi katlıyor; burada dokunulmuyor."""
        assert search_fold("sözlük") == "sözlük"


class TestArama:
    @pytest.mark.parametrize(
        "sorgu",
        ["veritabanı", "veritabani", "VERİTABANI", "Veritabani"],
    )
    def test_noktasiz_i_HER_IKI_YONDE(self, db: Database, sorgu: str) -> None:
        """En kritik test — bu olmadan arama Türkçe metinde yarım çalışıyordu."""
        assert len(db.search_dictations(sorgu)) == 1

    @pytest.mark.parametrize("sorgu", ["sözlük", "sozluk", "SÖZLÜK"])
    def test_aksanli_harfler(self, db: Database, sorgu: str) -> None:
        assert len(db.search_dictations(sorgu)) == 1

    @pytest.mark.parametrize("sorgu", ["şirket", "sirket", "ŞİRKET"])
    def test_s_harfi(self, db: Database, sorgu: str) -> None:
        assert len(db.search_dictations(sorgu)) == 1

    def test_ingilizce_terim(self, db: Database) -> None:
        assert len(db.search_dictations("docker")) == 1
        assert len(db.search_dictations("Docker")) == 1

    def test_onek_eslesmesi(self, db: Database) -> None:
        assert len(db.search_dictations("söz")) == 1

    def test_eslesmeyen_sorgu(self, db: Database) -> None:
        assert db.search_dictations("kesinlikle-olmayan-bir-kelime") == []

    def test_bos_sorgu_son_kayitlar(self, db: Database) -> None:
        assert len(db.search_dictations("")) == 4

    def test_bozuk_ifade_cokertmez(self, db: Database) -> None:
        """FTS5 sözdizimi karakterleri kullanıcı metninde olabilir."""
        for sorgu in ['"', "*", "AND OR NOT", "((("]:
            db.search_dictations(sorgu)  # istisna yükseltmemeli


class TestGoc:
    def test_v1_veritabani_bozulmadan_acilir(self, tmp_path: Path) -> None:
        """Kullanıcının mevcut geçmişi burada; göç veri kaybetmemeli."""
        path = tmp_path / "eski.db"

        # v1 şemasını elle kuruyoruz: `folded` sütunu ve FTS sütunu yok.
        conn = sqlite3.connect(str(path))
        conn.executescript(
            """
            CREATE TABLE dictations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                final_text TEXT NOT NULL,
                mode TEXT NOT NULL,
                app_name TEXT,
                window_title TEXT,
                language TEXT,
                stt_provider TEXT,
                stt_model TEXT,
                llm_provider TEXT,
                llm_model TEXT,
                audio_seconds REAL NOT NULL DEFAULT 0,
                fillers_removed INTEGER NOT NULL DEFAULT 0,
                stt_ms INTEGER NOT NULL DEFAULT 0,
                llm_ms INTEGER NOT NULL DEFAULT 0,
                total_ms INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0,
                pasted INTEGER NOT NULL DEFAULT 0
            );
            CREATE VIRTUAL TABLE dictations_fts USING fts5 (
                raw_text, final_text, app_name,
                content='dictations', content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            );
            INSERT INTO dictations (created_at, raw_text, final_text, mode, app_name)
            VALUES ('2026-08-01T10:00:00+00:00',
                    'Eski kayıt veritabanı hakkında',
                    'Eski kayıt veritabanı hakkında', 'quick', 'Test');
            """
        )
        conn.commit()
        conn.close()

        # Yeni kodla açıyoruz — göç burada çalışmalı.
        db = Database(path)
        try:
            assert len(db.recent_dictations()) == 1, "eski kayıt kaybolmuş"
            # Göç eski kaydı yeniden dizinlemiş olmalı.
            assert len(db.search_dictations("veritabani")) == 1
            assert len(db.search_dictations("veritabanı")) == 1

            # Yeni kayıt da eklenebilmeli.
            kaydet(db, "Yeni kayıt sözlük hakkında")
            assert len(db.search_dictations("sozluk")) == 1
            assert len(db.recent_dictations()) == 2
        finally:
            db.close()

    def test_goc_iki_kez_calistirilabilir(self, tmp_path: Path) -> None:
        """Motor her açılışta göç çalıştırıyor; ikinci kez zarar vermemeli."""
        path = tmp_path / "tekrar.db"
        first = Database(path)
        kaydet(first, "Kayıt veritabanı hakkında")
        first.close()

        second = Database(path)
        try:
            assert len(second.recent_dictations()) == 1
            assert len(second.search_dictations("veritabani")) == 1
        finally:
            second.close()


class TestSorguKurma:
    """Doğal dil sorgusundan FTS ifadesi (Faz 7.13).

    Öbek araması ölçüldü ve fazla katıydı:

        "docker"           → 2 sonuç
        "container docker" → 0 sonuç   (sıra değişince kayboluyor)
        "docker ayarları"  → 0 sonuç   (iki kelime de kayıtta olmasına rağmen)

    Kelime bazlı AND'e geçildi.
    """

    def test_tek_kelime(self) -> None:
        assert build_fts_query("docker") == '"docker"*'

    def test_coklu_kelime_AND(self) -> None:
        assert build_fts_query("docker container") == '"docker"* AND "container"*'

    def test_SIRA_ONEMSIZ(self, db: Database) -> None:
        """Öbek aramasında "container docker" 0 sonuç veriyordu."""
        assert len(db.search_dictations("container docker")) == 1

    def test_bitisik_olmayan_kelimeler(self, db: Database) -> None:
        """Öbek aramasında "docker ayarları" 0 sonuç veriyordu."""
        assert len(db.search_dictations("docker ayarları")) == 1

    def test_DOGAL_DIL_sorgusu(self, db: Database) -> None:
        """Sesli arama doğal cümleyle geliyor."""
        assert len(db.search_dictations("geçen hafta docker hakkında ne demiştim")) == 1

    def test_dolgu_kelimeleri_atilir(self) -> None:
        assert build_fts_query("geçen hafta docker hakkında ne demiştim") == '"docker"*'

    def test_dolgu_ESLESMESI_AKSANSIZ(self) -> None:
        """`search_fold` aksanları tokenizer'a bırakıyor ama dolgu listesi ASCII.

        Bu ayrışma yüzünden "geçen" ve "demiştim" ilk yazımda elenmiyordu ve
        doğal dil sorgusu 0 sonuç veriyordu.
        """
        assert build_fts_query("dün veritabanı hakkında ne söylemiştim") == '"veritabani"*'

    def test_hepsi_dolguysa_elde_olan_kullanilir(self) -> None:
        """Boş sorgu döndürmek, kullanıcının yazdığını tamamen yok saymak olurdu."""
        assert build_fts_query("ne demiştim") != ""

    def test_tek_harfli_kelimeler_atilir(self) -> None:
        assert build_fts_query("a docker b") == '"docker"*'

    def test_bos_sorgu(self) -> None:
        assert build_fts_query("   ") == ""
