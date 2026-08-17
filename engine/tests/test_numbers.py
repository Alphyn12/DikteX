"""Türkçe sayı normalizasyonu (Faz 7.9).

Bu modül kullanıcının metnini değiştiriyor, yani yanlış bir dönüşüm sessizce
yanlış bir sayı üretir — bir belgede ya da kodda bunun bedeli yüksek.

Testler iki şeyi koruyor: doğru sayılar doğru çevrilsin, **sayı olmayan hiçbir
şeye dokunulmasın**. İkincisi daha kritik, çünkü Türkçe'de sayı kelimeleri
günlük dilde sayı olmayan anlamlarda da geçiyor.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.pipeline.numbers import normalize_numbers


class TestBasitSayilar:
    @pytest.mark.parametrize(
        ("girdi", "beklenen"),
        [
            ("iki", "2"),
            ("on", "10"),
            ("on beş", "15"),
            ("yirmi üç", "23"),
            ("doksan dokuz", "99"),
        ],
    )
    def test_birler_ve_onlar(self, girdi: str, beklenen: str) -> None:
        assert normalize_numbers(girdi) == beklenen


class TestCarpanlar:
    @pytest.mark.parametrize(
        ("girdi", "beklenen"),
        [
            ("yüz", "100"),
            ("yüz elli", "150"),
            ("iki yüz otuz beş", "235"),
            ("bin", "1000"),
            ("iki bin yirmi altı", "2026"),
            ("bin dokuz yüz doksan", "1990"),
            ("üç milyon", "3000000"),
            ("bir milyar", "1000000000"),
        ],
    )
    def test_carpanli_sayilar(self, girdi: str, beklenen: str) -> None:
        """Çarpan kendinden önceki sayıyı çarpar; yoksa 1 varsayılır."""
        assert normalize_numbers(girdi) == beklenen


class TestCumleIcinde:
    @pytest.mark.parametrize(
        ("girdi", "beklenen"),
        [
            ("on beş dakika sürdü", "15 dakika sürdü"),
            ("toplantı iki bin yirmi altı yılında", "toplantı 2026 yılında"),
            ("yirmi üç ve kırk beş", "23 ve 45"),
            ("fiyat üç yüz lira", "fiyat 300 lira"),
        ],
    )
    def test_cumle_icinde_dogru_calisir(self, girdi: str, beklenen: str) -> None:
        assert normalize_numbers(girdi) == beklenen

    def test_noktalama_korunur(self) -> None:
        assert normalize_numbers("on beş, yirmi.") == "15, 20."


class TestDokunmama:
    """Sayı olmayanı bozmak, sayıyı çevirmemekten kötü."""

    def test_TEK_BASINA_BIR_artikel_sayilir(self) -> None:
        """"bir kahve" → "1 kahve" yapmak metni bozar."""
        assert normalize_numbers("bir kahve alayım") == "bir kahve alayım"

    def test_bir_baska_sayiyla_birlikte_sayidir(self) -> None:
        assert normalize_numbers("bir milyon") == "1000000"
        assert normalize_numbers("yirmi bir") == "21"

    @pytest.mark.parametrize(
        "metin",
        [
            "bugün hava güzel",
            "merhaba nasılsın",
            "kod incelemesi yapalım",
            "",
        ],
    )
    def test_sayisiz_metin_degismez(self, metin: str) -> None:
        assert normalize_numbers(metin) == metin

    def test_zaten_rakam_olan_dokunulmaz(self) -> None:
        assert normalize_numbers("15 dakika") == "15 dakika"

    @pytest.mark.parametrize(
        "metin",
        [
            "birinci gün",
            "ikinci sırada",
            "yarım saat",
            "çeyrek altın",
        ],
    )
    def test_sira_sayilari_ve_kesirler_KAPSAM_DISI(self, metin: str) -> None:
        """Bunlar cümlede sıfat; rakama çevirmek metni bozar.

        "birinci gün" ile "1. gün" aynı şey değil ve kullanıcının hangisini
        istediği belli değil.
        """
        assert normalize_numbers(metin) == metin

    def test_kelime_icindeki_sayi_kelimesi_bozulmaz(self) -> None:
        """"onay" içindeki "on" sayı değil."""
        assert normalize_numbers("onay verdi") == "onay verdi"
        assert normalize_numbers("birlikte gidelim") == "birlikte gidelim"


class TestBuyukHarf:
    def test_cumle_basindaki_sayi(self) -> None:
        assert normalize_numbers("On beş kişi geldi") == "15 kişi geldi"
