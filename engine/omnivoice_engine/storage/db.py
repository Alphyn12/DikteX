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

SCHEMA_VERSION = 1

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
    pasted          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dictations_created
    ON dictations (created_at DESC);

-- Tam metin arama. `content=` ile asıl tabloya bağlanır, metin iki kez
-- saklanmaz.
CREATE VIRTUAL TABLE IF NOT EXISTS dictations_fts USING fts5 (
    raw_text,
    final_text,
    app_name,
    content='dictations',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS dictations_ai AFTER INSERT ON dictations BEGIN
    INSERT INTO dictations_fts (rowid, raw_text, final_text, app_name)
    VALUES (new.id, new.raw_text, new.final_text, new.app_name);
END;

CREATE TRIGGER IF NOT EXISTS dictations_ad AFTER DELETE ON dictations BEGIN
    INSERT INTO dictations_fts (dictations_fts, rowid, raw_text, final_text, app_name)
    VALUES ('delete', old.id, old.raw_text, old.final_text, old.app_name);
END;

CREATE TRIGGER IF NOT EXISTS dictations_au AFTER UPDATE ON dictations BEGIN
    INSERT INTO dictations_fts (dictations_fts, rowid, raw_text, final_text, app_name)
    VALUES ('delete', old.id, old.raw_text, old.final_text, old.app_name);
    INSERT INTO dictations_fts (rowid, raw_text, final_text, app_name)
    VALUES (new.id, new.raw_text, new.final_text, new.app_name);
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
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()
        log.info("Veritabanı hazır: %s", self.path)

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
                    cost_usd, pasted
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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

    def search_dictations(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Tam metin arama. Boş sorgu son kayıtları döndürür."""
        if not query.strip():
            return self.recent_dictations(limit)

        # FTS5 sorgu sözdizimindeki özel karakterler kullanıcı metninde
        # olabilir; tırnak içine alıp önek eşleşmesi ekliyoruz.
        escaped = query.replace('"', '""')
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
