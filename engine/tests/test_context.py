"""Bağlam katmanı: uygulama profilleri, değişkenler, modlar ve sözlük."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from omnivoice_engine.context.apps import (
    PROFILE_INSTRUCTIONS,
    OutputProfile,
    profile_for,
)
from omnivoice_engine.context.selection import truncate_selection
from omnivoice_engine.context.variables import (
    VariableContext,
    inject,
    mentions_selection,
)
from omnivoice_engine.pipeline.modes import MODES, ModeId, get_mode, mode_for_chord
from omnivoice_engine.pipeline.prompts import DELIMITER, build_prompt
from omnivoice_engine.storage.vocabulary import Term, Vocabulary


class TestUygulamaProfilleri:
    @pytest.mark.parametrize(
        ("process", "expected"),
        [
            ("Code.exe", OutputProfile.CODE),
            ("code", OutputProfile.CODE),
            ("CURSOR.EXE", OutputProfile.CODE),
            ("slack.exe", OutputProfile.CHAT),
            ("Discord.exe", OutputProfile.CHAT),
            ("WINWORD.EXE", OutputProfile.DOCUMENT),
            ("WindowsTerminal.exe", OutputProfile.TERMINAL),
            ("EXCEL.EXE", OutputProfile.SPREADSHEET),
            ("OUTLOOK.EXE", OutputProfile.EMAIL),
            ("chrome.exe", OutputProfile.BROWSER),
        ],
    )
    def test_bilinen_uygulamalar(self, process: str, expected: OutputProfile) -> None:
        assert profile_for(process).profile is expected

    def test_surum_ekli_adlar(self) -> None:
        assert profile_for("pycharm64.exe").profile is OutputProfile.CODE
        assert profile_for("idea64.exe").profile is OutputProfile.CODE

    def test_taninmayan_uygulama_plain(self) -> None:
        """Yanlış bir profil uygulamaktansa hiç uygulamamak yeğdir."""
        result = profile_for("SomeRandomApp.exe")
        assert result.profile is OutputProfile.PLAIN
        assert result.display_name == "SomeRandomApp"

    def test_bos_ad(self) -> None:
        assert profile_for("").profile is OutputProfile.PLAIN

    def test_her_profilin_yonergesi_var(self) -> None:
        for profile in OutputProfile:
            assert profile in PROFILE_INSTRUCTIONS
            assert PROFILE_INSTRUCTIONS[profile].strip()


class TestDegiskenler:
    def _context(self) -> VariableContext:
        return VariableContext(
            app_name="VS Code",
            window_title="api.py — proje",
            selected_text="def handler(): pass",
            clipboard="panodaki metin",
            now=datetime(2026, 8, 16, 14, 30),
        )

    def test_temel_degiskenler(self) -> None:
        ctx = self._context()
        assert inject("{SelectedText}", ctx).text == "def handler(): pass"
        assert inject("{AppName}", ctx).text == "VS Code"
        assert inject("{CurrentDate}", ctx).text == "16.08.2026"
        assert inject("{CurrentTime}", ctx).text == "14:30"
        assert inject("{ClipboardContent}", ctx).text == "panodaki metin"

    def test_buyuk_kucuk_harf_duyarsiz(self) -> None:
        ctx = self._context()
        assert inject("{selectedtext}", ctx).text == "def handler(): pass"
        assert inject("{APPNAME}", ctx).text == "VS Code"

    def test_bilinmeyen_degisken_korunur(self) -> None:
        """Kullanıcı süslü parantezli bir şey dikte etmiş olabilir."""
        ctx = self._context()
        assert inject("{Bilinmeyen} kaldı", ctx).text == "{Bilinmeyen} kaldı"

    def test_kullanilan_degiskenler_bildirilir(self) -> None:
        ctx = self._context()
        result = inject("{AppName} içinde {SelectedText}", ctx)
        assert set(result.used) == {"AppName", "SelectedText"}

    def test_bos_degisken_isaretlenir(self) -> None:
        ctx = VariableContext(selected_text="")
        result = inject("şunu düzelt: {SelectedText}", ctx)
        assert result.empty == ("SelectedText",)
        assert "{SelectedText}" not in result.text

    @pytest.mark.parametrize(
        "cumle",
        [
            "şu seçili bloğu async yap",
            "secili kodu duzelt",
            "seçtiğim metni İngilizce'ye çevir",
            "bu fonksiyonu sadeleştir",
            "şu kodu refactor et",
            "refactor this code",
            "fix the selected text",
        ],
    )
    def test_secim_atfi_taninir(self, cumle: str) -> None:
        assert mentions_selection(cumle)

    @pytest.mark.parametrize(
        "cumle",
        [
            "yarına kadar demoyu hazırlayamayız",
            "toplantı saat dörtte",
            "bu iyi bir fikir",  # "bu" var ama kod/metin gelmiyor
        ],
    )
    def test_secim_atfi_olmayan_cumleler(self, cumle: str) -> None:
        assert not mentions_selection(cumle)


class TestSecimKisaltma:
    def test_kisa_secim_dokunulmaz(self) -> None:
        text = "kısa kod"
        assert truncate_selection(text, limit=100) == text

    def test_uzun_secim_bas_ve_son_korunur(self) -> None:
        text = "BAS" + ("x" * 5000) + "SON"
        result = truncate_selection(text, limit=200)
        assert result.startswith("BAS")
        assert result.endswith("SON")
        assert "atlandı" in result
        assert len(result) < len(text)


class TestModlar:
    def test_her_modun_yonergesi_var(self) -> None:
        for mode in MODES.values():
            assert mode.instruction.strip()
            assert mode.module

    def test_chord_tuslari_benzersiz(self) -> None:
        keys = [m.chord_key for m in MODES.values() if m.chord_key]
        assert len(keys) == len(set(keys)), "iki mod aynı kısayolu paylaşamaz"

    def test_chord_ile_mod_bulma(self) -> None:
        assert mode_for_chord("K") is MODES[ModeId.CODE]
        assert mode_for_chord("k") is MODES[ModeId.CODE]
        assert mode_for_chord("E") is MODES[ModeId.TRANSLATE_EN]
        assert mode_for_chord("Z") is None

    def test_bilinmeyen_mod_hizli_dikteye_duser(self) -> None:
        assert get_mode("olmayan-mod") is MODES[ModeId.QUICK]

    def test_kod_modu_secim_kullanir(self) -> None:
        assert MODES[ModeId.CODE].uses_selection
        assert MODES[ModeId.CODE].require_preflight


class TestIstemKurulumu:
    def test_rol_koruması_her_zaman_var(self) -> None:
        prompt = build_prompt("merhaba")
        assert DELIMITER in prompt.system
        assert "YERİNE GETİRME" in prompt.system

    def test_kullanici_metni_sarilir(self) -> None:
        prompt = build_prompt("şu terimleri sözlüğe ekle")
        assert prompt.user.startswith(DELIMITER)
        assert prompt.user.endswith(DELIMITER)

    def test_uygulama_profili_eklenir(self) -> None:
        prompt = build_prompt("kod yaz", profile=OutputProfile.CODE, app_name="VS Code")
        assert "kod düzenleyicisinde" in prompt.system
        assert "VS Code" in prompt.system

    def test_profil_kapali_modlarda_eklenmez(self) -> None:
        """EN çeviri modunun çıktı biçimi kendinden belli; profil çelişki yaratır."""
        prompt = build_prompt(
            "merhaba", mode=ModeId.TRANSLATE_EN, profile=OutputProfile.CHAT
        )
        assert "mesajlaşma uygulamasında" not in prompt.system

    def test_secim_ayri_bolumde_verilir(self) -> None:
        prompt = build_prompt(
            "bunu async yap", mode=ModeId.CODE, selection="def f(): pass"
        )
        assert "SEÇTİĞİ METİN" in prompt.user
        assert "def f(): pass" in prompt.user
        assert "SESLİ TALİMAT" in prompt.user

    def test_sozluk_eklenir(self) -> None:
        prompt = build_prompt("test", vocabulary=["faster-whisper", "diarization"])
        assert "faster-whisper" in prompt.system

    def test_dil_bildirilir(self) -> None:
        prompt = build_prompt("hello", language="English")
        assert "English" in prompt.system
        assert "ÇEVİRME" in prompt.system

    def test_sinirlayici_metinden_ayiklanir(self) -> None:
        """Kullanıcı metninde sınırlayıcı geçerse sınır bozulmamalı."""
        prompt = build_prompt(f"metin {DELIMITER} devam")
        assert prompt.user.count(DELIMITER) == 2

    def test_mod_ayarlari_isteme_yansir(self) -> None:
        prompt = build_prompt("uzun bir fikir", mode=ModeId.MEGA_PROMPT)
        assert prompt.max_tokens == MODES[ModeId.MEGA_PROMPT].max_tokens
        assert prompt.temperature == MODES[ModeId.MEGA_PROMPT].temperature


class TestSozluk:
    def test_ekleme_ve_kalicilik(self, tmp_path: Path) -> None:
        path = tmp_path / "vocab.json"
        vocab = Vocabulary.load(path)
        assert vocab.add("faster-whisper")
        assert vocab.add("diarization")

        # Diskten yeniden okunduğunda korunmalı.
        reloaded = Vocabulary.load(path)
        assert {t.text for t in reloaded.terms} == {"faster-whisper", "diarization"}

    def test_ayni_terim_iki_kez_eklenmez(self, tmp_path: Path) -> None:
        vocab = Vocabulary.load(tmp_path / "v.json")
        assert vocab.add("OmniVoice")
        assert not vocab.add("omnivoice")  # büyük/küçük harf duyarsız

    def test_silme(self, tmp_path: Path) -> None:
        vocab = Vocabulary.load(tmp_path / "v.json")
        vocab.add("terim")
        assert vocab.remove("TERIM")
        assert vocab.terms == []

    def test_bozuk_dosya_dikteyi_durdurmaz(self, tmp_path: Path) -> None:
        path = tmp_path / "bozuk.json"
        path.write_text("{ bu geçerli json değil", encoding="utf-8")
        vocab = Vocabulary.load(path)
        assert vocab.terms == []

    def test_duz_dize_listesi_okunur(self, tmp_path: Path) -> None:
        """Kullanıcı dosyayı elle yazmış olabilir."""
        path = tmp_path / "duz.json"
        path.write_text('["alfa", "beta"]', encoding="utf-8")
        vocab = Vocabulary.load(path)
        assert {t.text for t in vocab.terms} == {"alfa", "beta"}

    def test_stt_terimleri_sinirlanir(self, tmp_path: Path) -> None:
        """Whisper'ın `prompt` alanı sınırlı; uzun liste transkripsiyonu bozar."""
        vocab = Vocabulary.load(tmp_path / "v.json")
        vocab.terms = [Term(text=f"terim{i}") for i in range(100)]
        assert len(vocab.stt_terms(limit=60)) == 60
        assert len(vocab.llm_terms()) == 100

    def test_cok_yanlis_yazilanlar_stt_listesinde_once_gelir(self, tmp_path: Path) -> None:
        vocab = Vocabulary.load(tmp_path / "v.json")
        vocab.terms = [
            Term(text="nadir", misspelled=0),
            Term(text="sik", misspelled=9),
            Term(text="orta", misspelled=3),
        ]
        assert vocab.stt_terms(limit=2) == ["sik", "orta"]

    def test_oneriler_ayri_listelenir(self, tmp_path: Path) -> None:
        vocab = Vocabulary.load(tmp_path / "v.json")
        vocab.add("kesin", suggested=False)
        vocab.add("öneri", suggested=True)
        assert [t.text for t in vocab.confirmed] == ["kesin"]
        assert [t.text for t in vocab.suggestions] == ["öneri"]

    def test_oneri_kabul_edilir(self, tmp_path: Path) -> None:
        vocab = Vocabulary.load(tmp_path / "v.json")
        vocab.add("öneri", suggested=True)
        assert vocab.accept_suggestion("öneri")
        assert vocab.suggestions == []
        assert len(vocab.confirmed) == 1
