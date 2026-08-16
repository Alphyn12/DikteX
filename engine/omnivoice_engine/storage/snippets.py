"""Snippet ve şablon kütüphanesi (Properties V.3).

Kullanıcı sık kullandığı uzun prompt kalıplarını kaydeder ve sesle tetikler:
"kod inceleme şablonu" dediğinde o kalıp isteme eklenir.

Tetikleme **bulanık** olmalı: kullanıcı kayıtlı adı birebir söylemez. "kod
inceleme" kaydı "kod incelemesi yap" veya "koda inceleme şablonu" ile de
bulunabilmeli. Bu yüzden basit bir kelime örtüşmesi puanlaması kullanılıyor —
tam eşleşme aramak, özelliği pratikte kullanılamaz hâle getirirdi.

Depolama sözlükle aynı desende `.json`: kullanıcı elle düzenleyebilir,
sürüm kontrolüne koyabilir.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)

#: Bir snippet'in tetiklenmesi için gereken en düşük benzerlik.
#: Düşük tutmak yanlış snippet'i tetikler, yüksek tutmak hiç tetiklemez.
MATCH_THRESHOLD = 0.55

#: Eşleşmede yok sayılan Türkçe/İngilizce dolgu kelimeleri.
_STOPWORDS = frozenset(
    {
        "bir", "bu", "şu", "o", "ve", "ile", "için", "gibi", "olarak", "yap",
        "yaz", "ver", "kullan", "şablonu", "şablon", "kalıbı", "kalıp",
        "the", "a", "an", "and", "for", "with", "template", "use",
    }
)


@dataclass(frozen=True, slots=True)
class Snippet:
    """Kayıtlı bir prompt kalıbı."""

    name: str
    body: str
    #: Sesli tetikleme için ek anahtar kelimeler.
    triggers: tuple[str, ...] = ()
    #: Kaç kez kullanıldığı — sıralamada ve arayüzde gösterilir.
    used: int = 0

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "body": self.body,
            "triggers": list(self.triggers),
            "used": self.used,
        }


def fold(text: str) -> str:
    """Metni karşılaştırılabilir hâle getirir.

    İki iş yapıyor:

    1. **Türkçe büyük/küçük harf tuzağı.** Python'da `"İ".lower()` sonucu
       `"i"` değil, `"i" + birleşen nokta`. Bu yüzden `"KOD İNCELEME".lower()`
       ile `"kod inceleme"` eşit çıkmıyor. Birleşen işaretleri atarak çözüyoruz.
    2. **Aksan indirgeme.** Konuşma tanıma bazen aksansız yazıyor ve kullanıcı
       da öyle kaydetmiş olabilir; "sözlük" ile "sozluk" eşleşmeli.
    """
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # NFKD bunları ayrıştırmıyor; elle eşliyoruz.
    for source, target in (("ı", "i"), ("ğ", "g"), ("ş", "s"), ("ø", "o")):
        stripped = stripped.replace(source, target)
    return stripped


def _normalize(text: str) -> list[str]:
    """Metni karşılaştırılabilir kelime listesine indirir."""
    words = re.findall(r"\w+", fold(text))
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


#: İki kelimenin aynı kökten sayılması için gereken ortak önek uzunluğu.
#: Türkçe ekler kökün sonuna geldiği için önek karşılaştırması doğal çözüm.
_STEM_LENGTH = 4


def _words_match(a: str, b: str) -> bool:
    """İki kelime aynı kökten mi?

    Türkçe eklemeli: "inceleme" ile "incelemesi" aynı şeydir ama tam eşitlik
    aramak bunu kaçırır. Biri diğerinin öneki ise eşleşmiş sayıyoruz —
    yeterince uzun bir ortak kök varsa.
    """
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= _STEM_LENGTH and longer.startswith(shorter)


def _similarity(query_words: list[str], target_words: list[str]) -> tuple[float, int]:
    """Hedefin kaç kelimesinin sorguda geçtiği.

    Yönü bilinçli: **hedefin** kelimeleri sorguda aranıyor. Böylece uzun bir
    cümle içinde geçen kısa bir snippet adı bulunabiliyor ("bugün şu kod
    inceleme şablonunu kullanalım" → "kod inceleme").

    İki değer döner: oran ve eşleşen kelime **sayısı**. Sayı gerekli, çünkü
    tek kelimelik "kod" snippet'i de üç kelimelik "kod inceleme raporu" da
    1.0 oran verir; eşitlikte daha özgül olan kazanmalı.
    """
    if not target_words:
        return 0.0, 0
    hits = sum(1 for word in target_words if any(_words_match(word, q) for q in query_words))
    return hits / len(target_words), hits


@dataclass
class SnippetLibrary:
    """Snippet listesi ve kalıcılığı."""

    path: Path
    snippets: list[Snippet] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> SnippetLibrary:
        resolved = path or default_snippets_path()
        library = cls(path=resolved)

        if not resolved.exists():
            return library

        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Bozuk dosya yüzünden dikte çalışmaz hâle gelmemeli.
            log.warning("Snippet dosyası okunamadı: %s", resolved, exc_info=True)
            return library

        entries = raw.get("snippets", []) if isinstance(raw, dict) else raw
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            library.snippets.append(
                Snippet(
                    name=str(entry["name"]),
                    body=str(entry.get("body", "")),
                    triggers=tuple(str(t) for t in entry.get("triggers", [])),
                    used=int(entry.get("used", 0)),
                )
            )
        return library

    def save(self) -> None:
        payload = {"version": 1, "snippets": [s.to_payload() for s in self.snippets]}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)

    # ── Düzenleme ─────────────────────────────────────────────────────────

    def add(self, name: str, body: str, triggers: list[str] | None = None) -> bool:
        cleaned = name.strip()
        if not cleaned or not body.strip():
            return False
        if any(fold(s.name) == fold(cleaned) for s in self.snippets):
            return False
        self.snippets.append(
            Snippet(name=cleaned, body=body.strip(), triggers=tuple(triggers or ()))
        )
        self.save()
        return True

    def remove(self, name: str) -> bool:
        before = len(self.snippets)
        self.snippets = [s for s in self.snippets if fold(s.name) != fold(name.strip())]
        if len(self.snippets) == before:
            return False
        self.save()
        return True

    def mark_used(self, name: str) -> None:
        for index, snippet in enumerate(self.snippets):
            if fold(snippet.name) == fold(name):
                self.snippets[index] = Snippet(
                    name=snippet.name,
                    body=snippet.body,
                    triggers=snippet.triggers,
                    used=snippet.used + 1,
                )
                self.save()
                return

    # ── Eşleştirme ────────────────────────────────────────────────────────

    def find(self, spoken: str) -> Snippet | None:
        """Konuşulan metinde bir snippet tetikleniyor mu?

        En yüksek puanlı eşleşme döner; eşitlik durumunda daha çok kullanılan
        kazanır — kullanıcının alışkanlığı doğru tahmindir.
        """
        query = _normalize(spoken)
        if not query:
            return None

        best: tuple[tuple[float, int, int], Snippet] | None = None
        for snippet in self.snippets:
            # Ad ve tetikleyicilerin en iyisi alınır.
            candidates = [snippet.name, *snippet.triggers]
            ratio, hits = max(
                (_similarity(query, _normalize(c)) for c in candidates),
                key=lambda pair: (pair[0], pair[1]),
            )
            if ratio < MATCH_THRESHOLD:
                continue

            # Sıralama ölçütü: önce oran, sonra eşleşen kelime sayısı
            # (özgüllük), en son kullanım sıklığı.
            key = (ratio, hits, snippet.used)
            if best is None or key > best[0]:
                best = (key, snippet)

        return best[1] if best else None

    def to_payload(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "snippets": [s.to_payload() for s in self.snippets],
        }


def default_snippets_path() -> Path:
    return default_db_path().parent / "snippets.json"
