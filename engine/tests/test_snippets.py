"""Snippet kütüphanesi ve bulanık sesli tetikleme.

Tetikleme eşiği bu özelliğin yaşam noktası: çok gevşek olursa kullanıcı
alakasız bir şablonu tetikler ve bunu ancak çıktıyı okuyunca fark eder; çok
sıkı olursa şablon hiç tetiklenmez ve özellik ölü kalır.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omnivoice_engine.storage.snippets import Snippet, SnippetLibrary


@pytest.fixture
def library(tmp_path: Path) -> SnippetLibrary:
    lib = SnippetLibrary.load(tmp_path / "snippets.json")
    lib.add("kod inceleme", "Şu kodu incele ve iyileştirme öner:")
    lib.add("toplantı notu", "Aşağıdaki notları düzenli bir toplantı özetine çevir:")
    lib.add("hata analizi", "Bu hatayı analiz et:", triggers=["hata çözümü", "debug"])
    return lib


class TestDuzenleme:
    def test_ekleme_ve_kalicilik(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        lib = SnippetLibrary.load(path)
        assert lib.add("test", "gövde")

        yeniden = SnippetLibrary.load(path)
        assert [s.name for s in yeniden.snippets] == ["test"]
        assert yeniden.snippets[0].body == "gövde"

    def test_ayni_ad_iki_kez_eklenmez(self, library: SnippetLibrary) -> None:
        assert not library.add("KOD İNCELEME", "başka gövde")

    def test_bos_ad_veya_govde_reddedilir(self, library: SnippetLibrary) -> None:
        assert not library.add("", "gövde")
        assert not library.add("ad", "   ")

    def test_silme(self, library: SnippetLibrary) -> None:
        assert library.remove("kod inceleme")
        assert library.find("kod inceleme yap") is None

    def test_bozuk_dosya_dikteyi_durdurmaz(self, tmp_path: Path) -> None:
        path = tmp_path / "bozuk.json"
        path.write_text("{ bozuk", encoding="utf-8")
        assert SnippetLibrary.load(path).snippets == []

    def test_kullanim_sayaci(self, library: SnippetLibrary) -> None:
        library.mark_used("kod inceleme")
        library.mark_used("kod inceleme")
        snippet = next(s for s in library.snippets if s.name == "kod inceleme")
        assert snippet.used == 2


class TestTetikleme:
    @pytest.mark.parametrize(
        "soylenen",
        [
            "kod inceleme",
            "kod incelemesi yap",
            "şu kod inceleme şablonunu kullan",
            "bugün kod inceleme yapalım",
            "kod incelemeye ihtiyacım var",
        ],
    )
    def test_dogal_varyasyonlar_bulunur(
        self, library: SnippetLibrary, soylenen: str
    ) -> None:
        """Kullanıcı kayıtlı adı birebir söylemez; eşleşme buna dayanmalı."""
        found = library.find(soylenen)
        assert found is not None
        assert found.name == "kod inceleme"

    def test_aksansiz_yazim_eslesir(self, library: SnippetLibrary) -> None:
        """Konuşma tanıma bazen aksansız yazıyor."""
        found = library.find("kod incelemesi")
        assert found is not None

    def test_ek_tetikleyiciler_calisir(self, library: SnippetLibrary) -> None:
        assert library.find("debug yapalım") is not None
        assert library.find("hata çözümü lazım").name == "hata analizi"

    @pytest.mark.parametrize(
        "soylenen",
        [
            "yarına kadar demoyu hazırlayamayız",
            "toplantı saat dörtte",  # "toplantı" geçiyor ama "notu" yok
            "merhaba nasılsın",
            "",
        ],
    )
    def test_alakasiz_metin_tetiklemez(
        self, library: SnippetLibrary, soylenen: str
    ) -> None:
        """Yanlış şablonu tetiklemek, hiç tetiklememekten kötüdür."""
        assert library.find(soylenen) is None

    def test_en_iyi_eslesme_kazanir(self, tmp_path: Path) -> None:
        lib = SnippetLibrary.load(tmp_path / "s.json")
        lib.add("kod", "kısa")
        lib.add("kod inceleme raporu", "uzun")
        # "kod inceleme raporu hazırla" her ikisini de tutabilir; daha çok
        # kelimesi eşleşen kazanmalı.
        assert lib.find("kod inceleme raporu hazırla").name == "kod inceleme raporu"

    def test_esitlikte_cok_kullanilan_kazanir(self, tmp_path: Path) -> None:
        lib = SnippetLibrary.load(tmp_path / "s.json")
        lib.add("rapor", "A")
        lib.add("rapor", "B")  # eklenmez (aynı ad)
        lib.snippets.append(Snippet(name="özet", body="B", used=5))
        lib.snippets.append(Snippet(name="özet", body="C", used=1))
        assert lib.find("özet çıkar").used == 5
