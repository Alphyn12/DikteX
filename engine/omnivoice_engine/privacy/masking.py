"""Hassas veri maskeleme (Properties VI.1).

Buluta giden her metin önce buradan geçer. Amaç, bir TC kimlik numarasının,
kart numarasının veya API anahtarının Groq/OpenRouter/Gemini sunucularına
ulaşmasını engellemek.

**Maskeleme geri alınabilir.** Değer bir yer tutucuyla değiştirilip istem
gönderiliyor, dönen yanıtta yer tutucu gerçek değere geri çevriliyor. Sebebi
somut: kullanıcı "kart numaram şu, bunu forma yaz" dediyse çıktıda gerçek
numarayı görmek istiyor — ama numaranın buluta gitmesini istemiyor. Tek yönlü
maskeleme kullanıcının metnini bozardı.

**Ne koruduğu ve ne korumadığı:**

Korur → LLM ayağını. İstem metni, seçili metin, pano içeriği ve git diff'i.
Gerçek sızıntı yolu burasıdır: `{ClipboardContent}` ve `{SelectedText}` gerçek
anahtar taşıyabilir, git diff'inde `.env` satırı olabilir.

**Korumaz → STT ayağını.** Ses kaydı Groq'a maskelenmeden gidiyor, çünkü
maskeleyecek metin henüz yok — metin oradan geliyor. Yani bir parolayı sesle
okursan o ses konuşma tanıma sağlayıcısına ulaşır. Bunu ancak yerel STT
çözerdi ve o kapsam dışı. Arayüzde bu sınır açıkça yazıyor.

**Yanlış pozitif, kaçırmaktan pahalıdır.** Rastgele bir 11 haneli sayıyı TC
kimlik sanıp maskelemek, kullanıcının metnini bozar ve maskelemeye olan
güveni bitirir. Bu yüzden sayısal kimlikler **sağlama toplamıyla** doğrulanıyor:
TC kimlik kendi algoritmasıyla, kart numarası Luhn ile, IBAN mod-97 ile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class PiiKind(Enum):
    """Maskelenen değerin türü — arayüzde ne bulunduğunu göstermek için."""

    NATIONAL_ID = "national_id"
    CARD = "card"
    IBAN = "iban"
    API_KEY = "api_key"
    PRIVATE_KEY = "private_key"


#: Yer tutucu biçimi. Köşeli parantez seçildi çünkü modeller onu bir bütün
#: olarak taşıyor; süslü parantez `{...}` değişken enjeksiyonuyla çakışırdı.
def _token(index: int) -> str:
    return f"[PII-{index}]"


#: Geri çevirmede toleranslı olmak zorundayız: model yer tutucuyu
#: `[PII - 3]` ya da `[ PII-3 ]` diye yeniden yazabiliyor.
_TOKEN_PATTERN = re.compile(r"\[\s*PII\s*-\s*(\d+)\s*\]", re.IGNORECASE)


@dataclass
class MaskResult:
    """Maskelenmiş metin ve geri çevirme haritası."""

    text: str
    #: Yer tutucu → gerçek değer.
    mapping: dict[str, str] = field(default_factory=dict)
    #: Bulunan türler; arayüzde "2 kart, 1 anahtar gizlendi" demek için.
    kinds: tuple[PiiKind, ...] = ()

    @property
    def masked_count(self) -> int:
        return len(self.mapping)

    def unmask(self, text: str) -> str:
        """Yer tutucuları gerçek değerlere geri çevirir."""
        if not self.mapping:
            return text

        def replace(match: re.Match[str]) -> str:
            key = _token(int(match.group(1)))
            # Bilinmeyen numara modelin uydurduğu bir yer tutucudur; olduğu
            # gibi bırakmak, yanlış bir değer yazmaktan iyidir.
            return self.mapping.get(key, match.group(0))

        return _TOKEN_PATTERN.sub(replace, text)


# ── Sağlama toplamları ────────────────────────────────────────────────────


def is_valid_national_id(value: str) -> bool:
    """TC kimlik numarası algoritması.

    Yalnız "11 hane" demek yetmez: bir telefon numarası, bir sipariş numarası
    ya da koddaki bir sabit de 11 hanelidir. Algoritma yanlış pozitifleri
    pratik olarak sıfıra indiriyor.
    """
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False

    digits = [int(c) for c in value]
    odd_sum = sum(digits[0:9:2])   # 1., 3., 5., 7., 9. haneler
    even_sum = sum(digits[1:8:2])  # 2., 4., 6., 8. haneler

    if (odd_sum * 7 - even_sum) % 10 != digits[9]:
        return False
    return sum(digits[:10]) % 10 == digits[10]


def is_valid_card(digits: str) -> bool:
    """Luhn sağlaması — kart numaralarının standart kontrolü."""
    if not 13 <= len(digits) <= 19 or not digits.isdigit():
        return False

    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def is_valid_iban(value: str) -> bool:
    """IBAN mod-97 sağlaması (ISO 13616)."""
    compact = value.replace(" ", "").upper()
    if not 15 <= len(compact) <= 34 or not compact[:2].isalpha():
        return False

    rearranged = compact[4:] + compact[:4]
    numeric = ""
    for char in rearranged:
        if char.isdigit():
            numeric += char
        elif char.isalpha():
            numeric += str(ord(char) - 55)  # A=10 … Z=35
        else:
            return False
    return int(numeric) % 97 == 1


# ── Desenler ──────────────────────────────────────────────────────────────

#: Rakam grupları arasında boşluk/tire olabilir: "4111 1111 1111 1111".
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_NATIONAL_ID_CANDIDATE = re.compile(r"\b\d{11}\b")
_IBAN_CANDIDATE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}\b")

#: Bilinen sağlayıcı anahtar önekleri.
#:
#: Önek listesi bilinçli olarak dar: "32 karakterden uzun her dizeyi maskele"
#: gibi genel bir kural, koddaki hash'leri ve UUID'leri de silerdi.
_API_KEY_PATTERNS: list[tuple[re.Pattern[str], PiiKind]] = [
    # OpenAI / Anthropic / OpenRouter — `sk-`, `sk-ant-`, `sk-or-`
    (re.compile(r"\bsk-(?:ant-|or-)?[A-Za-z0-9_\-]{16,}"), PiiKind.API_KEY),
    # Google API anahtarı — bugün `AIza` + 35 karakter, ama uzunluk sabit
    # yazılmıyor: biçim değişirse kaçırmaktansa maskelemek doğru taraf ve
    # `AIza` öneki yeterince ayırt edici, yanlış pozitif riski yok denecek az.
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), PiiKind.API_KEY),
    # Google AI Studio / Gemini yeni biçim
    (re.compile(r"\bAQ\.[A-Za-z0-9_\-]{20,}"), PiiKind.API_KEY),
    # Groq
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), PiiKind.API_KEY),
    # GitHub
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}"), PiiKind.API_KEY),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), PiiKind.API_KEY),
    # Slack
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), PiiKind.API_KEY),
    # AWS erişim anahtarı
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), PiiKind.API_KEY),
    # Özel anahtar blokları — git diff'te gerçekten karşımıza çıkabilir.
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        PiiKind.PRIVATE_KEY,
    ),
]

#: `.env` satırları: `OPENAI_API_KEY=sk-...` ya da `token: "abc123..."`.
#:
#: Anahtar ADI ipucu olarak kullanılıyor; bu, önek listesine uymayan özel
#: anahtarları da yakalıyor ama rastgele metni maskelemiyor.
_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b (?P<name> [A-Z0-9_]* (?: SECRET | PASSWORD | PASSWD | TOKEN | APIKEY | API_KEY | ACCESS_KEY ) [A-Z0-9_]* )
    \s* [:=] \s*
    (?P<quote>["']?)
    (?P<value> [^\s"'#,;]{8,})
    (?P=quote)
    """
)


