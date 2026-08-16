"""Biçimlendirilmiş yapıştırma dönüşümleri.

Bu dönüşümler kullanıcının metnini değiştiriyor; bir hata sessizce yanlış
içerik yapıştırır. En kritik testler "ne kaybolmamalı" testleri.
"""

from __future__ import annotations

import json

import pytest

from omnivoice_engine.output.formats import (
    PasteFormat,
    apply_format,
    detect_format,
    markdown_to_html,
    markdown_to_plain,
)


class TestBicimTespiti:
    @pytest.mark.parametrize(
        ("komut", "beklenen"),
        [
            ("bunu json olarak yapıştır", PasteFormat.JSON_STRING),
            ("json'a çevir", PasteFormat.JSON_STRING),
            ("html olarak ver", PasteFormat.HTML),
            ("markdown biçiminde yaz", PasteFormat.MARKDOWN),
            ("düz metin olarak yapıştır", PasteFormat.PLAIN_FROM_MARKDOWN),
            ("duz metin istiyorum", PasteFormat.PLAIN_FROM_MARKDOWN),
            ("kod bloğu içine al", PasteFormat.CODE_BLOCK),
            ("kod blogu yap", PasteFormat.CODE_BLOCK),
        ],
    )
    def test_taninan_bicimler(self, komut: str, beklenen: PasteFormat) -> None:
        assert detect_format(komut) is beklenen

    @pytest.mark.parametrize(
        "komut",
        [
            "yarına kadar demoyu hazırlayamayız",
            "toplantı saat dörtte",
            "şu kodu düzelt",
        ],
    )
    def test_bicim_belirtilmemis(self, komut: str) -> None:
        assert detect_format(komut) is None


class TestMarkdownDuzMetin:
    def test_basliklar_temizlenir(self) -> None:
        assert markdown_to_plain("## Başlık\nmetin") == "Başlık\nmetin"

    def test_liste_isaretleri_temizlenir(self) -> None:
        assert markdown_to_plain("- bir\n- iki") == "bir\niki"

    def test_kalin_ve_italik(self) -> None:
        assert markdown_to_plain("**kalın** ve *italik*") == "kalın ve italik"

    def test_satir_ici_kod(self) -> None:
        assert markdown_to_plain("`kod` çalışır") == "kod çalışır"

    def test_baglanti_adresi_KAYBOLMAZ(self) -> None:
        """Yalnız metni bırakmak adresi kaybettirirdi ve kullanıcı fark etmezdi."""
        assert markdown_to_plain("[siteye](https://a.com) bak") == "siteye (https://a.com) bak"

    def test_kod_blogu_icerigi_korunur(self) -> None:
        result = markdown_to_plain("```python\nprint(1)\n```")
        assert "print(1)" in result
        assert "```" not in result

    def test_carpma_isareti_italik_sanilmaz(self) -> None:
        assert markdown_to_plain("3 * 4 * 5") == "3 * 4 * 5"

    @pytest.mark.parametrize(
        "metin",
        [
            "my_var_name kullan",
            "snake_case ve CONSTANT_NAME",
            "__init__ metodu",
            "a_b_c_d_e",
        ],
    )
    def test_alt_cizgili_kod_adlari_bozulmaz(self, metin: str) -> None:
        """Kelime içindeki `_` vurgu değildir — Markdown kuralı da bu.

        Bunu kaçırmak `my_var_name` → `myvarname` yapıyordu; bir geliştirici
        aracında sessiz veri bozulması demek.
        """
        assert markdown_to_plain(metin) == metin

    def test_gercek_alt_cizgi_italigi_calisir(self) -> None:
        """Kelime sınırındaki `_` hâlâ vurgu sayılmalı."""
        assert markdown_to_plain("bu _vurgulu_ kelime") == "bu vurgulu kelime"

    def test_gercek_alt_cizgi_kalini_calisir(self) -> None:
        """Boşluk içeren `__...__` gerçek kalın metindir, dunder değil."""
        assert markdown_to_plain("__önemli not__ burada") == "önemli not burada"


class TestJsonDizesi:
    def test_tirnaklar_kacislanir(self) -> None:
        result = apply_format('o "dedi" ki', PasteFormat.JSON_STRING)
        assert json.loads(result) == 'o "dedi" ki'

    def test_satir_sonu_kacislanir(self) -> None:
        result = apply_format("bir\niki", PasteFormat.JSON_STRING)
        assert "\\n" in result
        assert json.loads(result) == "bir\niki"

    def test_turkce_karakterler_korunur(self) -> None:
        """`ensure_ascii=False` olmasaydı 'ş' yerine \\u015f yazardı."""
        result = apply_format("şiğüöç", PasteFormat.JSON_STRING)
        assert "şiğüöç" in result
        assert json.loads(result) == "şiğüöç"


class TestHtml:
    def test_baslik(self) -> None:
        assert "<h2>Başlık</h2>" in markdown_to_html("## Başlık")

    def test_liste(self) -> None:
        result = markdown_to_html("- bir\n- iki")
        assert "<ul>" in result and result.count("<li>") == 2

    def test_kalin_ve_baglanti(self) -> None:
        result = markdown_to_html("**kalın** ve [bağ](https://a.com)")
        assert "<strong>kalın</strong>" in result
        assert '<a href="https://a.com">bağ</a>' in result

    def test_html_kacislanir(self) -> None:
        """Kullanıcı metnindeki < > işaretleri etiket sanılmamalı."""
        result = markdown_to_html("a < b ve c > d")
        assert "&lt;" in result and "&gt;" in result


class TestKodBlogu:
    def test_sarmalanir(self) -> None:
        assert apply_format("print(1)", PasteFormat.CODE_BLOCK) == "```\nprint(1)\n```"

    def test_icerikte_cit_varsa_uzatilir(self) -> None:
        """Metin zaten ``` içeriyorsa dış çit daha uzun olmalı, yoksa blok bozulur."""
        result = apply_format("```\nkod\n```", PasteFormat.CODE_BLOCK)
        assert result.startswith("````")
        assert result.endswith("````")


class TestDegismezlik:
    def test_plain_dokunmaz(self) -> None:
        metin = "## Başlık\n- madde"
        assert apply_format(metin, PasteFormat.PLAIN) == metin

    def test_markdown_dokunmaz(self) -> None:
        metin = "**kalın**"
        assert apply_format(metin, PasteFormat.MARKDOWN) == metin

    def test_bos_metin(self) -> None:
        for fmt in PasteFormat:
            apply_format("", fmt)  # hata yükseltmemeli
