"""Özel terim ve sözlük katmanı (Properties I.4).

Whisper "faster-whisper" yerine "faster whisper", "diarization" yerine
"diyarizasyon" duyabilir. Sözlük bu terimleri hem STT'ye bağlam ipucu olarak
hem de LLM'e "bunları değiştirme" yönergesi olarak iletir.

Ölçtük: sözlük enjeksiyonu çalışıyor — sözlükte tireli yazılan
`faster-whisper`, transkriptte de tireli döndü.

Depolama `.json` dosyasıdır (Properties I.4 açıkça böyle istiyor): kullanıcı
dosyayı elle düzenleyebilir, sürüm kontrolüne koyabilir, taşıyabilir.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)

#: STT istemine sığdırılacak terim sayısı. Whisper'ın `prompt` alanı sınırlı;
#: çok uzun bir liste transkripsiyonu bozar.
MAX_STT_TERMS = 60


@dataclass(frozen=True, slots=True)
class Term:
    """Sözlükteki bir terim."""

    text: str
    #: Bu terimin kaç kez yanlış yazıldığı — öneri sıralamasında kullanılır.
    misspelled: int = 0
    #: Kullanıcının eklediği mi, sistemin önerdiği mi?
    suggested: bool = False


@dataclass
class Vocabulary:
    """Terim listesi ve kalıcılığı."""

    path: Path
    terms: list[Term] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> Vocabulary:
        """Sözlüğü diskten okur. Dosya yoksa boş sözlük döner."""
        resolved = path or default_vocabulary_path()
        vocabulary = cls(path=resolved)

        if not resolved.exists():
            return vocabulary

        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Bozuk dosya yüzünden dikte çalışmaz hâle gelmemeli.
            log.warning("Sözlük okunamadı, boş başlatılıyor: %s", resolved, exc_info=True)
            return vocabulary

        entries = raw.get("terms", []) if isinstance(raw, dict) else raw
        for entry in entries:
            if isinstance(entry, str):
                vocabulary.terms.append(Term(text=entry))
            elif isinstance(entry, dict) and entry.get("text"):
                vocabulary.terms.append(
                    Term(
                        text=str(entry["text"]),
                        misspelled=int(entry.get("misspelled", 0)),
                        suggested=bool(entry.get("suggested", False)),
                    )
                )
        return vocabulary

    def save(self) -> None:
        """Sözlüğü diske yazar."""
        payload = {
            "version": 1,
            "terms": [
                {"text": t.text, "misspelled": t.misspelled, "suggested": t.suggested}
                for t in self.terms
            ],
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Önce geçici dosyaya yazıp taşıyoruz: yazma sırasında kesinti
            # olursa sözlük yarım kalmasın.
            temp = self.path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)

    # ── Düzenleme ─────────────────────────────────────────────────────────

    def add(self, text: str, *, suggested: bool = False) -> bool:
        """Terim ekler. Zaten varsa `False` döner."""
        cleaned = text.strip()
        if not cleaned:
            return False
        if any(t.text.lower() == cleaned.lower() for t in self.terms):
            return False
        self.terms.append(Term(text=cleaned, suggested=suggested))
        self.save()
        return True

    def remove(self, text: str) -> bool:
        before = len(self.terms)
        self.terms = [t for t in self.terms if t.text.lower() != text.strip().lower()]
        if len(self.terms) == before:
            return False
        self.save()
        return True

    def accept_suggestion(self, text: str) -> bool:
        """Önerilen bir terimi kalıcı hâle getirir."""
        for index, term in enumerate(self.terms):
            if term.text.lower() == text.strip().lower() and term.suggested:
                self.terms[index] = Term(text=term.text, misspelled=term.misspelled)
                self.save()
                return True
        return False

    # ── Kullanım ──────────────────────────────────────────────────────────

    def stt_terms(self, limit: int = MAX_STT_TERMS) -> list[str]:
        """STT istemine gidecek terimler.

        Öncelik sırası: en çok yanlış yazılanlar önce. Sınır dolduğunda
        kesilen terimler LLM katmanında yine de korunuyor.
        """
        ordered = sorted(self.terms, key=lambda t: (-t.misspelled, t.text.lower()))
        return [t.text for t in ordered[:limit]]

    def llm_terms(self) -> list[str]:
        """LLM istemine gidecek terimler — tamamı."""
        return [t.text for t in self.terms]

    @property
    def confirmed(self) -> list[Term]:
        return [t for t in self.terms if not t.suggested]

    @property
    def suggestions(self) -> list[Term]:
        return [t for t in self.terms if t.suggested]

    def to_payload(self) -> dict[str, object]:
        """Arayüze gönderilecek biçim."""
        return {
            "path": str(self.path),
            "terms": [
                {"text": t.text, "misspelled": t.misspelled, "suggested": t.suggested}
                for t in self.terms
            ],
            "confirmedCount": len(self.confirmed),
            "suggestionCount": len(self.suggestions),
        }


def default_vocabulary_path() -> Path:
    """Sözlüğün yeri — veritabanıyla aynı klasör."""
    return default_db_path().parent / "vocabulary.json"
