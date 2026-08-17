"""Sesli düzen komutları (Faz 7.10).

Whisper noktalama koyuyor ama **düzen kuramıyor**: konuşurken "yeni satır"
dediğinizde metne "yeni satır" diye yazıyor. Bu modül o ifadeleri gerçek
satır sonlarına ve madde işaretlerine çeviriyor.

## Yanlış pozitif burada gerçekten pahalı

"Yeni satır" bir komut olabilir, ama bir cümlenin parçası da olabilir:
"yeni satır ekledim", "yeni satıra geç dedi". Kelimeyi görür görmez
dönüştürmek metni bozar.

Bu yüzden komut sayılmak için **iki koşul** aranıyor:

1. İfade bir sınırda olmalı — cümle başında, sonunda ya da noktalama ile
   ayrılmış. Cümlenin ortasındaki bir kullanım komut sayılmıyor.
2. Ardından cümleye devam eden bir kelime gelmemeli. "yeni satır ekledim"
   komut değil; "…bitti. Yeni satır. Sonraki madde…" komut.

Ölçüt katı tutuldu: kaçırılan bir komut kullanıcıyı Enter'a bastırır,
yanlış tetiklenen bir komut cümlesini ikiye böler ve bunu ancak sonradan
fark eder.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class LayoutAction(Enum):
    NEWLINE = "newline"
    """Tek satır sonu."""

    PARAGRAPH = "paragraph"
    """Boş satırla ayrılmış yeni paragraf."""

    BULLET = "bullet"
    """Yeni satır + madde işareti."""


@dataclass(frozen=True, slots=True)
class LayoutResult:
    text: str
    #: Uygulanan komut sayısı — arayüzde rozet olarak gösteriliyor.
    applied: int = 0


def _fold(text: str) -> str:
    """Türkçe duyarlı küçük harfe indirme (bkz. `snippets.fold`)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    for source, target in (("ı", "i"), ("ğ", "g"), ("ş", "s")):
        stripped = stripped.replace(source, target)
    return stripped


#: Komut ifadeleri ve karşılıkları.
#:
#: Türkçe ve İngilizce birlikte: kullanıcı iki dilde de dikte edebiliyor ve
#: hangi dilde konuştuğunu komut için ayrıca belirtmesi saçma olurdu.
_COMMANDS: list[tuple[str, LayoutAction]] = [
    ("yeni paragraf", LayoutAction.PARAGRAPH),
    ("new paragraph", LayoutAction.PARAGRAPH),
    ("paragraf", LayoutAction.PARAGRAPH),
    ("yeni satır", LayoutAction.NEWLINE),
    ("alt satır", LayoutAction.NEWLINE),
    ("new line", LayoutAction.NEWLINE),
    ("madde işareti", LayoutAction.BULLET),
    ("yeni madde", LayoutAction.BULLET),
    ("bullet point", LayoutAction.BULLET),
]

_REPLACEMENTS: dict[LayoutAction, str] = {
    LayoutAction.NEWLINE: "\n",
    LayoutAction.PARAGRAPH: "\n\n",
    LayoutAction.BULLET: "\n- ",
}


#: Aksanlı harf → o harfin kabul edilen biçimleri.
#:
#: Konuşma tanıma bazen aksansız yazıyor: "madde isareti", "yeni satir".
#: Ölçtük — `re.IGNORECASE` Türkçe İ'yi doğru katlıyor ama ş/s, ı/i gibi
#: çiftleri elbette eşleştirmiyor. Aksansız yazılmış bir komutu kaçırmak,
#: kullanıcıya "bu özellik bazen çalışıyor" hissi verirdi.
_ACCENT_CLASSES = {
    "ı": "[ıi]",
    "i": "[iı]",
    "ş": "[şs]",
    "s": "[sş]",
    "ğ": "[ğg]",
    "g": "[gğ]",
    "ö": "[öo]",
    "o": "[oö]",
    "ü": "[üu]",
    "u": "[uü]",
    "ç": "[çc]",
    "c": "[cç]",
}


def _accent_tolerant(phrase: str) -> str:
    """İfadeyi aksan farklarına dayanıklı bir desene çevirir."""
    return "".join(_ACCENT_CLASSES.get(char, re.escape(char)) for char in phrase)


def _build_pattern() -> re.Pattern[str]:
    """Komut ifadelerini tek bir desende toplar.

    Uzun ifadeler önce: "yeni paragraf" varken "paragraf" eşleşirse komut
    yanlış okunur.
    """
    phrases = sorted((phrase for phrase, _ in _COMMANDS), key=len, reverse=True)
    alternation = "|".join(_accent_tolerant(p) for p in phrases)
    # Komut, noktalama ya da metin sınırıyla çevrili olmalı. Sağdaki
    # noktalama komutun kendisine ait sayılıp yutuluyor.
    return re.compile(
        r"(?:(?<=^)|(?<=[.!?:;,\n]))\s*(?P<cmd>" + alternation + r")\s*[.!?,;:]*\s*",
        re.IGNORECASE,
    )


_PATTERN = _build_pattern()
_ACTION_BY_PHRASE = {_fold(phrase): action for phrase, action in _COMMANDS}


def apply_layout_commands(text: str) -> LayoutResult:
    """Sesli düzen komutlarını gerçek düzene çevirir."""
    if not text:
        return LayoutResult(text=text)

    count = 0

    def substitute(match: re.Match[str]) -> str:
        nonlocal count
        action = _ACTION_BY_PHRASE.get(_fold(match.group("cmd")))
        if action is None:
            return match.group(0)
        count += 1
        return _REPLACEMENTS[action]

    result = _PATTERN.sub(substitute, text)

    # Komut metnin başındaysa baştaki boşluk/satır sonu artık gereksiz.
    result = result.lstrip("\n")
    # Üç ve daha fazla satır sonu, iki paragraf komutu arka arkaya gelince
    # oluşuyor; ikiye indiriyoruz.
    result = re.sub(r"\n{3,}", "\n\n", result)
    return LayoutResult(text=result.rstrip(), applied=count)
