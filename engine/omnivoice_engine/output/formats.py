"""Biçimlendirilmiş yapıştırma (Properties V.7).

Aynı metin hedefe göre farklı biçimde yapıştırılmalı: Notion'a Markdown,
bir JSON alanına kaçışlanmış dize, bir HTML editörüne etiketli metin.

Biçim iki yoldan belirlenir:
  1. Kullanıcı açıkça söyler ("json olarak yapıştır"),
  2. hedef uygulamanın profili ima eder (terminalde düz metin).

Dönüşümler **kayıpsız olmayabilir** — Markdown'ı düz metne çevirmek biçim
işaretlerini atar. Bu yüzden pre-flight'ta kullanıcı sonucu görüyor.
"""

from __future__ import annotations

import html
import json
import re
from enum import Enum


class PasteFormat(Enum):
    PLAIN = "plain"
    """Olduğu gibi. Varsayılan."""

    MARKDOWN = "markdown"
    """Markdown olarak bırak — zaten Markdown üretiliyorsa dokunma."""

    PLAIN_FROM_MARKDOWN = "plain_from_markdown"
    """Markdown işaretlerini temizleyip düz metne indir."""

    JSON_STRING = "json_string"
    """JSON dizesi olarak kaçışla — bir alana yapıştırmak için."""

    HTML = "html"
    """Temel HTML'e çevir."""

    CODE_BLOCK = "code_block"
    """Üç ters tırnakla sar."""


#: Kullanıcının sesli olarak biçim istediğini gösteren kalıplar.
#:
#: Türkçe eklemeli olduğu için kök + serbest ek deseni kullanılıyor
#: ("json'a", "markdown olarak", "düz metin şeklinde").
_FORMAT_HINTS: list[tuple[re.Pattern[str], PasteFormat]] = [
    (re.compile(r"\bjson\w*\b", re.IGNORECASE), PasteFormat.JSON_STRING),
    (re.compile(r"\bhtml\w*\b", re.IGNORECASE), PasteFormat.HTML),
    (re.compile(r"\bmarkdown\w*\b|\bmd\b", re.IGNORECASE), PasteFormat.MARKDOWN),
    (
        re.compile(r"\bdüz\s+metin\w*|\bduz\s+metin\w*|\bplain\s+text\b", re.IGNORECASE),
        PasteFormat.PLAIN_FROM_MARKDOWN,
    ),
    (
        re.compile(r"\bkod\s+blo\w*|\bcode\s+block\b", re.IGNORECASE),
        PasteFormat.CODE_BLOCK,
    ),
]


def detect_format(instruction: str) -> PasteFormat | None:
    """Sesli komuttan istenen biçimi çıkarır. Belirtilmemişse `None`."""
    for pattern, fmt in _FORMAT_HINTS:
        if pattern.search(instruction):
            return fmt
    return None


# ── Dönüşümler ────────────────────────────────────────────────────────────

#: Satır başındaki başlık, liste ve alıntı işaretleri.
_BLOCK_MARKERS = re.compile(r"^\s{0,3}(#{1,6}\s+|[-*+]\s+|\d+\.\s+|>\s?)", re.MULTILINE)
#: Kalın, italik ve satır içi kod.
#:
#: Alt çizgi vurgusu **kelime sınırında** olmak zorunda. Markdown'ın kendi
#: kuralı da bu ve sebebi somut: `my_var_name` gibi bir değişken adı yoksa
#: `myvarname` oluyor. Bir geliştirici aracında bu sessiz bir veri bozulması
#: — test yakaladı.
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDERSCORE = re.compile(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", re.DOTALL)
_ITALIC = re.compile(
    r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)"
    r"|(?<!\w)_(?!\s)([^_]+?)(?<!\s)_(?!\w)"
)

#: `__init__`, `__main__` gibi Python dunder adları.
#:
#: Markdown kuralına göre bunlar kalın metindir, ama bir geliştirici aracında
#: `__init__` yazan biri neredeyse her zaman metodu kastediyor. Ayırt edici
#: ölçüt boşluk: gerçek kalın metin ("__önemli not__") boşluk içerir, dunder
#: içermez.
_DUNDER_CONTENT = re.compile(r"^\w+$")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_FENCE = re.compile(r"^```[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def _strip_bold_underscore(match: re.Match[str]) -> str:
    """`__x__` kalıbını çözer — ama dunder adına dokunmaz."""
    content = match.group(1)
    if _DUNDER_CONTENT.match(content):
        return match.group(0)  # `__init__` olduğu gibi kalsın
    return content


def markdown_to_plain(text: str) -> str:
    """Markdown işaretlerini kaldırır, içeriği korur.

    Bağlantılarda hem metin hem adres korunur: `[a](b)` → `a (b)`. Yalnız
    metni bırakmak adresi kaybettirirdi ve kullanıcı bunu yapıştırdığı yerde
    fark edemezdi.
    """
    result = _FENCE.sub(lambda m: m.group(1), text)
    result = _LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", result)
    result = _INLINE_CODE.sub(lambda m: m.group(1), result)
    result = _BOLD_STAR.sub(lambda m: m.group(1), result)
    result = _BOLD_UNDERSCORE.sub(_strip_bold_underscore, result)
    result = _ITALIC.sub(lambda m: m.group(1) or m.group(2) or "", result)
    result = _BLOCK_MARKERS.sub("", result)
    # Üçten fazla boş satır bırakma.
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def markdown_to_html(text: str) -> str:
    """Temel Markdown → HTML.

    Tam bir Markdown ayrıştırıcısı değil; başlık, liste, kalın, italik, kod
    ve bağlantıyı kapsar. Daha fazlası için bir kütüphane gerekirdi ve
    yapıştırma için bu kadarı yetiyor.
    """
    lines = text.split("\n")
    output: list[str] = []
    in_list = False

    def inline(value: str) -> str:
        escaped = html.escape(value, quote=False)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", escaped)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)

    for line in lines:
        stripped = line.strip()

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            if in_list:
                output.append("</ul>")
                in_list = False
            level = len(heading.group(1))
            output.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        item = re.match(r"^[-*+]\s+(.*)$", stripped)
        if item:
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{inline(item.group(1))}</li>")
            continue

        if in_list:
            output.append("</ul>")
            in_list = False

        if stripped:
            output.append(f"<p>{inline(stripped)}</p>")

    if in_list:
        output.append("</ul>")
    return "\n".join(output)


def apply_format(text: str, fmt: PasteFormat) -> str:
    """Metni istenen biçime çevirir."""
    match fmt:
        case PasteFormat.PLAIN | PasteFormat.MARKDOWN:
            return text
        case PasteFormat.PLAIN_FROM_MARKDOWN:
            return markdown_to_plain(text)
        case PasteFormat.JSON_STRING:
            # `json.dumps` dış tırnakları da ekler; kullanıcı bir JSON alanına
            # yapıştıracaksa tırnaklarıyla birlikte istiyordur.
            return json.dumps(text, ensure_ascii=False)
        case PasteFormat.HTML:
            return markdown_to_html(text)
        case PasteFormat.CODE_BLOCK:
            # Metin zaten ``` içeriyorsa daha uzun bir çit gerekiyor.
            fence = "```"
            while fence in text:
                fence += "`"
            return f"{fence}\n{text}\n{fence}"
