"""Türkçe sayı normalizasyonu (Faz 7.9).

Whisper Türkçe sayıları **yazıyla** döküyor: "on beş dakika", "iki bin yirmi
altı". Bir belge ya da kod içinde bunlar rakam olmalı.

## Neden yerel, neden LLM değil

Üç sebep: anlık, bedava ve **belirlenimci**. Model bazen çeviriyor bazen
çevirmiyor; kural her zaman aynı sonucu veriyor. Dikte aracında öngörülebilirlik,
zekâdan değerli.

## Türkçe sayı yapısı

Türkçe sayılar bitişik değil, **ayrı kelimelerle** kuruluyor ve sıra sabit:

    [milyar] [milyon] [bin] [yüz] [onlar] [birler]
    "iki yüz otuz beş"        → 235
    "bin dokuz yüz doksan"    → 1990
    "iki bin yirmi altı"      → 2026

Çarpanlar (yüz, bin, milyon) kendinden önceki sayıyı çarpar; önlerinde sayı
yoksa 1 varsayılır ("bin dokuz yüz" = 1900, "yüz elli" = 150).

## Ne YAPILMIYOR

Sıra sayıları ("birinci", "ikinci") ve kesirler ("yarım", "çeyrek") kapsam
dışı: bunlar cümle içinde sayı olarak değil sıfat olarak duruyor ve rakama
çevirmek metni bozar — "birinci gün" ile "1. gün" aynı şey değil ve
kullanıcının hangisini istediği belli değil.
"""

from __future__ import annotations

import re

#: Birler ve onlar.
_UNITS: dict[str, int] = {
    "sıfır": 0,
    "bir": 1,
    "iki": 2,
    "üç": 3,
    "dört": 4,
    "beş": 5,
    "altı": 6,
    "yedi": 7,
    "sekiz": 8,
    "dokuz": 9,
    "on": 10,
    "yirmi": 20,
    "otuz": 30,
    "kırk": 40,
    "elli": 50,
    "altmış": 60,
    "yetmiş": 70,
    "seksen": 80,
    "doksan": 90,
}

#: Çarpanlar. Sıra önemli: büyükten küçüğe ayrıştırılıyor.
_MULTIPLIERS: dict[str, int] = {
    "yüz": 100,
    "bin": 1_000,
    "milyon": 1_000_000,
    "milyar": 1_000_000_000,
}

_NUMBER_WORDS = frozenset(_UNITS) | frozenset(_MULTIPLIERS)

#: "bir" tek başına sayı DEĞİL, belirsiz artikeldir: "bir kahve" → "1 kahve"
#: yapmak metni bozar. Yalnız başka sayı kelimeleriyle birlikteyken sayı
#: sayılıyor.
_ARTICLE = "bir"


def _parse_group(words: list[str]) -> int:
    """Ardışık sayı kelimelerini tek bir tam sayıya çevirir."""
    total = 0
    current = 0

    for word in words:
        if word in _UNITS:
            current += _UNITS[word]
            continue

        multiplier = _MULTIPLIERS[word]
        if multiplier >= 1_000:
            # "iki bin" → 2000; "bin" tek başına → 1000.
            total += (current or 1) * multiplier
            current = 0
        else:
            # "üç yüz" → 300; "yüz" tek başına → 100.
            current = (current or 1) * multiplier

    return total + current


_TOKEN = re.compile(r"\w+|\W+", re.UNICODE)


def normalize_numbers(text: str) -> str:
    """Yazıyla dökülmüş Türkçe sayıları rakama çevirir.

    Sayı olmayan hiçbir şeye dokunulmuyor; tanınmayan bir kelime grubu
    olduğu gibi kalıyor.
    """
    if not text:
        return text

    tokens = _TOKEN.findall(text)
    output: list[str] = []
    buffer: list[str] = []
    #: Tamponlanan sayı kelimeleri arasındaki boşluklar — sayı değilse geri
    #: yazılabilsin diye saklanıyor.
    gaps: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        # Tek başına "bir" artikel sayılıyor, sayı değil.
        if len(buffer) == 1 and buffer[0].lower() == _ARTICLE:
            output.append(buffer[0])
        else:
            output.append(str(_parse_group([w.lower() for w in buffer])))
        # Aradaki boşlukları rakama çevirirken atıyoruz ("on beş" → "15"),
        # ama artikel durumunda korumalıyız.
        if len(buffer) == 1:
            output.extend(gaps)
        buffer.clear()
        gaps.clear()

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()

        if lowered in _NUMBER_WORDS:
            buffer.append(token)
            # Sonraki jeton yalnız boşluksa ve ondan sonra yine sayı kelimesi
            # geliyorsa, bu grup devam ediyor demektir.
            following = tokens[index + 1] if index + 1 < len(tokens) else ""
            after = tokens[index + 2].lower() if index + 2 < len(tokens) else ""
            if following.strip() == "" and after in _NUMBER_WORDS:
                gaps.append(following)
                index += 2
                continue
            flush()
            index += 1
            continue

        flush()
        output.append(token)
        index += 1

    flush()
    return "".join(output)
