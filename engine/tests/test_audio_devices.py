"""Mikrofon seçiminin sağlamlığı.

Canlı testte bulunan iki gerçek hatadan doğdu:

1. Geçersiz bir aygıt indeksi vermek `PortAudioError` yükseltiyordu ve bu
   yakalanmadığı için **motor süreci komple düşüyordu**; kullanıcı hem
   mikrofonsuz hem uygulamasız kalıyordu.
2. PortAudio aygıt indeksleri oturumlar arasında kayıyor (aynı mikrofon bir
   seferinde 20, diğerinde 15). Seçimi indeksle saklamak yanlış aygıtı açar.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.audio.capture import (
    AudioDeviceError,
    MicrophoneCapture,
    list_input_devices,
)


class TestAygitListesi:
    def test_liste_beklenen_alanlari_tasir(self) -> None:
        for device in list_input_devices():
            assert isinstance(device["index"], int)
            assert isinstance(device["name"], str)
            assert device["name"].strip()
            assert isinstance(device["isSystemDefault"], bool)

    def test_ayni_ad_iki_kez_gelmez(self) -> None:
        """Aynı fiziksel aygıtın host API kopyaları elenmiş olmalı."""
        names = [d["name"] for d in list_input_devices()]
        assert len(names) == len(set(names))

    def test_surucu_yolu_adlari_elenir(self) -> None:
        for device in list_input_devices():
            name = str(device["name"])
            assert not name.startswith("@")
            assert ".sys," not in name

    def test_wdm_ks_listelenmez(self) -> None:
        for device in list_input_devices():
            assert device["hostApi"] != "Windows WDM-KS"


class TestAygitDegistirme:
    def test_gecersiz_aygit_hata_yukseltir_surec_dusmez(self) -> None:
        """Akış açıkken geçersiz aygıt: hata gelir ama nesne kullanılabilir kalır."""
        mic = MicrophoneCapture(pre_roll_seconds=0.5)
        try:
            mic.start_stream()
        except AudioDeviceError:
            pytest.skip("Bu makinede mikrofon yok")

        assert mic.is_streaming
        previous = mic.device

        with pytest.raises(AudioDeviceError):
            mic.set_device(9999)  # var olmayan indeks

        # En kritik güvence: eski aygıta geri dönülmüş ve akış hâlâ açık.
        assert mic.device == previous
        assert mic.is_streaming

        mic.stop_stream()

    def test_ayni_aygiti_secmek_zararsiz(self) -> None:
        mic = MicrophoneCapture(pre_roll_seconds=0.5)
        mic.set_device(None)  # zaten None
        assert mic.device is None

    def test_kayit_sirasinda_degistirilemez(self) -> None:
        mic = MicrophoneCapture(pre_roll_seconds=0.5)
        try:
            mic.start_stream()
        except AudioDeviceError:
            pytest.skip("Bu makinede mikrofon yok")

        mic.start_recording()
        with pytest.raises(AudioDeviceError, match="Kayıt sürerken"):
            mic.set_device(0)

        mic.cancel_recording()
        mic.stop_stream()


class TestAdlaCozumleme:
    """İndeksler kaydığı için seçim adla saklanmalı."""

    def test_bilinen_ad_cozumlenir(self) -> None:
        devices = list_input_devices()
        if not devices:
            pytest.skip("Bu makinede mikrofon yok")

        mic = MicrophoneCapture()
        name = str(devices[0]["name"])
        assert mic.resolve_device_by_name(name) == devices[0]["index"]

    def test_bilinmeyen_ad_none_doner(self) -> None:
        mic = MicrophoneCapture()
        assert mic.resolve_device_by_name("Olmayan Mikrofon 123") is None
