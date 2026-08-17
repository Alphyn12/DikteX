"""Başarısız dikte kuyruğu (Faz 7.2).

İnternet kesikse ya da sağlayıcı hata verirse konuşma tamamen kayboluyordu.
Ses zaten bellekte; diske alıp bağlantı gelince göndermek onu kurtarıyor.

## Gizlilik gerilimi — bilinçli ve sınırlı bir taviz

Uygulama kullanıcıya "ses diske yazılmıyor" diyor ve bu, sürekli dinlenen
pre-roll için doğru olmaya devam ediyor. Ama bu modül, **başarısız bir
diktenin** sesini diske yazıyor. Bu, gizlilik duruşunda gerçek bir değişiklik
ve şu kurallarla sınırlandırıldı:

1. **Yalnız başarısızlıkta yazılır.** Başarılı dikte diske hiç değmiyor.
2. **Gönderilir gönderilmez silinir.** Kuyrukta kalması bir hata belirtisidir.
3. **Sayı ve yaş sınırı var.** Unutulan bir kayıt sonsuza kadar durmasın.
4. **Kullanıcı görebilir ve silebilir.** Arayüzde kuyruk sayısı gösteriliyor.
5. **Klasör kullanıcının kendi profilinde**, veritabanının yanında.

Alternatif "sesi bellekte tut" olurdu ama motor yeniden başlarsa (ya da
bilgisayar kapanırsa) kayıt yine giderdi — ki hata anında en olası senaryo bu.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)

#: Kuyrukta en fazla kaç kayıt tutulur. Aşılırsa en eskisi silinir.
MAX_ITEMS = 20

#: Bir kayıt en fazla kaç gün bekler. Aşan kayıt sessizce silinir —
#: haftalarca önce konuşulmuş bir cümleyi yapıştırmanın değeri yok, ama
#: diskte duran sesin gizlilik maliyeti sürüyor.
MAX_AGE_DAYS = 7


@dataclass(frozen=True, slots=True)
class QueuedClip:
    """Kuyrukta bekleyen bir kayıt."""

    item_id: str
    audio_path: Path
    meta_path: Path
    mode: str
    #: Kaydın alındığı an (Unix zamanı).
    created_at: float
    duration_seconds: float
    #: Kuyruğa girmesine sebep olan hata.
    error: str
    #: Kaç kez denendi — sürekli başarısız olan bir kayıt ayırt edilebilsin.
    attempts: int
    file_suffix: str

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.item_id,
            "mode": self.mode,
            "createdAt": self.created_at,
            "durationSeconds": round(self.duration_seconds, 1),
            "error": self.error,
            "attempts": self.attempts,
        }


class ClipQueue:
    """Başarısız kayıtların diskteki kuyruğu."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or default_queue_dir()

    # ── Yazma ─────────────────────────────────────────────────────────────

    def add(
        self,
        *,
        audio: bytes,
        suffix: str,
        mode: str,
        duration_seconds: float,
        error: str,
    ) -> QueuedClip | None:
        """Kaydı kuyruğa alır. Yazılamazsa `None` — kuyruk hatası dikteyi
        büsbütün çökertmemeli."""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            item_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
            audio_path = self.directory / f"{item_id}{suffix}"
            meta_path = self.directory / f"{item_id}.json"

            audio_path.write_bytes(audio)
            meta = {
                "id": item_id,
                "mode": mode,
                "createdAt": time.time(),
                "durationSeconds": duration_seconds,
                "error": error,
                "attempts": 0,
                "suffix": suffix,
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except OSError:
            log.warning("Kayıt kuyruğa alınamadı", exc_info=True)
            return None

        self.prune()
        log.info("Kayıt kuyruğa alındı: %s (%s)", item_id, error)
        return self._read_item(meta_path)

    def mark_attempt(self, item: QueuedClip) -> None:
        """Deneme sayacını artırır."""
        try:
            meta = json.loads(item.meta_path.read_text(encoding="utf-8"))
            meta["attempts"] = int(meta.get("attempts", 0)) + 1
            item.meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except (OSError, json.JSONDecodeError, ValueError):
            log.warning("Deneme sayacı güncellenemedi: %s", item.item_id, exc_info=True)

    def remove(self, item: QueuedClip) -> None:
        """Kaydı ve sesini siler. Gönderim başarılıysa **hemen** çağrılmalı."""
        for path in (item.audio_path, item.meta_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                log.warning("Kuyruk dosyası silinemedi: %s", path, exc_info=True)

    def remove_by_id(self, item_id: str) -> bool:
        for item in self.items():
            if item.item_id == item_id:
                self.remove(item)
                return True
        return False

    def clear(self) -> int:
        items = self.items()
        for item in items:
            self.remove(item)
        return len(items)

    # ── Okuma ─────────────────────────────────────────────────────────────

    def items(self) -> list[QueuedClip]:
        """Kuyruktaki kayıtlar, en eskisi başta."""
        if not self.directory.exists():
            return []

        found: list[QueuedClip] = []
        for meta_path in sorted(self.directory.glob("*.json")):
            item = self._read_item(meta_path)
            if item is not None:
                found.append(item)
        return sorted(found, key=lambda item: item.created_at)

    def _read_item(self, meta_path: Path) -> QueuedClip | None:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        suffix = str(meta.get("suffix", ".flac"))
        audio_path = meta_path.with_suffix("")
        audio_path = audio_path.with_name(audio_path.name + suffix)
        if not audio_path.exists():
            # Sesi olmayan bir kayıt işe yaramaz; artığı temizle.
            try:
                meta_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        return QueuedClip(
            item_id=str(meta.get("id", meta_path.stem)),
            audio_path=audio_path,
            meta_path=meta_path,
            mode=str(meta.get("mode", "quick")),
            created_at=float(meta.get("createdAt", 0.0)),
            duration_seconds=float(meta.get("durationSeconds", 0.0)),
            error=str(meta.get("error", "")),
            attempts=int(meta.get("attempts", 0)),
            file_suffix=suffix,
        )

    # ── Bakım ─────────────────────────────────────────────────────────────

    def prune(self) -> int:
        """Yaşlı ve fazla kayıtları siler. Silinen sayısını döner."""
        items = self.items()
        doomed = [item for item in items if item.age_days > MAX_AGE_DAYS]

        survivors = [item for item in items if item not in doomed]
        if len(survivors) > MAX_ITEMS:
            # En eskiler gider: yenisi kullanıcının aklında olma ihtimali
            # daha yüksek.
            doomed += survivors[: len(survivors) - MAX_ITEMS]

        for item in doomed:
            log.info("Kuyruktan düşürüldü: %s (%.1f gün)", item.item_id, item.age_days)
            self.remove(item)
        return len(doomed)

    def to_payload(self) -> dict[str, object]:
        items = self.items()
        return {
            "directory": str(self.directory),
            "items": [item.to_payload() for item in items],
            "count": len(items),
        }


def default_queue_dir() -> Path:
    return default_db_path().parent / "queue"
