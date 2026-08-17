"""Yerel SQLite veritabanı — dikte geçmişi, arama ve harcama takibi.

Properties VI.3 (Prompt Geçmişi) ve Faz 2.12 (Maliyet Takibi).

Veriler kullanıcının makinesinde kalır; hiçbir yere gönderilmez. Tam metin
arama için FTS5 kullanılır — SQLite ile birlikte gelir, ek bağımlılık yok.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

#: Türkçe'ye özgü, Unicode'un katlamadığı harf çiftleri.
#:
#: FTS5'in `remove_diacritics 2` ayarı ö→o, ü→u, ç→c, ş→s, ğ→g yapıyor —
#: bunlar aksanlı harfler. Ama **ı** (U+0131) aksanlı bir i değil, ayrı bir
#: harf; Unicode onu i'ye katlamaz. Aynı şekilde **İ** (U+0130) küçültülünce
#: i + birleşen nokta veriyor.
#:
#: Ölçtük: "veritabanı" kayıtlıyken "veritabani" araması 0 sonuç veriyordu.
#: Türkçe klavyesi olmayan biri tam da öyle yazar.
_FOLD_MAP = str.maketrans({"ı": "i", "İ": "i", "̇": ""})


def search_fold(text: str) -> str:
    """Aramada kullanılan katlanmış biçim.

    Yalnız FTS5'in kendi başına yapamadığını yapıyor; aksan temizliğini
    tokenizer'a bırakıyoruz.
    """
    return text.lower().translate(_FOLD_MAP)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
    id              INTEGER PRIMARY KEY,
    created_at      TEXT    NOT NULL,
    raw_text        TEXT    NOT NULL,
    final_text      TEXT    NOT NULL,
    mode            TEXT    NOT NULL DEFAULT 'quick',
    app_name        TEXT,
    window_title    TEXT,
    language        TEXT,
    stt_provider    TEXT,
    stt_model       TEXT,
    llm_provider    TEXT,
    llm_model       TEXT,
    audio_seconds   REAL    NOT NULL DEFAULT 0,
    fillers_removed INTEGER NOT NULL DEFAULT 0,
    stt_ms          INTEGER NOT NULL DEFAULT 0,
    llm_ms          INTEGER NOT NULL DEFAULT 0,
    total_ms        INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL    NOT NULL DEFAULT 0,
    pasted          INTEGER NOT NULL DEFAULT 0,
    -- Aramada kullanılan katlanmış metin (bkz. `search_fold`).
    --
    -- FTS5'in `remove_diacritics 2` ayarı ö→o, ü→u, ş→s yapıyor ama Türkçe
    -- **ı** ayrı bir harf, aksanlı bir i değil — Unicode onu katlamıyor.
    -- Ölçtük: "veritabanı" kayıtlıyken "veritabani" araması 0 sonuç
    -- veriyordu. Türkçe klavyesi olmayan biri tam da öyle yazar.
    folded          TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_dictations_created
    ON dictations (created_at DESC);

-- Tam metin arama. `content=` ile asıl tabloya bağlanır, metin iki kez
-- saklanmaz.
CREATE VIRTUAL TABLE IF NOT EXISTS dictations_fts USING fts5 (
    raw_text,
    final_text,
    app_name,
    folded,
    content='dictations',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS dictations_ai AFTER INSERT ON dictations BEGIN
    INSERT INTO dictations_fts (rowid, raw_text, final_text, app_name, folded)
    VALUES (new.id, new.raw_text, new.final_text, new.app_name, new.folded);
END;

CREATE TRIGGER IF NOT EXISTS dictations_ad AFTER DELETE ON dictations BEGIN
    INSERT INTO dictations_fts (dictations_fts, rowid, raw_text, final_text, app_name, folded)
    VALUES ('delete', old.id, old.raw_text, old.final_text, old.app_name, old.folded);
END;

CREATE TRIGGER IF NOT EXISTS dictations_au AFTER UPDATE ON dictations BEGIN
    INSERT INTO dictations_fts (dictations_fts, rowid, raw_text, final_text, app_name, folded)
    VALUES ('delete', old.id, old.raw_text, old.final_text, old.app_name, old.folded);
    INSERT INTO dictations_fts (rowid, raw_text, final_text, app_name, folded)
    VALUES (new.id, new.raw_text, new.final_text, new.app_name, new.folded);
END;

-- Sağlayıcı çağrısı başına harcama. Dikte kaydı silinse de maliyet geçmişi
-- kalır; aylık toplam bundan hesaplanır.
CREATE TABLE IF NOT EXISTS spend (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT    NOT NULL,
    provider     TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    kind         TEXT    NOT NULL,
    cost_usd     REAL    NOT NULL,
    latency_ms   INTEGER NOT NULL DEFAULT 0,
    meta         TEXT
);

CREATE INDEX IF NOT EXISTS idx_spend_created ON spend (created_at DESC);

-- Toplantı kayıtları (Faz 4). Döküm, özet ve eylem maddeleri.
CREATE TABLE IF NOT EXISTS meetings (
    id               INTEGER PRIMARY KEY,
    created_at       TEXT    NOT NULL,
    transcript       TEXT    NOT NULL,
    summary          TEXT    NOT NULL DEFAULT '',
    -- Eylem maddeleri JSON dizisi olarak; sayıları değişken ve sorgu
    -- gerektirmiyorlar, ayrı tablo fazla olurdu.
    action_items     TEXT    NOT NULL DEFAULT '[]',
    duration_seconds REAL    NOT NULL DEFAULT 0,
    language         TEXT,
    cost_usd         REAL    NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_meetings_created ON meetings (created_at DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class DictationRecord:
    """Kaydedilecek bir dikte."""

    raw_text: str
    final_text: str
    mode: str = "quick"
    app_name: str | None = None
    window_title: str | None = None
    language: str | None = None
    stt_provider: str | None = None
    stt_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    audio_seconds: float = 0.0
    fillers_removed: int = 0
    stt_ms: int = 0
    llm_ms: int = 0
    total_ms: int = 0
    cost_usd: float = 0.0
    pasted: bool = False


@dataclass(frozen=True, slots=True)
class SpendSummary:
    """Harcama özeti — panelde ve bütçe freninde kullanılır."""

    today_usd: float
    month_usd: float
    total_usd: float
    call_count: int


def default_db_path() -> Path:
    """Veritabanının yeri: `%LOCALAPPDATA%\\OmniVoice\\omnivoice.sqlite`."""
    import os

    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    directory = Path(base) / "OmniVoice"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "omnivoice.sqlite"


class Database:
    """SQLite sarmalayıcı.

    Bağlantı tek ve kilitli: motor tek süreçtir, eşzamanlı yazma beklenmiyor;
    kilit, ses geri çağrımı gibi farklı iş parçacıklarından gelen yazmaları
    güvene alır.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL, okuma sırasında yazmayı engellemez — arayüz geçmişi tararken
        # yeni bir dikte kaydedilebilsin diye.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            upgraded = self._upgrade_to_v2()
            self._conn.executescript(_SCHEMA)

            if upgraded:
                # FTS tablosu şema betiğiyle YENİ kuruldu ve boş. İçeriği
                # asıl tablodan yeniden üretmek zorundayız; yoksa göçten
                # sonra eski kayıtlar aranamaz hâle gelir.
                #
                # Bu satır bir testle korunuyor: ilk yazımda unutulmuştu ve
                # göç, kullanıcının tüm geçmişini aramanın dışında bırakıyordu.
                self._conn.execute(
                    "INSERT INTO dictations_fts (dictations_fts) VALUES ('rebuild')"
                )
                log.info("Arama dizini yeniden üretildi")

            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()
        log.info("Veritabanı hazır: %s", self.path)

    def _upgrade_to_v2(self) -> bool:
        """v1 → v2: aramaya katlanmış metin sütunu ekler.

        Yükseltme yapıldıysa `True` döner; çağıran taraf FTS dizinini yeniden
        üretmek zorunda.

        Şema betiği `IF NOT EXISTS` kullandığı için var olan tabloları
        değiştirmiyor; sütun ve FTS tablosu burada elle yükseltiliyor.

        Yükseltme **sessizce atlanmıyor**: başarısız olursa arama yalnız
        Türkçe ı/i durumunda eksik çalışır, uygulama çalışmaya devam eder.
        """
        try:
            tables = {
                row["name"]
                for row in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                )
            }
            if "dictations" not in tables:
                return False  # Yeni veritabanı; şema betiği doğrusunu kuracak.

            columns = {
                row["name"] for row in self._conn.execute("PRAGMA table_info(dictations)")
            }
            if "folded" in columns:
                return False  # Zaten yükseltilmiş.

            log.info("Veritabanı v2'ye yükseltiliyor (arama katlaması)")
            self._conn.execute(
                "ALTER TABLE dictations ADD COLUMN folded TEXT NOT NULL DEFAULT ''"
            )

            # Eski kayıtları doldur. Tetikleyiciler FTS'i güncelleyecek, ama
            # FTS tablosu eski sütun düzeninde olduğu için önce onu atıyoruz.
            self._conn.execute("DROP TRIGGER IF EXISTS dictations_ai")
            self._conn.execute("DROP TRIGGER IF EXISTS dictations_ad")
            self._conn.execute("DROP TRIGGER IF EXISTS dictations_au")
            self._conn.execute("DROP TABLE IF EXISTS dictations_fts")

            rows = self._conn.execute(
                "SELECT id, raw_text, final_text, app_name FROM dictations"
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    "UPDATE dictations SET folded = ? WHERE id = ?",
                    (
                        search_fold(
                            f"{row['raw_text']} {row['final_text']} {row['app_name'] or ''}"
                        ),
                        row["id"],
                    ),
                )
            self._conn.commit()
            log.info("Yükseltme tamam: %d kayıt katlandı", len(rows))
            return True
        except sqlite3.Error:
            log.warning("Veritabanı yükseltmesi başarısız", exc_info=True)
            return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Dikte ─────────────────────────────────────────────────────────────

    def add_dictation(self, record: DictationRecord) -> int:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO dictations (
                    created_at, raw_text, final_text, mode, app_name, window_title,
                    language, stt_provider, stt_model, llm_provider, llm_model,
                    audio_seconds, fillers_removed, stt_ms, llm_ms, total_ms,
                    cost_usd, pasted, folded
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    now,
                    record.raw_text,
                    record.final_text,
                    record.mode,
                    record.app_name,
                    record.window_title,
                    record.language,
                    record.stt_provider,
                    record.stt_model,
                    record.llm_provider,
                    record.llm_model,
                    record.audio_seconds,
                    record.fillers_removed,
                    record.stt_ms,
                    record.llm_ms,
                    record.total_ms,
                    record.cost_usd,
                    int(record.pasted),
                    search_fold(
                        f"{record.raw_text} {record.final_text} {record.app_name or ''}"
                    ),
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid or 0)

    def mark_pasted(self, dictation_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE dictations SET pasted = 1 WHERE id = ?", (dictation_id,)
            )
            self._conn.commit()

    def recent_dictations(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dictations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_dictation(self, record_id: int) -> dict[str, Any] | None:
        """Tek bir kaydı kimliğine göre getirir."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM dictations WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def search_dictations(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Tam metin arama. Boş sorgu son kayıtları döndürür."""
        if not query.strip():
            return self.recent_dictations(limit)

        # FTS5 sorgu sözdizimindeki özel karakterler kullanıcı metninde
        # olabilir; tırnak içine alıp önek eşleşmesi ekliyoruz.
        # Sorgu da katlanıyor: dizin katlanmış metni taşıyor, sorgu
        # taşımazsa "veritabani" araması "veritabanı" kaydını bulamaz.
        escaped = search_fold(query).replace('"', '""')
        fts_query = f'"{escaped}"*'

        with self._lock:
            try:
                rows = self._conn.execute(
                    """
                    SELECT d.* FROM dictations_fts f
                    JOIN dictations d ON d.id = f.rowid
                    WHERE dictations_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # Bozuk FTS ifadesi aramayı çökertmesin.
                log.warning("Arama ifadesi çözümlenemedi: %r", query)
                return []
        return [dict(row) for row in rows]

    @staticmethod
    def _local_day_bounds() -> tuple[str, str]:
        """Kullanıcının bugününün UTC karşılığı.

        Kayıtlar UTC olarak saklanır (sıralama için doğrusu bu), ama "bugün"
        kullanıcının yerel günüdür. İkisini doğrudan karşılaştırmak, saat
        farkı yüzünden gece yarısı civarında yanlış sayım verirdi: Türkiye'de
        yerel 01:00, UTC'de hâlâ bir önceki gün.
        """
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()

    def today_stats(self) -> dict[str, Any]:
        """Panelin "Bugün" başlığı için sayılar."""
        start, end = self._local_day_bounds()
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    COUNT(*)                          AS dictations,
                    COUNT(DISTINCT app_name)          AS apps,
                    COALESCE(SUM(fillers_removed), 0) AS fillers,
                    COALESCE(SUM(audio_seconds), 0)   AS audio_seconds,
                    -- "Gecikme" kullanıcı için konuşmayı bitirdikten sonra
                    -- beklediği süredir. `total_ms` kaydın başından ölçtüğü
                    -- için konuşma süresini de içerir ve gecikmeyi olduğundan
                    -- kat kat yüksek gösterirdi.
                    COALESCE(AVG(stt_ms + llm_ms), 0)  AS avg_ms,
                    COALESCE(AVG(total_ms), 0)         AS avg_total_ms
                FROM dictations
                WHERE created_at >= ? AND created_at < ?
                """,
                (start, end),
            ).fetchone()
        return dict(row) if row else {}

    # ── Toplantı ──────────────────────────────────────────────────────────

    def add_meeting(
        self,
        *,
        transcript: str,
        summary: str,
        action_items: list[dict[str, Any]],
        duration_seconds: float,
        language: str | None,
        cost_usd: float,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO meetings (created_at, transcript, summary, action_items, "
                "duration_seconds, language, cost_usd) VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now(UTC).isoformat(),
                    transcript,
                    summary,
                    json.dumps(action_items, ensure_ascii=False),
                    duration_seconds,
                    language,
                    cost_usd,
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid or 0)

    def recent_meetings(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM meetings ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

        meetings: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            # Eylem maddeleri JSON olarak saklanıyor; arayüze çözülmüş gitmeli.
            try:
                item["action_items"] = json.loads(item["action_items"])
            except (json.JSONDecodeError, TypeError):
                item["action_items"] = []
            meetings.append(item)
        return meetings

    def meeting_count_today(self) -> int:
        start, end = self._local_day_bounds()
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM meetings WHERE created_at >= ? AND created_at < ?",
                (start, end),
            ).fetchone()
        return int(row["n"]) if row else 0

    # ── Harcama ───────────────────────────────────────────────────────────

    def add_spend(
        self,
        *,
        provider: str,
        model: str,
        kind: str,
        cost_usd: float | None,
        latency_ms: int,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Bir sağlayıcı çağrısının bedelini kaydeder.

        Maliyet bildirilmediyse (örn. Groq ücretsiz katman) 0 yazılır — tahmin
        uydurulmaz, harcama olduğundan yüksek gösterilmez.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO spend (created_at, provider, model, kind, cost_usd, latency_ms, meta) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now(UTC).isoformat(),
                    provider,
                    model,
                    kind,
                    float(cost_usd or 0.0),
                    latency_ms,
                    json.dumps(meta, ensure_ascii=False) if meta else None,
                ),
            )
            self._conn.commit()

    def spend_summary(self) -> SpendSummary:
        # Harcama da kullanıcının yerel gününe/ayına göre özetlenir; bütçe
        # uyarısı onun takvimine göre anlam taşır.
        day_start, day_end = self._local_day_bounds()
        now = datetime.now().astimezone()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start_utc = month_start.astimezone(UTC).isoformat()

        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN created_at >= ? AND created_at < ?
                                      THEN cost_usd END), 0) AS today,
                    COALESCE(SUM(CASE WHEN created_at >= ? THEN cost_usd END), 0) AS month,
                    COALESCE(SUM(cost_usd), 0) AS total,
                    COUNT(*) AS calls
                FROM spend
                """,
                (day_start, day_end, month_start_utc),
            ).fetchone()
        return SpendSummary(
            today_usd=float(row["today"]),
            month_usd=float(row["month"]),
            total_usd=float(row["total"]),
            call_count=int(row["calls"]),
        )