@dataclass
class _Finding:
    start: int
    end: int
    value: str
    kind: PiiKind


def _collect(text: str) -> list[_Finding]:
    findings: list[_Finding] = []

    for pattern, kind in _API_KEY_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(_Finding(match.start(), match.end(), match.group(0), kind))

    for match in _ASSIGNMENT.finditer(text):
        # Yalnız DEĞER maskeleniyor, anahtar adı kalıyor: modelin
        # "burada bir API anahtarı var" bağlamını görmesi işine yarıyor.
        findings.append(
            _Finding(
                match.start("value"),
                match.end("value"),
                match.group("value"),
                PiiKind.API_KEY,
            )
        )

    for match in _IBAN_CANDIDATE.finditer(text):
        if is_valid_iban(match.group(0)):
            findings.append(
                _Finding(match.start(), match.end(), match.group(0), PiiKind.IBAN)
            )

    for match in _CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"[ -]", "", match.group(0))
        if is_valid_card(digits):
            findings.append(
                _Finding(match.start(), match.end(), match.group(0), PiiKind.CARD)
            )

    for match in _NATIONAL_ID_CANDIDATE.finditer(text):
        if is_valid_national_id(match.group(0)):
            findings.append(
                _Finding(match.start(), match.end(), match.group(0), PiiKind.NATIONAL_ID)
            )

    return findings


