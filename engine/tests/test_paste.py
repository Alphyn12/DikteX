"""Yapıştırma motorunun kırılgan noktaları.

İkisi de canlı testte bulunan, **sessizce** başarısız olan gerçek hatalardan
doğdu. İkisi de çekirdek özelliği (metnin hedef uygulamaya gitmesi) tamamen
işlevsiz bırakıyordu ve hiçbir hata mesajı üretmiyordu.
"""

from __future__ import annotations

import ctypes

import pytest

from omnivoice_engine.output import paste as paste_module
from omnivoice_engine.output.paste import (
    _INPUT,
    _KEYBDINPUT,
    read_clipboard_text,
    write_clipboard_text,
)


class TestInputYapisi:
    """`SendInput` yanlış `cbSize` görürse hiçbir olay göndermeden 0 döner."""

    def test_input_boyutu_mimariye_uyar(self) -> None:
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        # x64: 4 (type) + 4 (hizalama) + 32 (birlik) = 40
        # x86: 4 (type) + 28 (birlik) = 32
        beklenen = 40 if pointer_size == 8 else 32
        assert ctypes.sizeof(_INPUT) == beklenen

    def test_birlik_en_buyuk_uyeye_gore_boyutlanir(self) -> None:
        """Yalnız KEYBDINPUT tanımlansaydı yapı küçük kalır ve çağrı düşerdi."""
        assert ctypes.sizeof(_INPUT) > ctypes.sizeof(_KEYBDINPUT) + 4

    def test_keybdinput_alanlari(self) -> None:
        names = [name for name, _ in _KEYBDINPUT._fields_]
        assert names == ["wVk", "wScan", "dwFlags", "time", "dwExtraInfo"]

    def test_sendinput_imzasi_tanimli(self) -> None:
        """argtypes tanımlı olmalı; yoksa ctypes işaretçiyi yanlış geçirebilir."""
        assert paste_module._user32.SendInput.argtypes is not None
        assert paste_module._user32.SendInput.restype is not None


class TestPano:
    def test_yazma_ve_okuma(self) -> None:
        metin = "OmniVoice pano testi — ğüşıöç"
        onceki = read_clipboard_text()
        try:
            assert write_clipboard_text(metin)
            assert read_clipboard_text() == metin
        finally:
            if onceki is not None:
                write_clipboard_text(onceki)

    def test_bos_metin_yazilabilir(self) -> None:
        onceki = read_clipboard_text()
        try:
            assert write_clipboard_text("")
        finally:
            if onceki is not None:
                write_clipboard_text(onceki)


class TestYapistirma:
    def test_bos_metin_hicbir_sey_yapmaz(self) -> None:
        """Boş çıktı için pano bozulmamalı."""
        onceki = "dokunulmamali"
        write_clipboard_text(onceki)
        paste_module.paste_text("")
        assert read_clipboard_text() == onceki

    def test_gecersiz_pencere_metni_panoda_birakir(self) -> None:
        """Odak alınamazsa metin yanlış pencereye gönderilmemeli — ama kaybolmamalı da.

        Bu test eskiden `PasteError` bekliyordu. Davranış Faz 7.1'de bilinçli
        olarak değişti: hata fırlatmak kullanıcının dikte ettiği metni yok
        ediyordu. Artık metin panoda kalıyor ve durum bildiriliyor.
        """
        onceki = read_clipboard_text()
        try:
            outcome = paste_module.paste_text("deneme", window_handle=999_999_999)
            assert outcome.method is paste_module.PasteMethod.CLIPBOARD
            assert outcome.needs_manual_paste
            # Kritik olan bu satır: metin kullanıcının erişebileceği yerde.
            assert read_clipboard_text() == "deneme"
        finally:
            if onceki is not None:
                write_clipboard_text(onceki)


class TestOdak:
    def test_gecersiz_tanitici_false_doner(self) -> None:
        from omnivoice_engine.output.window import focus_window

        assert focus_window(0) is False
        assert focus_window(999_999_999) is False
