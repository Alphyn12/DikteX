"""Sesli düzen komutları (Faz 7.10).

Bu özellikte yanlış pozitif, kaçırmaktan pahalı:

* **Kaçırılan komut** → kullanıcı Enter'a basar. Can sıkıcı ama görünür.
* **Yanlış tetiklenen komut** → cümle ikiye bölünür ve kullanıcı bunu ancak
  yapıştırdığı yerde fark eder, belki hiç fark etmez.

Testlerin çoğu bu yüzden "bölmemeli" testleri.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.pipeline.layout import apply_layout_commands


class TestKomutlar:
    def test_yeni_satir(self) -> None:
        result = apply_layout_commands("ilk cümle. yeni satır ikinci cümle")
        assert result.text == "ilk cümle.\nikinci cümle"
        assert result.applied == 1

    def test_yeni_paragraf(self) -> None:
        result = apply_layout_commands("giriş. yeni paragraf gelişme")
        assert result.text == "giriş.\n\ngelişme"

    def test_madde_isareti(self) -> None:
        result = apply_layout_commands("liste: madde işareti birinci konu")
        assert result.text == "liste:\n- birinci konu"

    def test_ingilizce_komutlar(self) -> None:
        """Kullanıcı iki dilde de dikte edebiliyor."""
        assert apply_layout_commands("first. new line second").text == "first.\nsecond"

    def test_ardisik_maddeler(self) -> None:
        result = apply_layout_commands(
            "plan: madde işareti tasarım. madde işareti kodlama. madde işareti test"
        )
        assert result.text == "plan:\n- tasarım.\n- kodlama.\n- test"
        assert result.applied == 3

    def test_uzun_ifade_once_eslesir(self) -> None:
        """"yeni paragraf" varken "paragraf" eşleşirse komut yanlış okunur."""
        result = apply_layout_commands("bir. yeni paragraf iki")
        assert result.text == "bir.\n\niki"


class TestBolmeme:
    @pytest.mark.parametrize(
        "metin",
        [
            "dosyaya yeni satır ekledim",
            "buraya yeni madde eklemek gerekiyor",
            "bu paragraf çok uzun olmuş",
            "kod içine bullet point koymuşlar",
        ],
    )
    def test_cumle_ICINDEKI_kullanim_komut_degil(self, metin: str) -> None:
        """En önemli testler.

        "yeni satır ekledim" bir komut değil, cümlenin parçası. Bölersek
        kullanıcı cümlesinin ikiye ayrıldığını yapıştırınca görür.
        """
        result = apply_layout_commands(metin)
        assert result.text == metin
        assert result.applied == 0

    @pytest.mark.parametrize(
        "metin",
        [
            "bugün hava güzel",
            "kod incelemesi yapalım",
            "",
        ],
    )
    def test_komutsuz_metin_degismez(self, metin: str) -> None:
        assert apply_layout_commands(metin).text == metin.rstrip()

    def test_zaten_satir_sonu_olan_bozulmaz(self) -> None:
        metin = "birinci satır\nikinci satır"
        assert apply_layout_commands(metin).text == metin


class TestTemizlik:
    def test_bastaki_komut_bosluk_birakmaz(self) -> None:
        result = apply_layout_commands("yeni satır metin başlıyor")
        assert result.text == "metin başlıyor"

    def test_ust_uste_paragraf_ikiye_iner(self) -> None:
        result = apply_layout_commands("bir. yeni paragraf. yeni paragraf iki")
        assert "\n\n\n" not in result.text

    def test_sondaki_bosluk_kirpilir(self) -> None:
        assert apply_layout_commands("metin. yeni satır").text == "metin."


class TestTurkceHarfler:
    def test_buyuk_harfli_komut_calisir(self) -> None:
        result = apply_layout_commands("Bitti. Yeni Satır Devam")
        assert result.text == "Bitti.\nDevam"

    def test_madde_isareti_buyuk_I(self) -> None:
        """Türkçe İ küçültme tuzağı — `.lower()` tek başına yetmiyor."""
        result = apply_layout_commands("liste: MADDE İŞARETİ konu")
        assert result.applied == 1

    @pytest.mark.parametrize(
        "metin",
        [
            "liste: madde isareti konu",
            "bitti. yeni satir devam",
            "giris. yeni paragraf gelisme",
        ],
    )
    def test_AKSANSIZ_yazim_da_eslesir(self, metin: str) -> None:
        """Konuşma tanıma bazen aksansız yazıyor.

        Ölçtük: `re.IGNORECASE` Türkçe İ'yi doğru katlıyor ama ş/s, ı/i
        çiftlerini elbette eşleştirmiyor. Aksansız komutu kaçırmak
        kullanıcıya "bu özellik bazen çalışıyor" hissi verirdi.
        """
        assert apply_layout_commands(metin).applied == 1
