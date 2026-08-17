"""Otomatik değiştirme kuralları (Faz 7.8).

Bu modül kullanıcının metnini **doğrudan değiştiriyor**. Yanlış bir kural
sessizce yanlış metin üretir ve kullanıcı bunu ancak yapıştırdığı yerde
görür — belki hiç görmez.

Testlerin çoğu bu yüzden "bozmamalı" testleri.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omnivoice_engine.pipeline.replacements import (
    Replacement,
    ReplacementLibrary,
    apply_replacements,
)


def rules(*pairs: tuple[str, str], whole_word: bool = True) -> list[Replacement]:
    return [Replacement(find=f, replace=r, whole_word=whole_word) for f, r in pairs]


class TestTemelDegistirme:
    def test_basit_degistirme(self) -> None:
        result = apply_replacements("omni voice çalışıyor", rules(("omni voice", "OmniVoice")))
        assert result.text == "OmniVoice çalışıyor"
        assert result.applied == ("omni voice",)

    def test_buyuk_kucuk_harf_duyarsiz(self) -> None:
        """Whisper aynı adı farklı büyüklüklerde yazabiliyor."""
        result = apply_replacements("Omni Voice ve OMNI VOICE", rules(("omni voice", "OmniVoice")))
        assert result.text == "OmniVoice ve OmniVoice"

    def test_degisiklik_yoksa_applied_bos(self) -> None:
        result = apply_replacements("alakasız bir cümle", rules(("kod", "code")))
        assert not result.changed
        assert result.applied == ()

    def test_bos_metin(self) -> None:
        assert apply_replacements("", rules(("a", "b"))).text == ""

    def test_kuralsiz_metin_degismez(self) -> None:
        assert apply_replacements("metin", []).text == "metin"


class TestTurkceEkler:
    """Türkçe eklemeli; kelime sınırı ekleri kesmemeli."""

    @pytest.mark.parametrize(
        ("girdi", "beklenen"),
        [
            ("omni voice", "OmniVoice"),
            ("omni voice'u aç", "OmniVoice'u aç"),
            ("omni voice’u aç", "OmniVoice’u aç"),
        ],
    )
    def test_ekler_korunur(self, girdi: str, beklenen: str) -> None:
        result = apply_replacements(girdi, rules(("omni voice", "OmniVoice")))
        assert result.text == beklenen

    def test_ek_bitisik_yazilinca_da_korunur(self) -> None:
        result = apply_replacements("sql'i çalıştır", rules(("sql", "SQL")))
        assert result.text == "SQL'i çalıştır"


class TestBozmama:
    def test_kelime_ICINDE_degistirmez(self) -> None:
        """`kod` kuralı `kodlama`yı bozmamalı — sol sınır katı."""
        result = apply_replacements("mikrokod ve rekod", rules(("kod", "CODE")))
        assert result.text == "mikrokod ve rekod"

    @pytest.mark.parametrize(
        "metin",
        [
            "bu cümlede hiçbir kural yok",
            "sayılar 123 ve 456",
            "noktalama: virgül, nokta.",
        ],
    )
    def test_alakasiz_metin_bozulmaz(self, metin: str) -> None:
        result = apply_replacements(metin, rules(("omni voice", "OmniVoice"), ("sql", "SQL")))
        assert result.text == metin

    def test_kural_metni_regex_olarak_yorumlanmaz(self) -> None:
        """Kullanıcı `.` veya `(` yazarsa desen bozulmamalı."""
        result = apply_replacements(
            "fiyat 1.5 dolar", rules(("1.5", "1,5"), whole_word=False)
        )
        assert result.text == "fiyat 1,5 dolar"
        # Nokta joker olsaydı "125" gibi bir şeyi de yakalardı.
        assert apply_replacements("125 dolar", rules(("1.5", "X"), whole_word=False)).text == "125 dolar"


class TestSiralama:
    def test_uzun_kural_once_uygulanir(self) -> None:
        """Kısa kural uzun kuralın parçasını yerse ikincisi bir daha eşleşmez."""
        result = apply_replacements(
            "kod inceleme yap",
            rules(("kod", "CODE"), ("kod inceleme", "code review")),
        )
        assert result.text == "code review yap"

    def test_zincirleme_bagimsiz_kurallar(self) -> None:
        result = apply_replacements(
            "sql ve json", rules(("sql", "SQL"), ("json", "JSON"))
        )
        assert result.text == "SQL ve JSON"


class TestKutuphane:
    def test_ekleme_ve_kalicilik(self, tmp_path: Path) -> None:
        path = tmp_path / "r.json"
        assert ReplacementLibrary.load(path).add("omni voice", "OmniVoice")

        yeniden = ReplacementLibrary.load(path)
        assert yeniden.rules[0].find == "omni voice"
        assert yeniden.apply("omni voice").text == "OmniVoice"

    def test_ayni_kural_iki_kez_eklenmez(self, tmp_path: Path) -> None:
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        assert lib.add("sql", "SQL")
        assert not lib.add("SQL", "Sql")

    def test_birebir_ayni_kural_reddedilir(self, tmp_path: Path) -> None:
        """Gürültü: her diktede "uygulandı" der ama hiçbir şey değişmez."""
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        assert not lib.add("SQL", "SQL")

    def test_BUYUK_HARF_DUZELTMESI_kabul_edilir(self, tmp_path: Path) -> None:
        """`sql → SQL` bu özelliğin en yaygın kullanımı.

        Kendini değiştiren kural kontrolü harf katlamasıyla yapılsaydı bunu
        reddederdi — ilk yazımda tam olarak bu oldu.
        """
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        assert lib.add("sql", "SQL")
        assert lib.apply("sql sorgusu").text == "SQL sorgusu"

    def test_bos_arama_reddedilir(self, tmp_path: Path) -> None:
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        assert not lib.add("   ", "bir şey")

    def test_silme(self, tmp_path: Path) -> None:
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        lib.add("sql", "SQL")
        assert lib.remove("SQL")
        assert lib.rules == []

    def test_bozuk_dosya_dikteyi_durdurmaz(self, tmp_path: Path) -> None:
        path = tmp_path / "bozuk.json"
        path.write_text("{ bozuk", encoding="utf-8")
        assert ReplacementLibrary.load(path).rules == []

    def test_kullanim_sayaci(self, tmp_path: Path) -> None:
        lib = ReplacementLibrary.load(tmp_path / "r.json")
        lib.add("sql", "SQL")
        result = lib.apply("sql sorgusu")
        lib.mark_used(result.applied)
        assert lib.rules[0].used == 1
