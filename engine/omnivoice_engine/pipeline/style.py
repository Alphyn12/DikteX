"""Öğrenen kişisel stil — Style Refiner (Faz 3.13).

Pre-flight zaten bedava bir eğitim sinyali üretiyor: model ne yazdı, kullanıcı
ne yapıştırdı. Aradaki fark kullanıcının gerçek stili ve şu ana kadar çöpe
gidiyordu. Bu modül o farkı saklıyor ve sonraki istemlere örnek olarak
ekliyor.

## Neden varsayılan KAPALI

Bu özellik, **geçmiş dikte içeriğini yeni isteklere taşıyor**. Yani dün
yazdığınız kişisel bir not, bugünkü iş diktenizin isteminde örnek olarak yer
alabilir. Aynı sağlayıcıya gitse bile bu, kullanıcının beklemediği bir veri
akışı — ve beklenmeyen veri akışları açık rıza ister.

Bu yüzden kip varsayılan olarak kapalı, arayüzde ne sakladığı **tek tek
görünüyor** ve tek düğmeyle silinebiliyor. Açıkken de örnekler PII
maskelemesinden geçiriliyor.

## Her düzenleme stil sinyali değil

Kullanıcı metni **baştan yazmış** olabilir. O bir stil tercihi değil, çıktının
reddi; örnek olarak vermek modele yanlış hedef gösterir. Kelime düzeyinde
benzerlik eşiği bunu eliyor.

Daha ince bir ayrım — yazım hatası düzeltmesi ile ufak bir üslup tercihi —
**denendi ve yapılamadı**; ayrıntısı `is_style_signal` içinde. Sezgisel bir
sınıflandırıcıya güvenmek yerine çıktısı denetlenebilir kılındı: saklanan her
örnek arayüzde tek tek görünüyor ve silinebiliyor.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)

#: İsteme eklenen en fazla örnek sayısı.
#:
#: Her örnek girdi jetonu demek ve dikte başına maliyeti artırıyor. Beş örnek
#: ölçülebilir bir stil sinyali veriyor ve ~200 jetondan az yer tutuyor.
MAX_PROMPT_EXAMPLES = 5

#: Diskte tutulan en fazla örnek. Eskiler düşüyor: stil zamanla değişiyor ve
#: bir yıl önceki tercih bugünü temsil etmiyor.
MAX_STORED = 40

#: Örnek olarak saklanacak metnin en fazla uzunluğu. Uzun metinler hem
#: maliyetli hem de stil sinyali taşımıyor.
MAX_LENGTH = 400

#: Kelime düzeyinde en düşük benzerlik. Altındaki düzenlemeler "baştan yazma"
#: sayılıyor ve saklanmıyor.
#:
#: Değer ölçülerek seçildi:
#:
#:     0.105  baştan yazma        (reddedilmeli)
#:     0.286  agresif kısaltma    (gerçek üslup sinyali)
#:     0.400  kısaltma
#:     0.667  resmiden samimiye
#:     0.900  ek düşürme
#:
#: Eşik 0.20: baştan yazmayı eliyor, en agresif kısaltmayı geçiriyor.
MIN_WORD_SIMILARITY = 0.20


@dataclass(frozen=True, slots=True)
class StyleExample:
    """Modelin çıktısı ve kullanıcının düzelttiği hâli."""

    before: str
    after: str
    mode: str
    created_at: float

    def to_payload(self) -> dict[str, object]:
        return {
            "before": self.before,
            "after": self.after,
            "mode": self.mode,
            "createdAt": self.created_at,
        }


_WORD = re.compile(r"\w+|\S")


def similarity(before: str, after: str) -> float:
    """İki metnin **kelime düzeyinde** benzerlik oranı, 0–1.

    Karakter düzeyi denendi ve yetmedi: ölçümde yazım hatası düzeltmesi
    (0.985) ile ek düşürme gibi gerçek bir üslup tercihi (0.976) aynı bölgeye
    düşüyordu. Kelime düzeyi bu ikisini daha iyi ayırıyor.
    """
    return SequenceMatcher(
        None, _WORD.findall(before.lower()), _WORD.findall(after.lower())
    ).ratio()


def is_style_signal(before: str, after: str) -> bool:
    """Bu düzenleme öğrenilmeye değer mi?

    Üç eleme:

    * Değişmemişse sinyal yok.
    * Çok uzunsa saklanmıyor — maliyetli ve stil taşımıyor.
    * Kelime benzerliği eşiğin altındaysa **baştan yazma** sayılıyor:
      kullanıcı modelin çıktısını atmış, örnek olarak vermek modele yanlış
      hedef gösterir.

    **Ne ayırt EDİLMİYOR:** yazım hatası düzeltmesi ile ufak bir üslup
    tercihi. Ölçüldü, ayrılamadı — "başlayacaktır → başlayacak" bir üslup
    sinyali ama bir yazım düzeltmesiyle aynı bölgede duruyor. Denenen
    kelime-bazlı sınıflandırıcı ikisini **ters** işaretledi.

    Bu yüzden iddia edilmiyor: önemsiz bir örneğin saklanması zararsız
    (birkaç jeton) ve asıl güvence, saklananların arayüzde **tek tek
    görünüp silinebilmesi**. Sezgisel bir sınıflandırıcının çıktısı
    denetlenebilir olmalı.
    """
    before = before.strip()
    after = after.strip()

    if not before or not after or before == after:
        return False
    if len(before) > MAX_LENGTH or len(after) > MAX_LENGTH:
        return False

    return similarity(before, after) >= MIN_WORD_SIMILARITY


def build_style_block(examples: list[StyleExample]) -> str:
    """Örnekleri isteme eklenecek metne çevirir.

    Örnekler **en yenisi en sonda** diziliyor: modeller sona yakın olana daha
    çok ağırlık veriyor ve en yeni tercih en güncel olan.
    """
    if not examples:
        return ""

    lines = [
        "KULLANICININ STİLİ:",
        "Aşağıda, bu kullanıcının geçmişte senin çıktını nasıl düzelttiği var. "
        "Aynı tercihleri uygula; örnekleri kopyalama, yalnız üsluba bak.",
        "",
    ]
    for example in examples[-MAX_PROMPT_EXAMPLES:]:
        lines.append(f"- Senin yazdığın:   {example.before}")
        lines.append(f"  Kullanıcı yaptı:  {example.after}")
    return "\n".join(lines)


@dataclass
class StyleLibrary:
    """Stil örneklerinin diskteki hâli."""

    path: Path
    examples: list[StyleExample] = field(default_factory=list)
    enabled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path | None = None, *, enabled: bool = False) -> StyleLibrary:
        resolved = path or default_style_path()
        library = cls(path=resolved, enabled=enabled)

        if not resolved.exists():
            return library

        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("Stil örnekleri okunamadı: %s", resolved)
            return library

        entries = raw.get("examples", []) if isinstance(raw, dict) else raw
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            before = str(entry.get("before", ""))
            after = str(entry.get("after", ""))
            if not before or not after:
                continue
            library.examples.append(
                StyleExample(
                    before=before,
                    after=after,
                    mode=str(entry.get("mode", "quick")),
                    created_at=float(entry.get("createdAt", 0.0)),
                )
            )
        return library

    def save(self) -> bool:
        payload = {"version": 1, "examples": [e.to_payload() for e in self.examples]}
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix(".json.tmp")
                temp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                temp.replace(self.path)
            return True
        except OSError:
            log.warning("Stil örnekleri kaydedilemedi", exc_info=True)
            return False

    def observe(self, before: str, after: str, *, mode: str = "quick") -> bool:
        """Bir pre-flight düzenlemesini değerlendirir ve uygunsa saklar."""
        if not self.enabled or not is_style_signal(before, after):
            return False

        # Aynı düzeltme tekrar geldiyse yenisini tutuyoruz: eski kayıt
        # listeyi doldurup daha yeni örnekleri dışarı iterdi.
        self.examples = [
            e for e in self.examples if e.before != before.strip()
        ]
        self.examples.append(
            StyleExample(
                before=before.strip(),
                after=after.strip(),
                mode=mode,
                created_at=time.time(),
            )
        )
        if len(self.examples) > MAX_STORED:
            self.examples = self.examples[-MAX_STORED:]
        self.save()
        log.info("Stil örneği kaydedildi (%d toplam)", len(self.examples))
        return True

    def prompt_block(self, *, mode: str | None = None) -> str:
        """İsteme eklenecek stil metni.

        Mod verilirse **önce o modun** örnekleri kullanılıyor: kod modundaki
        tercihler sohbet modunda yanlış hedef gösterir.
        """
        if not self.enabled or not self.examples:
            return ""
        pool = [e for e in self.examples if mode is None or e.mode == mode]
        if not pool:
            pool = self.examples
        return build_style_block(pool)

    def clear(self) -> int:
        count = len(self.examples)
        self.examples = []
        self.save()
        return count

    def to_payload(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "enabled": self.enabled,
            "examples": [e.to_payload() for e in self.examples],
            "count": len(self.examples),
        }


def default_style_path() -> Path:
    return default_db_path().parent / "style.json"
