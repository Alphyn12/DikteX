"""Öğrenen kişisel stil (Faz 3.13).

İki şey sınanıyor:

1. **Baştan yazmanın elenmesi.** Kullanıcı çıktıyı atıp yeniden yazdıysa bu
   bir stil tercihi değil, çıktının reddi; örnek olarak vermek modele yanlış
   hedef gösterir. Eşik ölçülen gerçek düzenlemelerden seçildi ve `OLCULEN`
   tablosu onu sabitliyor.

2. **Kapalıyken hiçbir şey saklanmaması.** Bu özellik geçmiş dikte içeriğini
   yeni isteklere taşıyor; kapalıyken sızıntı olmamalı.

Daha ince bir ayrım (yazım hatası ile ufak üslup tercihi) denendi ve
yapılamadı; `test_ONEMSIZ_duzenleme_de_saklanir` bunu bilinçli bir kabul
olarak kayda geçiriyor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omnivoice_engine.pipeline.style import (
    MAX_LENGTH,
    MAX_PROMPT_EXAMPLES,
    MAX_STORED,
    MIN_WORD_SIMILARITY,
    StyleLibrary,
    build_style_block,
    is_style_signal,
    similarity,
)

#: Gerçek pre-flight düzenlemeleri ve ölçülen kelime benzerlikleri.
#: Eşik bu tablodan seçildi; tablo değişirse eşik yeniden değerlendirilmeli.
OLCULEN = [
    (
        "baştan yazma",
        "Toplantı yarın saat ondadır ve tüm ekip katılacaktır.",
        "Bambaşka bir konu hakkında tamamen farklı bir cümle yazıyorum.",
        0.105,
        False,
    ),
    (
        "agresif kısaltma",
        "Bu özelliği eklemek için öncelikle bir araştırma yapmamız gerekiyor.",
        "Önce araştırma yapmalıyız.",
        0.286,
        True,
    ),
    (
        "kısa kısaltma",
        "Bu sohbet için uzun bir cümledir ve düzeltilecektir efendim.",
        "SOHBET kısa cümle efendim.",
        0.400,
        True,
    ),
    (
        "resmiden samimiye",
        "Merhaba, umarım iyisinizdir. Size bir konuda yazmak istiyorum.",
        "Selam, bir konuda yazmak istiyorum.",
        0.667,
        True,
    ),
    (
        "ek düşürme",
        "Toplantı yarın saat onda başlayacaktır ve tüm ekip katılacaktır.",
        "Toplantı yarın saat onda başlayacak ve tüm ekip katılacaktır.",
        0.900,
        True,
    ),
]


class TestSinyalSecimi:
    @pytest.mark.parametrize(
        ("ad", "before", "after", "beklenen_oran", "kabul"), OLCULEN
    )
    def test_olculen_vakalar(
        self, ad: str, before: str, after: str, beklenen_oran: float, kabul: bool
    ) -> None:
        """Eşik bu ölçümlerden seçildi; sapma olursa eşik yeniden bakılmalı."""
        oran = similarity(before, after)
        assert abs(oran - beklenen_oran) < 0.02, f"{ad}: {oran:.3f}"
        assert is_style_signal(before, after) is kabul, ad

    def test_esik_olculen_araligin_icinde(self) -> None:
        """Eşik, reddedilen ile kabul edilen en yakın vakanın arasında olmalı."""
        assert 0.105 < MIN_WORD_SIMILARITY < 0.286

    def test_degismemis_metin_sinyal_degil(self) -> None:
        assert not is_style_signal("aynı metin", "aynı metin")

    def test_bos_metin_sinyal_degil(self) -> None:
        assert not is_style_signal("", "bir şey")
        assert not is_style_signal("bir şey", "  ")

    def test_ONEMSIZ_duzenleme_de_saklanir(self) -> None:
        """Bu bilinçli bir kabul, kusur değil.

        Yazım hatası düzeltmesi ile ufak bir üslup tercihini ayırmak denendi
        ve yapılamadı: "başlayacaktır → başlayacak" bir üslup sinyali ama
        yazım düzeltmesiyle aynı bölgede. Önemsiz bir örneği saklamak zararsız
        (birkaç jeton); asıl güvence, saklananların arayüzde görünüp
        silinebilmesi.
        """
        uzun = "Bu cümle yeterince uzun olsun ki oran yüksek kalsın efendim."
        assert is_style_signal(uzun, uzun + "!")

    def test_cok_uzun_metin_saklanmaz(self) -> None:
        uzun = "a" * (MAX_LENGTH + 1)
        assert not is_style_signal(uzun, uzun + "b")

    def test_benzerlik_olcusu_makul(self) -> None:
        assert similarity("aynı", "aynı") == 1.0
        assert similarity("abc", "xyz") < 0.2

    def test_benzerlik_KELIME_duzeyinde(self) -> None:
        """Karakter düzeyi yetmiyordu: yazım hatası (0.985) ile ek düşürme
        (0.976) aynı bölgeye düşüyordu."""
        # Kelime düzeyinde tek kelime farkı, karakter düzeyinden çok daha
        # düşük bir oran veriyor.
        assert similarity("bir iki üç", "bir iki dört") < 0.9


class TestKapaliyken:
    def test_kapaliyken_HICBIR_SEY_saklanmaz(self, tmp_path: Path) -> None:
        """Bu özellik geçmiş içeriği yeni isteklere taşıyor; sızıntı olmamalı."""
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=False)
        assert not lib.observe(
            "Merhaba, umarım iyisinizdir. Size bir konuda yazıyorum.",
            "Selam, bir konuda yazıyorum.",
        )
        assert lib.examples == []

    def test_kapaliyken_isteme_metin_eklenmez(self, tmp_path: Path) -> None:
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=True)
        lib.observe(
            "Merhaba, umarım iyisinizdir. Size bir konuda yazıyorum.",
            "Selam, bir konuda yazıyorum.",
        )
        assert lib.prompt_block() != ""

        lib.enabled = False
        assert lib.prompt_block() == ""


class TestSaklama:
    @pytest.fixture
    def lib(self, tmp_path: Path) -> StyleLibrary:
        return StyleLibrary.load(tmp_path / "s.json", enabled=True)

    def test_ornek_saklanir_ve_kalici(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        lib = StyleLibrary.load(path, enabled=True)
        assert lib.observe(
            "Merhaba, umarım iyisinizdir. Size bir konuda yazıyorum.",
            "Selam, bir konuda yazıyorum.",
        )

        yeniden = StyleLibrary.load(path, enabled=True)
        assert len(yeniden.examples) == 1
        assert yeniden.examples[0].after == "Selam, bir konuda yazıyorum."

    def test_ayni_duzeltme_tekrar_gelirse_yenisi_kalir(self, lib: StyleLibrary) -> None:
        before = "Merhaba, umarım iyisinizdir. Size bir konuda yazıyorum."
        lib.observe(before, "Selam, bir konuda yazıyorum.")
        lib.observe(before, "Selam, şu konuda yazıyorum.")
        assert len(lib.examples) == 1
        assert lib.examples[0].after == "Selam, şu konuda yazıyorum."

    def test_sayi_siniri_asilmaz(self, lib: StyleLibrary) -> None:
        for index in range(MAX_STORED + 10):
            lib.observe(
                f"Bu {index} numaralı uzun bir cümledir ve düzeltilecektir efendim.",
                f"Bu {index} numaralı kısa cümledir efendim.",
            )
        assert len(lib.examples) == MAX_STORED

    def test_temizleme(self, lib: StyleLibrary) -> None:
        lib.observe(
            "Merhaba, umarım iyisinizdir. Size bir konuda yazıyorum.",
            "Selam, bir konuda yazıyorum.",
        )
        assert lib.clear() == 1
        assert lib.examples == []

    def test_bozuk_dosya_dikteyi_durdurmaz(self, tmp_path: Path) -> None:
        path = tmp_path / "bozuk.json"
        path.write_text("{ bozuk", encoding="utf-8")
        assert StyleLibrary.load(path, enabled=True).examples == []


class TestIstemMetni:
    def test_bos_liste_bos_metin(self) -> None:
        assert build_style_block([]) == ""

    def test_en_fazla_bes_ornek(self, tmp_path: Path) -> None:
        """Her örnek girdi jetonu; dikte başına maliyeti artırıyor."""
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=True)
        for index in range(MAX_PROMPT_EXAMPLES + 5):
            lib.observe(
                f"Bu {index} numaralı uzun bir cümledir ve düzeltilecektir efendim.",
                f"Bu {index} numaralı kısa cümledir efendim.",
            )
        block = lib.prompt_block()
        assert block.count("Senin yazdığın:") == MAX_PROMPT_EXAMPLES

    def test_EN_YENI_EN_SONDA(self, tmp_path: Path) -> None:
        """Modeller sona yakın olana daha çok ağırlık veriyor."""
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=True)
        lib.observe(
            "Bu eski numaralı uzun bir cümledir ve düzeltilecektir efendim.",
            "Bu ESKI numaralı kısa cümledir efendim.",
        )
        lib.observe(
            "Bu yeni numaralı uzun bir cümledir ve düzeltilecektir efendim.",
            "Bu YENI numaralı kısa cümledir efendim.",
        )
        block = lib.prompt_block()
        assert block.index("ESKI") < block.index("YENI")

    def test_mod_eslesen_ornekler_tercih_edilir(self, tmp_path: Path) -> None:
        """Kod modundaki tercihler sohbet modunda yanlış hedef gösterir."""
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=True)
        lib.observe(
            "Bu sohbet için uzun bir cümledir ve düzeltilecektir efendim.",
            "Bu SOHBET için kısa cümledir efendim.",
            mode="quick",
        )
        lib.observe(
            "Bu kod için uzun bir cümledir ve düzeltilecektir efendim.",
            "Bu KOD için kısa cümledir efendim.",
            mode="code",
        )
        block = lib.prompt_block(mode="code")
        assert "KOD" in block
        assert "SOHBET" not in block

    def test_mod_eslesmezse_hepsi_kullanilir(self, tmp_path: Path) -> None:
        """Boş bir stil bloğu vermektense elde olanı vermek daha iyi."""
        lib = StyleLibrary.load(tmp_path / "s.json", enabled=True)
        lib.observe(
            "Bu sohbet için uzun bir cümledir ve düzeltilecektir efendim.",
            "Bu SOHBET için kısa cümledir efendim.",
            mode="quick",
        )
        assert "SOHBET" in lib.prompt_block(mode="sql")
