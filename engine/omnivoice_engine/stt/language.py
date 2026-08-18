"""Dil tespiti düzeltmesi.

## Sorun

Whisper'a dil verilmediğinde kendisi tahmin ediyor ve **yanılabiliyor**.
Kullanıcı Türkçe konuşurken çıktı İzlandaca geldi:

    Halló, það er hljóð. Einn, tvö, þrír, tilraun er í gangi...

Metin kaybolmuyor ama tamamen kullanılamaz hâle geliyor.

## Neden dili sabitlemiyoruz

Akla ilk gelen çözüm `language="tr"` yazmak. Kullanıcı hem Türkçe hem
İngilizce dikte ediyor; birini sabitlemek diğerini bozardı.

## Yaklaşım: izin verilen diller

Kullanıcı **konuştuğu dilleri** bildiriyor (varsayılan: Türkçe + İngilizce).
Normal akış değişmiyor — tek çağrı, otomatik tespit. Yalnız tespit edilen dil
bu kümenin dışına düşerse ses, izin verilen her dille yeniden çözümlenip en
olası sonuç seçiliyor.

Yani ek maliyet **sadece hata durumunda** ödeniyor.

## Seçim ölçütü ölçüldü

Whisper `verbose_json` yanıtında segment başına `avg_logprob` veriyor.
Doğru dil belirgin biçimde daha yüksek:

    Türkçe ses, "tr" ile   → -0.130   ✓
    Türkçe ses, "en" ile   → -0.910
    İngilizce ses, "en" ile → -0.201  ✓
    İngilizce ses, "tr" ile → -0.295

Ayrıca ölçüldü: yanlış dil **dayatmak** metni zorla çevirmiyor. İngilizce
sese "tr" verildiğinde metin yine doğru İngilizce çıktı. Dil parametresi bir
zorlama değil, eğilim — bu yüzden düzeltme denemesi güvenli.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Kullanıcı ayar yapmadıysa kabul edilen diller.
#:
#: İkisi birden: kullanıcı gün içinde ikisini de kullanıyor ve hangisini
#: konuştuğunu önceden söylemek zorunda kalmamalı.
DEFAULT_LANGUAGES: tuple[str, ...] = ("tr", "en")

#: Whisper dili adıyla bildiriyor ("Turkish"), biz kodla çalışıyoruz ("tr").
#:
#: Liste kasten kısa: buradaki amaç her dili tanımak değil, **izin verilen**
#: dilleri tanımak. Tanınmayan bir ad zaten kümenin dışında sayılıyor ve
#: düzeltmeyi tetikliyor — istediğimiz de bu.
_NAME_TO_CODE: dict[str, str] = {
    "turkish": "tr",
    "türkçe": "tr",
    "tr": "tr",
    "english": "en",
    "en": "en",
    "german": "de",
    "de": "de",
    "french": "fr",
    "fr": "fr",
    "spanish": "es",
    "es": "es",
}

#: Arayüzde ve günlükte gösterilecek adlar.
DISPLAY_NAMES: dict[str, str] = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}


def to_code(language: str | None) -> str | None:
    """Whisper'ın bildirdiği dil adını iki harfli koda çevirir.

    Tanınmayan ad `None` döndürüyor: "bilmiyorum" ile "izinli değil" aynı
    şey değil, ama ikisi de düzeltmeyi tetiklemeli.
    """
    if not language:
        return None
    return _NAME_TO_CODE.get(language.strip().lower())


def is_allowed(language: str | None, allowed: tuple[str, ...]) -> bool:
    """Tespit edilen dil kullanıcının konuştuğu diller arasında mı?

    `allowed` boşsa denetim kapalı demektir; her şey kabul ediliyor.
    """
    if not allowed:
        return True
    code = to_code(language)
    return code is not None and code in allowed


def better(first: float | None, second: float | None) -> bool:
    """`first` güven skoru `second`'dan iyi mi?

    Bilinmeyen skor en kötü sayılıyor: elimizde ölçüm yokken bir sonucu
    diğerine tercih etmek için sebep de yok.
    """
    if first is None:
        return False
    if second is None:
        return True
    return first > second


def normalize(languages: object) -> tuple[str, ...]:
    """Ayarlardan gelen listeyi güvenli bir dil kodu demetine çevirir.

    Ayar dosyası kullanıcı tarafından elle düzenlenebiliyor; tanınmayan ya da
    bozuk girdilerin motoru düşürmesine izin vermiyoruz.
    """
    if not isinstance(languages, (list, tuple)):
        return DEFAULT_LANGUAGES
    kodlar = []
    for öge in languages:
        kod = to_code(öge) if isinstance(öge, str) else None
        if kod and kod not in kodlar:
            kodlar.append(kod)
    return tuple(kodlar)
