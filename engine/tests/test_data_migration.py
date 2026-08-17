"""OmniVoice → DikteX veri göçü.

Uygulama yeniden adlandırıldı ve kullanıcı verisinin yeri değişti:

    %LOCALAPPDATA%\\OmniVoice\\omnivoice.sqlite
    %LOCALAPPDATA%\\DikteX\\diktex.sqlite

Bu göç **gerçek kullanıcı verisi** taşıyor: dikte geçmişi, ayarlar,
snippet'ler, kuyruk. Yanlış giderse kaybedilen şey geri getirilemez, o yüzden
hem başarı hem de başarısızlık yolu burada sabitleniyor.

En kritik nokta WAL. SQLite'ın en son yazdıkları `-wal` yan dosyasında
bekliyor olabilir; yalnız ana dosyayı taşımak o kayıtları geride bırakır.
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest

import omnivoice_engine.storage.db as db_module


@pytest.fixture
def veri_kokü(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`%LOCALAPPDATA%` yerine geçen boş klasör."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    importlib.reload(db_module)
    return tmp_path


def _eski_veritabanı(kök: Path, *, kayıt_sayısı: int = 3) -> Path:
    """Eski adla, içinde kayıt olan bir veritabanı oluşturur."""
    eski = kök / "OmniVoice"
    eski.mkdir(exist_ok=True)
    yol = eski / "omnivoice.sqlite"
    conn = sqlite3.connect(str(yol))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE d (t TEXT)")
    conn.executemany(
        "INSERT INTO d VALUES (?)", [(f"dikte {i}",) for i in range(kayıt_sayısı)]
    )
    conn.commit()
    conn.close()
    return yol


def test_klasör_ve_dosya_yeni_ada_taşınıyor(veri_kokü: Path) -> None:
    _eski_veritabanı(veri_kokü)
    (veri_kokü / "OmniVoice" / "settings.json").write_text("{}", encoding="utf-8")

    yol = db_module.default_db_path()

    assert yol.parent.name == "DikteX"
    assert yol.name == "diktex.sqlite"
    # Eski klasör tamamen gitmeli; yarım bir göç iki ayrı veri kümesi demek.
    assert not (veri_kokü / "OmniVoice").exists()
    # Yalnız veritabanı değil, klasörün TAMAMI taşınıyor.
    assert (yol.parent / "settings.json").exists()


def test_kayıtlar_korunuyor(veri_kokü: Path) -> None:
    _eski_veritabanı(veri_kokü, kayıt_sayısı=7)

    yol = db_module.default_db_path()

    conn = sqlite3.connect(str(yol))
    try:
        assert conn.execute("SELECT count(*) FROM d").fetchone()[0] == 7
    finally:
        conn.close()


def test_wal_içinde_bekleyen_yazma_kaybolmuyor(veri_kokü: Path) -> None:
    """Göçün en kolay yanlış yapılan yeri.

    `-wal` dosyası geride bırakılırsa en son yazılan kayıtlar kaybolur ve
    bu, sessiz bir veri kaybı olur: veritabanı açılır, yalnız içi eksiktir.
    """
    yol_eski = _eski_veritabanı(veri_kokü)

    conn = sqlite3.connect(str(yol_eski))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO d VALUES ('wal icinde bekleyen')")
    conn.commit()
    # Baglantiyi kapatmadan WAL'in gerçekten dolu olduğunu doğruluyoruz.
    assert (yol_eski.parent / "omnivoice.sqlite-wal").stat().st_size > 0
    conn.close()

    yol = db_module.default_db_path()

    conn = sqlite3.connect(str(yol))
    try:
        satır = conn.execute(
            "SELECT count(*) FROM d WHERE t = 'wal icinde bekleyen'"
        ).fetchone()
        assert satır[0] == 1
    finally:
        conn.close()
    # Checkpoint sonrası yan dosyalar geride kalmamalı.
    assert not (yol.parent / "omnivoice.sqlite-wal").exists()
    assert not (yol.parent / "omnivoice.sqlite-shm").exists()


def test_taşıma_yapılamazsa_eski_veri_kullanılmaya_devam_ediyor(
    veri_kokü: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uygulamanın açık bir örneği dosyaları kilitliyorsa.

    Doğru davranış eski adla devam etmek. Yeni ada boş bir veritabanı açmak
    kullanıcıya geçmişini kaybetmiş gibi görünürdü.
    """
    _eski_veritabanı(veri_kokü, kayıt_sayısı=5)

    def kilitli(self: Path, hedef: object) -> None:
        raise PermissionError(5, "Erişim engellendi")

    monkeypatch.setattr(Path, "rename", kilitli)

    yol = db_module.default_db_path()

    assert yol.parent.name == "OmniVoice"
    assert yol.name == "omnivoice.sqlite"
    conn = sqlite3.connect(str(yol))
    try:
        assert conn.execute("SELECT count(*) FROM d").fetchone()[0] == 5
    finally:
        conn.close()


def test_göç_tekrar_çağrılınca_zarar_vermiyor(veri_kokü: Path) -> None:
    _eski_veritabanı(veri_kokü)

    birinci = db_module.default_db_path()
    ikinci = db_module.default_db_path()

    assert birinci == ikinci
    conn = sqlite3.connect(str(ikinci))
    try:
        assert conn.execute("SELECT count(*) FROM d").fetchone()[0] == 3
    finally:
        conn.close()


def test_temiz_kurulumda_doğrudan_yeni_ad_kullanılıyor(veri_kokü: Path) -> None:
    """Eski klasör yoksa göç mantığı hiç devreye girmemeli."""
    yol = db_module.default_db_path()

    assert yol.parent.name == "DikteX"
    assert yol.name == "diktex.sqlite"
    assert not (veri_kokü / "OmniVoice").exists()


def test_yeni_veritabanı_varken_eskisi_üzerine_yazılmıyor(veri_kokü: Path) -> None:
    """İkisi birden varsa yeni olan kazanır.

    Kullanıcı yeni sürümü bir süre kullandıktan sonra eski klasör bir
    yedekten geri gelirse, taze veriyi eskisiyle ezmek en kötü sonuç olurdu.
    """
    yeni_klasör = veri_kokü / "DikteX"
    yeni_klasör.mkdir()
    conn = sqlite3.connect(str(yeni_klasör / "diktex.sqlite"))
    conn.execute("CREATE TABLE d (t TEXT)")
    conn.execute("INSERT INTO d VALUES ('yeni veri')")
    conn.commit()
    conn.close()

    _eski_veritabanı(veri_kokü, kayıt_sayısı=99)

    yol = db_module.default_db_path()

    conn = sqlite3.connect(str(yol))
    try:
        assert conn.execute("SELECT t FROM d").fetchone()[0] == "yeni veri"
    finally:
        conn.close()
