"""Yapıştırma motoru (Properties V.7, Faz 2.10).

Metni hedef uygulamaya göndermenin iki yolu var:

- **Tuş tuş yazmak** (`SendInput` ile her karakter): yavaş, Türkçe karakterlerde
  klavye düzenine bağımlı, uzun metinde saniyeler sürer.
- **Pano + Ctrl+V**: anlık, düzenden bağımsız, biçimlendirmeyi korur.

İkincisini kullanıyoruz. Panonun kullanıcıya ait olduğunu unutmuyoruz: eski
içerik yapıştırmadan önce saklanır, sonra geri konur.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum

import win32clipboard
import win32con

from omnivoice_engine.output.window import can_send_input_to, focus_window

log = logging.getLogger(__name__)

#: Odak değişimi ile tuş gönderimi arasında hedef pencereye nefes payı.
_FOCUS_SETTLE_SECONDS = 0.06
#: Ctrl+V sonrası panoyu geri koymadan önce beklenen süre. Hedef uygulama
#: panoyu okumadan geri koyarsak eski içerik yapışır.
_PASTE_SETTLE_SECONDS = 0.25

_CLIPBOARD_RETRIES = 5
_CLIPBOARD_RETRY_DELAY = 0.02


# ── SendInput yapıları ────────────────────────────────────────────────────

_user32 = ctypes.WinDLL("user32", use_last_error=True)

KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_V = 0x56
VK_C = 0x43


#: `ULONG_PTR` mimariye göre 4 veya 8 bayt. `WPARAM` bu tipin ctypes karşılığı.
_ULONG_PTR = wintypes.WPARAM


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    """Kullanılmıyor ama birlik boyutunu belirleyen en büyük üye bu."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    """Win32 `INPUT`.

    Birliğin üç üyesi de tanımlı olmalı: `SendInput`'a geçilen `cbSize`
    yapının boyutundan hesaplanır ve Windows bunu birebir bekler. Yalnız
    `KEYBDINPUT` tanımlanırsa yapı x64'te 40 yerine 32 bayt olur; Windows o
    zaman hiçbir olay göndermeden **sessizce 0 döndürür**. Ölçtük — yapıştırma
    hiç çalışmıyordu ve hiçbir hata görünmüyordu.
    """

    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT


def _key_event(vk: int, *, up: bool) -> _INPUT:
    event = _INPUT(type=INPUT_KEYBOARD)
    event.ki = _KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if up else 0,
        time=0,
        dwExtraInfo=0,
    )
    return event


def _send_ctrl_key(vk: int) -> bool:
    """Ctrl + verilen tuş dizisini gönderir."""
    events = [
        _key_event(VK_CONTROL, up=False),
        _key_event(vk, up=False),
        _key_event(vk, up=True),
        _key_event(VK_CONTROL, up=True),
    ]
    array = (_INPUT * len(events))(*events)
    sent = _user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))
    if sent != len(events):
        log.error(
            "SendInput eksik gönderdi: %d/%d (hata %d, yapı %d bayt)",
            sent,
            len(events),
            ctypes.get_last_error(),
            ctypes.sizeof(_INPUT),
        )
        return False
    return True


def _send_ctrl_v() -> bool:
    """Yapıştırma: Ctrl+V."""
    return _send_ctrl_key(VK_V)


def _send_copy() -> bool:
    """Kopyalama: Ctrl+C. Seçili metni okumak için kullanılır."""
    return _send_ctrl_key(VK_C)


# ── Pano ──────────────────────────────────────────────────────────────────


def _open_clipboard() -> bool:
    """Panoyu açar.

    Pano tek seferde tek süreç tarafından açılabilir; başka bir uygulama o an
    kullanıyorsa kısa bir süre yeniden deneriz.
    """
    for _ in range(_CLIPBOARD_RETRIES):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:  # noqa: BLE001 - pano meşgul
            time.sleep(_CLIPBOARD_RETRY_DELAY)
    return False


def read_clipboard_text() -> str | None:
    """Panodaki metni okur. Metin yoksa `None`."""
    if not _open_clipboard():
        return None
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return str(win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT))
        return None
    except Exception:  # noqa: BLE001
        return None
    finally:
        win32clipboard.CloseClipboard()


def write_clipboard_text(text: str) -> bool:
    if not _open_clipboard():
        return False
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        return True
    except Exception:  # noqa: BLE001
        log.error("Panoya yazılamadı", exc_info=True)
        return False
    finally:
        win32clipboard.CloseClipboard()


# ── Yapıştırma ────────────────────────────────────────────────────────────


class PasteError(RuntimeError):
    """Metin hedef pencereye de panoya da konulamadı — gerçek başarısızlık."""


class PasteMethod(Enum):
    """Metnin kullanıcıya nasıl ulaştığı."""

    DIRECT = "direct"
    """Ctrl+V gönderildi, metin hedef pencereye yapıştı."""

    CLIPBOARD = "clipboard"
    """Yapıştırılamadı ama metin panoda duruyor; kullanıcı elle yapıştırabilir."""


@dataclass(frozen=True, slots=True)
class PasteOutcome:
    """Yapıştırmanın sonucu.

    Metin panoya düştüyse bu bir **hata değil**, kısmi başarıdır: kullanıcı
    konuşmasını kaybetmedi. Ama bunu bilmesi şart, yoksa Ctrl+V'ye basması
    gerektiğini anlamaz ve metnin kaybolduğunu sanır.
    """

    method: PasteMethod
    #: Doğrudan yapıştırılamadıysa sebebi — kullanıcıya gösterilir.
    reason: str | None = None

    @property
    def needs_manual_paste(self) -> bool:
        return self.method is PasteMethod.CLIPBOARD


def _describe(handle: int) -> str:
    """Pencereyi kullanıcının tanıyacağı biçimde adlandırır."""
    try:
        import win32gui  # noqa: PLC0415

        title = win32gui.GetWindowText(handle) or ""
        return title[:60] if title else f"pencere {handle}"
    except Exception:  # noqa: BLE001
        return f"pencere {handle}"


def _describe_foreground() -> str:
    try:
        import win32gui  # noqa: PLC0415

        handle = win32gui.GetForegroundWindow()
        return f"{_describe(handle)} (hwnd {handle})"
    except Exception:  # noqa: BLE001
        return "bilinmiyor"


def paste_text(
    text: str, *, window_handle: int | None = None, restore_clipboard: bool = True
) -> PasteOutcome:
    """Metni hedef pencereye yapıştırır; olmazsa panoda bırakır.

    Eskiden bu fonksiyon başarısızlıkta hata fırlatıyordu ve metin kayboluyordu.
    Üç ayrı yerde doğrudan yapıştırma **sessizce** başarısız olabiliyor:

    1. Hedef bizden yüksek bütünlük seviyesinde (yönetici olarak çalışan bir
       uygulama, Görev Yöneticisi, kurulum sihirbazı). `SendInput` bu durumda
       başarı döner ama olaylar yutulur — bu yüzden **önceden** kontrol edilir.
    2. Pencere öne getirilemez.
    3. `SendInput` eksik olay gönderir.

    Üçünde de metin panoda bırakılıyor ve pano **geri konulmuyor**: kullanıcının
    Ctrl+V ile yapıştıracağı şey orada durmalı.
    """
    if not text:
        return PasteOutcome(method=PasteMethod.DIRECT)

    previous = read_clipboard_text() if restore_clipboard else None

    if not write_clipboard_text(text):
        # Buraya düşersek metin gerçekten hiçbir yerde değil.
        raise PasteError("Pano kilitli — başka bir uygulama kullanıyor olabilir")

    def fallback(reason: str) -> PasteOutcome:
        """Metni panoda bırak ve sebebi bildir."""
        log.warning("Doğrudan yapıştırma yapılamadı: %s", reason)
        return PasteOutcome(method=PasteMethod.CLIPBOARD, reason=reason)

    if window_handle and not can_send_input_to(window_handle):
        return fallback(
            "Hedef uygulama yönetici olarak çalışıyor; Windows bu pencereye "
            "tuş göndermemize izin vermiyor."
        )

    if window_handle and not focus_window(window_handle):
        # Hangi pencere olduğunu söylemek şart: kullanıcı "yazacağım yere
        # tıkladım" diyor ama hedef bambaşka bir pencere olabilir — örneğin
        # kısayola OmniVoice odaktayken basılmışsa. İsimsiz bir hata
        # kullanıcıyı da beni de kör bırakıyordu.
        log.warning(
            "Odak alınamadı — hedef: %s | o anki ön plan: %s",
            _describe(window_handle),
            _describe_foreground(),
        )
        return fallback(
            f"“{_describe(window_handle)}” penceresi öne getirilemedi."
        )

    time.sleep(_FOCUS_SETTLE_SECONDS)

    if not _send_ctrl_v():
        return fallback("Tuş dizisi gönderilemedi.")

    if restore_clipboard and previous is not None:
        # Hedef uygulama panoyu okuyana kadar bekliyoruz; erken geri koyarsak
        # kullanıcının eski içeriği yapışır.
        time.sleep(_PASTE_SETTLE_SECONDS)
        write_clipboard_text(previous)

    return PasteOutcome(method=PasteMethod.DIRECT)
