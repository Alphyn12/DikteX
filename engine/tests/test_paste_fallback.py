"""Yapıştırma doğrulama ve pano yedeği (Faz 7.1).

Buradaki asıl mesele **sessiz kayıp**. Doğrudan yapıştırma üç ayrı yerde
başarısız olabiliyor ve ikisinde Windows hiçbir hata vermiyor. Eskiden bu
durumda metin yok oluyordu; artık panoda kalması ve kullanıcıya söylenmesi
gerekiyor.

Win32 çağrıları gerçek pencere gerektirdiği için taklit ediliyor; sınanan şey
**karar mantığı**: hangi durumda panoya düşülüyor, pano geri konuluyor mu.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.output import paste as paste_module
from omnivoice_engine.output.paste import (
    PasteError,
    PasteMethod,
    paste_text,
)


@pytest.fixture
def fake_win32(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Win32 katmanını taklit eder ve ne olduğunu kaydeder."""
    state: dict[str, object] = {
        "clipboard": "kullanıcının eski panosu",
        "writes": [],
        "ctrl_v_sent": 0,
        "can_send": True,
        "focus_ok": True,
        "send_ok": True,
        "write_ok": True,
    }

    def read() -> str | None:
        return state["clipboard"]  # type: ignore[return-value]

    def write(text: str) -> bool:
        if not state["write_ok"]:
            return False
        state["clipboard"] = text
        state["writes"].append(text)  # type: ignore[union-attr]
        return True

    monkeypatch.setattr(paste_module, "read_clipboard_text", read)
    monkeypatch.setattr(paste_module, "write_clipboard_text", write)
    monkeypatch.setattr(paste_module, "can_send_input_to", lambda _h: state["can_send"])
    monkeypatch.setattr(paste_module, "focus_window", lambda _h: state["focus_ok"])

    def send_ctrl_v() -> bool:
        state["ctrl_v_sent"] += 1  # type: ignore[operator]
        return state["send_ok"]  # type: ignore[return-value]

    monkeypatch.setattr(paste_module, "_send_ctrl_v", send_ctrl_v)
    # Testler beklemesin.
    monkeypatch.setattr(paste_module.time, "sleep", lambda _s: None)
    return state


class TestBasariliYapistirma:
    def test_dogrudan_yapistirilir(self, fake_win32: dict[str, object]) -> None:
        outcome = paste_text("merhaba", window_handle=1234)
        assert outcome.method is PasteMethod.DIRECT
        assert not outcome.needs_manual_paste
        assert fake_win32["ctrl_v_sent"] == 1

    def test_pano_geri_konur(self, fake_win32: dict[str, object]) -> None:
        """Pano kullanıcıya ait; ödünç alıp geri vermek gerekiyor."""
        paste_text("merhaba", window_handle=1234)
        assert fake_win32["clipboard"] == "kullanıcının eski panosu"

    def test_bos_metin_hicbir_sey_yapmaz(self, fake_win32: dict[str, object]) -> None:
        paste_text("", window_handle=1234)
        assert fake_win32["ctrl_v_sent"] == 0
        assert fake_win32["writes"] == []


class TestPanoYedegi:
    """Doğrudan yapıştırmanın başarısız olduğu üç yol."""

    def test_yuksek_butunluk_seviyesi(self, fake_win32: dict[str, object]) -> None:
        """Yönetici olarak çalışan uygulamaya tuş gönderilemiyor.

        Kritik olan: `SendInput` bu durumda BAŞARI döner. O yüzden hiç
        denemeden, önceden bakmak zorundayız.
        """
        fake_win32["can_send"] = False
        outcome = paste_text("gizli metin", window_handle=1234)

        assert outcome.method is PasteMethod.CLIPBOARD
        assert outcome.needs_manual_paste
        assert outcome.reason and "yönetici" in outcome.reason
        # Boşuna tuş göndermedik.
        assert fake_win32["ctrl_v_sent"] == 0

    def test_odak_alinamadi(self, fake_win32: dict[str, object]) -> None:
        fake_win32["focus_ok"] = False
        outcome = paste_text("metin", window_handle=1234)
        assert outcome.method is PasteMethod.CLIPBOARD
        assert fake_win32["ctrl_v_sent"] == 0

    def test_sendinput_eksik_gonderdi(self, fake_win32: dict[str, object]) -> None:
        fake_win32["send_ok"] = False
        outcome = paste_text("metin", window_handle=1234)
        assert outcome.method is PasteMethod.CLIPBOARD

    @pytest.mark.parametrize(
        ("anahtar", "deger"),
        [("can_send", False), ("focus_ok", False), ("send_ok", False)],
    )
    def test_yedekte_metin_PANODA_KALIR(
        self, fake_win32: dict[str, object], anahtar: str, deger: bool
    ) -> None:
        """Bu testin bozulması, kullanıcının dikte ettiği metni kaybetmesi demek.

        Pano geri konursa kullanıcı Ctrl+V'ye bastığında eski içeriğini
        yapıştırır ve konuşması yok olur.
        """
        fake_win32[anahtar] = deger
        paste_text("kaybolmaması gereken metin", window_handle=1234)
        assert fake_win32["clipboard"] == "kaybolmaması gereken metin"


class TestGercekBasarisizlik:
    def test_panoya_yazilamazsa_hata(self, fake_win32: dict[str, object]) -> None:
        """Metin hiçbir yere konulamadıysa bu gerçek bir hatadır."""
        fake_win32["write_ok"] = False
        with pytest.raises(PasteError):
            paste_text("metin", window_handle=1234)