def _resolve_overlaps(findings: list[_Finding]) -> list[_Finding]:
    """Çakışan bulguları teke indirir.

    Çakışma gerçek: 16 haneli bir kart numarasının içinde geçerli bir TC
    kimlik dizisi bulunabiliyor. **Uzun olan kazanıyor** — kısa olanı seçmek
    numaranın bir kısmını maskelenmemiş bırakırdı, ki bu maskelememekten
    beterdir: kullanıcı korunduğunu sanır.
    """
    ordered = sorted(findings, key=lambda f: (f.start, -(f.end - f.start)))
    kept: list[_Finding] = []
    for finding in ordered:
        if kept and finding.start < kept[-1].end:
            if (finding.end - finding.start) > (kept[-1].end - kept[-1].start):
                kept[-1] = finding
            continue
        kept.append(finding)
    return kept


def mask(text: str) -> MaskResult:
    """Metindeki hassas değerleri yer tutucularla değiştirir.

    Aynı değer birden çok geçiyorsa **aynı** yer tutucuyu alıyor; farklı
    numara vermek modele iki ayrı değer varmış izlenimi verirdi.
    """
    if not text:
        return MaskResult(text=text)

    findings = _resolve_overlaps(_collect(text))
    if not findings:
        return MaskResult(text=text)

    mapping: dict[str, str] = {}
    by_value: dict[str, str] = {}
    kinds: list[PiiKind] = []
    pieces: list[str] = []
    cursor = 0

    for finding in findings:
        pieces.append(text[cursor : finding.start])
        placeholder = by_value.get(finding.value)
        if placeholder is None:
            placeholder = _token(len(mapping) + 1)
            mapping[placeholder] = finding.value
            by_value[finding.value] = placeholder
            kinds.append(finding.kind)
        pieces.append(placeholder)
        cursor = finding.end

    pieces.append(text[cursor:])
    return MaskResult(text="".join(pieces), mapping=mapping, kinds=tuple(kinds))


def mask_all(*texts: str | None) -> tuple[list[str | None], MaskResult]:
    """Birden çok metni **ortak** bir haritayla maskeler.

    İstem birden fazla parçadan kuruluyor (dikte metni, seçili metin, pano,
    git diff). Her parçayı ayrı maskelemek aynı anahtara farklı yer tutucular
    verirdi ve geri çevirme karışırdı.
    """
    separator = "\x00"
    joined = separator.join(t or "" for t in texts)
    result = mask(joined)
    parts = result.text.split(separator)

    restored: list[str | None] = []
    for original, part in zip(texts, parts, strict=True):
        restored.append(None if original is None else part)
    return restored, result
