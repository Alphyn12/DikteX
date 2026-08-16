"""Dinamik değişken enjeksiyonu (Properties II.3).

Kullanıcı konuşurken "şu seçili kodu refactor et" veya "bugünün tarihini yaz"
diyebilir. Bu değişkenler sesli komutun içine sistem verisiyle doldurulur.

Desteklenen değişkenler:
    {SelectedText}      seçili metin (pano üzerinden okunur)
    {ClipboardContent}  panodaki mevcut içerik
    {CurrentDate}       bugünün tarihi
    {CurrentTime}       şu anki saat
    {AppName}           aktif uygulamanın adı
    {AppTitle}          aktif pencerenin başlığı

Değişkenler iki yoldan gelir: kullanıcı adını doğrudan söyler ("süslü parantez
selected text"), ya da tetikleyici bir ifade kullanır ("şu seçili", "bunu").
İkincisi Türkçe konuşmada çok daha doğal olduğu için desteklenmesi şart.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)

#: Değişken adları büyük/küçük harf duyarsız eşleşir.
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

#: "şu kod" derken kastedilen nesneler. Türkçe eklemeli bir dil olduğu için
#: sonlarına ek gelir: kod → kodu, fonksiyon → fonksiyonu, satır → satırları.
#: Bu yüzden kök eşleşmesinden sonra serbest bir ek kuyruğu bırakıyoruz.
_TARGET_NOUNS = r"(?:kod|metin|blok|satır|satir|fonksiyon|paragraf|cümle|cumle|yazı|yazi)"

#: Kullanıcının seçili metne atıf yaptığını gösteren Türkçe ve İngilizce
#: kalıplar. Bunlardan biri geçtiğinde seçili metin otomatik okunur.
#:
#: Yalnız "bu"/"şu" yetmez — "bu iyi bir fikir" cümlesinde seçim kastedilmiyor.
#: İşaret zamiri bir metin/kod nesnesiyle birlikte gelmeli.
_SELECTION_HINTS = re.compile(
    r"("
    r"\b(?:seçili|secili|seçtiğim|sectigim|işaretlediğim|isaretledigim)\w*"
    r"|\b(?:şu|su|bu|o)\s+" + _TARGET_NOUNS + r"\w*"
    r"|\b(?:selected|highlighted)\b"
    r"|\bthis\s+(?:code|text|block|function|snippet|paragraph)\b"
    r")",
    re.IGNORECASE | re.UNICODE,
)


@dataclass(frozen=True, slots=True)
class VariableContext:
    """Değişkenleri doldurmak için gereken sistem verisi."""

    app_name: str = ""
    window_title: str = ""
    selected_text: str = ""
    clipboard: str = ""
    now: datetime = field(default_factory=datetime.now)

    def resolve(self, name: str) -> str | None:
        """Değişken adını değerine çevirir. Bilinmeyen ad için `None`."""
        match name.lower():
            case "selectedtext" | "selection":
                return self.selected_text
            case "clipboardcontent" | "clipboard":
                return self.clipboard
            case "currentdate" | "date":
                return self.now.strftime("%d.%m.%Y")
            case "currenttime" | "time":
                return self.now.strftime("%H:%M")
            case "appname" | "app":
                return self.app_name
            case "apptitle" | "title":
                return self.window_title
            case _:
                return None


@dataclass(frozen=True, slots=True)
class InjectionResult:
    """Değişken doldurma sonucu."""

    text: str
    #: Hangi değişkenlerin gerçekten doldurulduğu — arayüzde rozet olarak gösterilir.
    used: tuple[str, ...]
    #: Metinde geçen ama karşılığı boş olan değişkenler.
    empty: tuple[str, ...]


def inject(text: str, context: VariableContext) -> InjectionResult:
    """Metindeki `{Değişken}` yer tutucularını doldurur.

    Karşılığı olmayan yer tutucu **olduğu gibi bırakılır**: kullanıcı süslü
    parantezli bir şey dikte etmiş olabilir ve onu sessizce silmek metni bozar.
    """
    used: list[str] = []
    empty: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = context.resolve(name)
        if value is None:
            return match.group(0)
        if not value.strip():
            empty.append(name)
            return ""
        used.append(name)
        return value

    return InjectionResult(
        text=_PLACEHOLDER_RE.sub(replace, text),
        used=tuple(dict.fromkeys(used)),
        empty=tuple(dict.fromkeys(empty)),
    )


def mentions_selection(text: str) -> bool:
    """Kullanıcı seçili metne atıf yapıyor mu?

    "şu seçili bloğu async yap" gibi bir cümlede `{SelectedText}` yazılmaz ama
    kastedilen odur. Bu tespit, seçili metnin isteme eklenip eklenmeyeceğine
    karar verir.
    """
    return bool(_SELECTION_HINTS.search(text))
