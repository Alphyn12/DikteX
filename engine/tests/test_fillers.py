"""Dolgu temizlemenin sınırlarını sabitler.

En önemli testler silinenler değil, **silinmeyenler**: fazla agresif bir
temizleyici cümlenin anlamını bozar ve kullanıcı bunu ancak yanlış metni
yapıştırdıktan sonra fark eder.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.pipeline.fillers import strip_fillers


class TestSesler:
    """Kelime olmayan duraksama sesleri silinir."""

    @pytest.mark.parametrize(
        ("giris", "beklenen"),
        [
            ("Yarına kadar eee bitiremeyiz", "Yarına kadar bitiremeyiz"),
            ("Şu ııı dosyayı aç", "Şu dosyayı aç"),
            ("Bence mmm olabilir", "Bence olabilir"),
            ("Hmm tamam", "Tamam"),
            ("Bu uh zor", "Bu zor"),
        ],
    )
    def test_ses_silinir(self, giris: str, beklenen: str) -> None:
        assert strip_fillers(giris).text == beklenen

    def test_silinen_sayilir(self) -> None:
        sonuc = strip_fillers("eee bir ııı iki mmm üç")
        assert sonuc.removed_count == 3
        assert sonuc.changed

    def test_bastaki_ses_silinince_buyuk_harf_korunur(self) -> None:
        # "Şey," gitmez (kelime), ama "Eee, tamam" → "Tamam"
        assert strip_fillers("Eee, tamam").text == "Tamam"


class TestKorunanlar:
    """Anlamı taşıyan hiçbir şey silinmez — en kritik güvence."""

    @pytest.mark.parametrize(
        "cumle",
        [
            # Bağlama bağlı kelimeler yerelde silinmez; LLM katmanına bırakılır.
            "Şu şey nerede",
            "Yani sonuç olarak bitti",
            "İşte tam da bunu diyorum",
            "Hani şu mavi olan",
            # İçinde dolgu harfi geçen gerçek kelimeler bozulmaz.
            "Eeeğitim yanlış yazılmış olabilir",
            "Emmm firması aradı",
            # Türkçe anlamlı ikilemeler korunur.
            "Yavaş yavaş ilerliyoruz",
            "Az az yedi",
            "Çok çok teşekkürler",
        ],
    )
    def test_degistirilmez(self, cumle: str) -> None:
        assert strip_fillers(cumle).text == cumle

    def test_bos_metin(self) -> None:
        assert strip_fillers("").text == ""
        assert strip_fillers("   ").removed_count == 0


class TestTekrarlar:
    """Kekeleme kaynaklı kelime tekrarları tek kopyaya indirilir."""

    def test_ikili_tekrar(self) -> None:
        assert strip_fillers("Ben ben gidiyorum").text == "Ben gidiyorum"

    def test_uclu_tekrar(self) -> None:
        sonuc = strip_fillers("Bu bu bu olmaz")
        assert sonuc.text == "Bu olmaz"
        assert sonuc.removed_count == 2

    def test_buyuk_kucuk_harf_farki(self) -> None:
        assert strip_fillers("Ama ama olmaz").text == "Ama olmaz"


class TestNoktalama:
    """Silme sonrası artık noktalama bırakılmaz."""

    def test_virgul_artigi_temizlenir(self) -> None:
        # "hazırlayamayız eee, pazartesi" → önce " , " kalır, temizlenmeli
        assert strip_fillers("Hazırlayamayız eee, pazartesi").text == "Hazırlayamayız, pazartesi"

    def test_cift_bosluk_kalmaz(self) -> None:
        assert "  " not in strip_fillers("Bir eee iki").text

    def test_bastaki_virgul_kalmaz(self) -> None:
        assert not strip_fillers("eee, tamam").text.startswith(",")


class TestGercekOrnek:
    """Groq'un gerçekten döndürdüğü cümle (Faz 2 STT testinden)."""

    def test_tts_ciktisi(self) -> None:
        duyulan = "Şey, yarına kadar demoyu hazırlayamayız eee, pazartesi sabahı diyelim mi acaba?"
        sonuc = strip_fillers(duyulan)
        # "eee" gider, "Şey" kalır — bağlama bağlı olduğu için LLM'e bırakılır.
        assert "eee" not in sonuc.text
        assert sonuc.text.startswith("Şey,")
        assert "pazartesi sabahı" in sonuc.text
        assert sonuc.removed_count == 1
