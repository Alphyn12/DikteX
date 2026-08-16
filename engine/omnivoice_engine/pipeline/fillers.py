"""Dolgu kelime temizleme (Properties I.1).

İki katmanlı çalışır:

1. **Bu modül** — kesin olarak anlamsız olanları siler: "eee", "ııı", "mmm"
   gibi sesler ve kekeleme kaynaklı kelime tekrarları. Yerel, anlık, bedava.
2. **LLM katmanı** — bağlama bağlı olanları ("yani", "işte", "şey") cümlenin
   anlamına bakarak temizler.

Ayrım bilinçli: "şey" bazen gerçekten bir dolgu, bazen "şu şey nerede?"
cümlesindeki gibi cümlenin öznesi. Bunu düzenli ifadeyle ayırt etmek mümkün
değil, bu yüzden buradaki temizlik yalnız **kelime olmayan** seslerle sınırlı.
Anlamı bozma riski olan hiçbir şey burada silinmez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Kelime olmayan duraksama sesleri. Harfin en az üç kez tekrarı ya da
#: bilinen kalıplar. "ee" gibi iki harflileri de alıyoruz ama yalnız tek
#: başlarına durduklarında.
_SOUND_PATTERNS = [
    r"[eE]{2,}",  # eee, ee
    r"[ıI]{2,}",  # ııı, ıı
    r"[iI]{3,}",  # iii
    r"[aA]{3,}",  # aaa
    r"[öÖ]{2,}",  # öö
    r"[uU]{3,}",  # uuu
    r"[mM]{2,}",  # mmm
    r"[hH][mM]+",  # hmm, hm
    r"[eE][hH]+",  # eh, ehh
    r"[aA][hH]+",  # ah (duraksama)
    r"[uU][hH]+",  # uh
    r"[uU][mM]+",  # um
    r"[eE][rR]{2,}",  # err
]

#: Tam kelime olarak eşleşmeli — "eee" silinir ama "eeeğitim" bozulmaz.
_SOUND_RE = re.compile(
    r"(?<![\wçğıöşüÇĞİÖŞÜ])(?:" + "|".join(_SOUND_PATTERNS) + r")(?![\wçğıöşüÇĞİÖŞÜ])",
    re.UNICODE,
)

#: Kekeleme: aynı kelimenin peş peşe tekrarı ("bir bir", "ben ben ben").
#: Türkçede anlamlı ikilemeler de var ("yavaş yavaş", "az az"), bu yüzden
#: bilinen ikilemeler korunuyor.
_REDUPLICATION_ALLOWLIST = {
    "yavaş",
    "az",
    "çok",
    "tek",
    "bir",  # "bir bir anlattı" — anlamlı olabilir, riske girmiyoruz
    "iyi",
    "güzel",
    "sıcak",
    "usul",
    "yer",
    "zaman",
    "ara",
    "kıvır",
    "koşa",
    "gide",
}

_REPEAT_RE = re.compile(
    r"(?<![\wçğıöşüÇĞİÖŞÜ])([\wçğıöşüÇĞİÖŞÜ]+)(\s+\1)+(?![\wçğıöşüÇĞİÖŞÜ])",
    re.IGNORECASE | re.UNICODE,
)

#: Silme sonrası kalan boşluk ve noktalama artıkları.
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?…])")
_DOUBLE_PUNCT_RE = re.compile(r"([,;:])\s*(?=[,.;:!?])")
_LEADING_PUNCT_RE = re.compile(r"^[\s,;:]+")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True, slots=True)
class FillerResult:
    """Temizlenmiş metin ve ne kadarının atıldığı."""

    text: str
    removed_count: int

    @property
    def changed(self) -> bool:
        return self.removed_count > 0


def _strip_repetitions(text: str) -> tuple[str, int]:
    removed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        word = match.group(1)
        if word.lower() in _REDUPLICATION_ALLOWLIST:
            return match.group(0)
        # Kaç kopyanın atıldığını say: toplam tekrar sayısı eksi bir.
        copies = len(match.group(0).split())
        removed += copies - 1
        return word

    return _REPEAT_RE.sub(replace, text), removed


def strip_fillers(text: str) -> FillerResult:
    """Kelime olmayan duraksama seslerini ve kekelemeleri temizler."""
    if not text.strip():
        return FillerResult(text=text, removed_count=0)

    sounds = _SOUND_RE.findall(text)
    cleaned = _SOUND_RE.sub("", text)

    cleaned, repeats = _strip_repetitions(cleaned)

    # Silme işlemi "hazırlayamayız , pazartesi" gibi artıklar bırakır.
    cleaned = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = _DOUBLE_PUNCT_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _LEADING_PUNCT_RE.sub("", cleaned)
    cleaned = cleaned.strip()

    # Baştaki kelime küçük harfe düşmüş olabilir ("Şey, yarına" → "yarına").
    if cleaned and text.strip()[:1].isupper():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return FillerResult(text=cleaned, removed_count=len(sounds) + repeats)
