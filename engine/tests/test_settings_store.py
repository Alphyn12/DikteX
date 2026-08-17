"""Kalıcı kullanıcı ayarları (Faz 3.15 / 7.B).

Bu modülün varlık sebebi somut bir hata: mikrofon seçimi her motor yeniden
başlatmasında sıfırlanıyordu ve model değiştirmek `config.py` düzenlemeyi
gerektiriyordu.

Testlerin ağırlığı **bozuk veriye dayanıklılıkta**: ayar dosyası uygulamanın
açılış yolunda okunuyor, bozulursa uygulama hiç açılmaz hâle gelebilir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnivoice_engine.storage.settings_store import SettingsStore, UserSettings


@pytest.fixture
def store(tmp_path: Path) -> SettingsStore:
    return SettingsStore.load(tmp_path / "settings.json")


class TestKalicilik:
    def test_kaydedilen_ayar_geri_okunur(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        SettingsStore.load(path).update(
            microphone_name="Realtek Mikrofon", llm_model="google/gemini-3.5-flash-lite"
        )

        yeniden = SettingsStore.load(path)
        assert yeniden.settings.microphone_name == "Realtek Mikrofon"
        assert yeniden.settings.llm_model == "google/gemini-3.5-flash-lite"

    def test_mikrofon_ADLA_saklanir(self, store: SettingsStore) -> None:
        """İndeks saklamak işe yaramaz: PortAudio indeksleri kayıyor.

        Kaydedilen 3 numaralı aygıt bir sonraki açılışta bambaşka bir
        mikrofon olabilir ve kullanıcı bunu ancak kaydın boş çıkmasıyla anlar.
        """
        assert not hasattr(UserSettings(), "microphone_index")
        assert hasattr(UserSettings(), "microphone_name")

    def test_none_secim_yapilmadi_demek(self, store: SettingsStore) -> None:
        assert store.settings.llm_model is None
        store.update(llm_model="bir/model")
        store.update(llm_model=None)
        assert store.settings.llm_model is None

    def test_bos_dize_none_olur(self, store: SettingsStore) -> None:
        """Arayüzden temizlenen alan geçersiz bir model kimliği üretmemeli."""
        store.update(llm_model="   ")
        assert store.settings.llm_model is None

    def test_kismi_guncelleme_digerlerini_bozmaz(self, store: SettingsStore) -> None:
        store.update(llm_model="a/b", microphone_name="Mik")
        store.update(llm_model="c/d")
        assert store.settings.microphone_name == "Mik"


class TestBozukVeri:
    def test_bozuk_json_varsayilanlara_doner(self, tmp_path: Path) -> None:
        """Bozuk ayar dosyası uygulamayı açılmaz hâle getirmemeli."""
        path = tmp_path / "bozuk.json"
        path.write_text("{ bu json degil", encoding="utf-8")

        store = SettingsStore.load(path)
        assert store.settings.llm_model is None
        assert store.settings.microphone_name is None

    def test_liste_iceren_dosya_yok_sayilir(self, tmp_path: Path) -> None:
        path = tmp_path / "liste.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert SettingsStore.load(path).settings.microphone_name is None

    def test_tek_bozuk_alan_digerlerini_goturmez(self, tmp_path: Path) -> None:
        path = tmp_path / "kismi.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "microphoneName": "Realtek",
                    "autoStopSeconds": "sayi-degil",
                }
            ),
            encoding="utf-8",
        )
        store = SettingsStore.load(path)
        assert store.settings.microphone_name == "Realtek"
        assert store.settings.auto_stop_seconds is None

    def test_bilinmeyen_alanlar_yok_sayilir(self, tmp_path: Path) -> None:
        """İleride kaldırılan bir alan, eski dosyayı okunamaz yapmamalı."""
        path = tmp_path / "fazla.json"
        path.write_text(
            json.dumps({"version": 1, "llmModel": "a/b", "kaldirilmisAlan": 42}),
            encoding="utf-8",
        )
        assert SettingsStore.load(path).settings.llm_model == "a/b"

    def test_olmayan_dosya_varsayilan(self, tmp_path: Path) -> None:
        assert SettingsStore.load(tmp_path / "yok.json").settings == UserSettings()


class TestDegerKisitlari:
    def test_otomatik_durdurma_siniri(self, store: SettingsStore) -> None:
        store.update(auto_stop_seconds=600)
        assert store.settings.auto_stop_seconds == 10.0
        store.update(auto_stop_seconds=-3)
        assert store.settings.auto_stop_seconds == 0.0

    def test_gecersiz_dil_yok_sayilir(self, store: SettingsStore) -> None:
        store.update(locale="klingon")
        assert store.settings.locale is None
        store.update(locale="en")
        assert store.settings.locale == "en"

    def test_maskeleme_bool_olur(self, store: SettingsStore) -> None:
        store.update(mask_pii=1)
        assert store.settings.mask_pii is True


class TestHataYolu:
    def test_bilinmeyen_ayar_HATA_verir(self, store: SettingsStore) -> None:
        """Sessizce yok saymak, çalışmayan bir ayar olarak ortaya çıkardı."""
        with pytest.raises(KeyError):
            store.update(olmayanAyar="deger")

    def test_yazilamayan_yol_cokertmez(self, tmp_path: Path) -> None:
        engel = tmp_path / "engel"
        engel.write_text("dosya", encoding="utf-8")
        store = SettingsStore.load(engel / "settings.json")
        # Yazma başarısız olacak ama hata yükseltmemeli.
        store.update(llm_model="a/b")
        assert store.settings.llm_model == "a/b"
