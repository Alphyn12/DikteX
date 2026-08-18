"""Dil tespiti düzeltmesi.

Kullanıcı Türkçe konuşurken Whisper dili **İzlandaca** sandı ve metni öyle
çözümledi:

    Halló, það er hljóð. Einn, tvö, þrír, tilraun er í gangi...

Metin kaybolmadı ama tamamen kullanılamaz hâle geldi. Dili sabitlemek çözüm
değil: kullanıcı hem Türkçe hem İngilizce dikte ediyor.

Buradaki testler düzeltmenin **ne zaman devreye girdiğini** ve daha da
önemlisi **ne zaman girmediğini** sabitliyor. Gereksiz tetiklenen bir
düzeltme her diktede iki ekstra API çağrısı demek olurdu.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.providers import ProviderError, ProviderInfo, PrivacyClass, Transcript, Usage
from omnivoice_engine.stt.language import DEFAULT_LANGUAGES, is_allowed, normalize, to_code
from omnivoice_engine.stt.router import SttRouter


def klip(saniye: float = 2.0) -> AudioClip:
    import numpy as np

    örnek = int(16000 * saniye)
    return AudioClip(samples=np.zeros(örnek, dtype="float32"), sample_rate=16000)


class SahteStt:
    """Dile göre farklı sonuç veren sağlayıcı.

    Gerçek Whisper'ın ölçülen davranışını taklit ediyor: dil verilmezse
    yanılabiliyor, doğru dil verildiğinde güven skoru belirgin yükseliyor.
    """

    def __init__(self, sonuçlar: dict[str | None, tuple[str, str, float | None]]) -> None:
        self.sonuçlar = sonuçlar
        self.çağrılar: list[str | None] = []

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="sahte", privacy=PrivacyClass.PRIVATE, models=["test"])

    def is_available(self) -> bool:
        return True

    async def transcribe(self, clip, *, language=None, vocabulary=None):  # noqa: ANN001
        self.çağrılar.append(language)
        if language not in self.sonuçlar:
            raise ProviderError("sahte", f"{language} için sonuç tanımlı değil")
        metin, dil, güven = self.sonuçlar[language]
        return Transcript(
            text=metin,
            language=dil,
            model="test",
            provider="sahte",
            usage=Usage(latency_ms=1, cost_usd=None, audio_seconds=2.0),
            confidence=güven,
        )


# ── Dil kodu eşlemesi ─────────────────────────────────────────────────────


def test_whisper_dil_adları_koda_çevriliyor() -> None:
    assert to_code("Turkish") == "tr"
    assert to_code("English") == "en"
    # Büyük/küçük harf ve boşluk fark etmemeli: ad sağlayıcıdan geliyor.
    assert to_code("  turkish ") == "tr"


def test_tanınmayan_dil_izinli_sayılmıyor() -> None:
    """İzlandaca eşlemede yok; tam da düzeltilmesi gereken durum bu."""
    assert to_code("Icelandic") is None
    assert not is_allowed("Icelandic", ("tr", "en"))


def test_boş_liste_denetimi_kapatıyor() -> None:
    """Kullanıcı hiçbir dil seçmediyse eski davranış: her şey kabul."""
    assert is_allowed("Icelandic", ())


def test_bozuk_ayar_varsayılana_düşüyor() -> None:
    """Ayar dosyası elle düzenlenebiliyor; motoru düşürmemeli."""
    assert normalize(None) == DEFAULT_LANGUAGES
    assert normalize("tr") == DEFAULT_LANGUAGES
    assert normalize(["tr", "tr", "Turkish"]) == ("tr",)
    assert normalize(["uydurma"]) == ()


# ── Düzeltme davranışı ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_izlandaca_tespit_türkçeye_düzeltiliyor() -> None:
    sağlayıcı = SahteStt(
        {
            None: ("Halló, það er hljóð.", "Icelandic", -0.62),
            "tr": ("Merhaba, ses geliyor.", "Turkish", -0.13),
            "en": ("Hello there is sound.", "English", -0.91),
        }
    )
    router = SttRouter([sağlayıcı], languages=("tr", "en"))

    sonuç = await router.transcribe(klip())

    assert sonuç.language == "Turkish"
    assert sonuç.text == "Merhaba, ses geliyor."
    # Otomatik + iki dil denemesi.
    assert sağlayıcı.çağrılar == [None, "tr", "en"]


@pytest.mark.asyncio
async def test_izin_verilen_dil_tespit_edilirse_ek_çağrı_yok() -> None:
    """En önemli test: normal akış pahalanmamalı.

    Düzeltme her diktede tetiklenseydi her kayıt iki ekstra API çağrısı
    ederdi — gecikme de maliyet de üç katına çıkardı.
    """
    sağlayıcı = SahteStt({None: ("Merhaba dünya.", "Turkish", -0.14)})
    router = SttRouter([sağlayıcı], languages=("tr", "en"))

    sonuç = await router.transcribe(klip())

    assert sonuç.text == "Merhaba dünya."
    assert sağlayıcı.çağrılar == [None]


@pytest.mark.asyncio
async def test_ingilizce_konuşma_türkçeye_zorlanmıyor() -> None:
    """Kullanıcı iki dil de konuşuyor; düzeltme birini dayatmamalı."""
    sağlayıcı = SahteStt({None: ("Simplify this function.", "English", -0.26)})
    router = SttRouter([sağlayıcı], languages=("tr", "en"))

    sonuç = await router.transcribe(klip())

    assert sonuç.language == "English"
    assert sağlayıcı.çağrılar == [None]


@pytest.mark.asyncio
async def test_çağıran_dili_verdiyse_düzeltme_yapılmıyor() -> None:
    """Toplantı boru hattı dili açıkça veriyor; kararına karışmıyoruz."""
    sağlayıcı = SahteStt({"en": ("Hello.", "English", -0.2)})
    router = SttRouter([sağlayıcı], languages=("tr",))

    sonuç = await router.transcribe(klip(), language="en")

    assert sonuç.text == "Hello."
    assert sağlayıcı.çağrılar == ["en"]


@pytest.mark.asyncio
async def test_güven_skoru_yoksa_ilk_deneme_seçiliyor() -> None:
    """Sağlayıcı `avg_logprob` bildirmiyorsa sıralama tek ölçüt kalıyor.

    Uydurma bir skor üretmek yerine ilk başarılı denemeyi kullanıyoruz.
    """
    sağlayıcı = SahteStt(
        {
            None: ("bilinmeyen", "Icelandic", None),
            "tr": ("Türkçe metin", "Turkish", None),
            "en": ("English text", "English", None),
        }
    )
    router = SttRouter([sağlayıcı], languages=("tr", "en"))

    sonuç = await router.transcribe(klip())

    assert sonuç.text == "Türkçe metin"


@pytest.mark.asyncio
async def test_düzeltme_denemeleri_de_başarısızsa_ilk_sonuç_korunuyor() -> None:
    """Kötü bir metin, hiç metin olmamasından iyidir.

    Kullanıcı konuştu; elimizdekini vermek en azından panoya bir şey koyuyor.
    """
    sağlayıcı = SahteStt({None: ("Halló", "Icelandic", -0.6)})
    router = SttRouter([sağlayıcı], languages=("tr", "en"))

    sonuç = await router.transcribe(klip())

    assert sonuç.text == "Halló"
    assert sağlayıcı.çağrılar == [None, "tr", "en"]
