"""Düşük seviyeli klavye kancası — basılı tut kipi (Faz 7.7).

Electron'un `globalShortcut` API'si yalnız tuşa **basılmayı** bildiriyor,
bırakılmayı bildirmiyor. Bas-konuş (push-to-talk) için bırakma şart, bu yüzden
`WH_KEYBOARD_LL` kancası gerekiyor.

## Gizlilik — bu modülün en önemli kısmı

Bu kanca sistemdeki **her tuş vuruşunu** görür: parolalar, kredi kartı
numaraları, özel mesajlar. Bir keylogger ile aradaki tek fark, ne yaptığıdır.
Bu yüzden aşağıdaki kurallar koddan önce gelir:

1. **Hiçbir tuş kodu saklanmaz.** Yalnız izlenen tuşun (Space) ve değiştirici
   tuşların anlık basılı/bırakılmış durumu tutuluyor; başka hiçbir tuş
   herhangi bir yere yazılmıyor.
2. **Hiçbir tuş günlüğe yazılmaz.** Hata ayıklama günlüğü bile tuş kodu
   içermiyor — bir kez yazılan günlük dosyada kalır.
3. **Hiçbir tuş yutulmaz.** Kanca daima `CallNextHookEx` çağırıyor; kısayolun
   kendisi bile hedef uygulamaya geçmeye devam ediyor.
4. **Kanca yalnız basılı tut kipi açıkken kuruluyor.** Kapalıyken hiç
   yüklenmiyor — kullanılmayan bir kanca taşımanın savunması yok.

## Zaman aşımı tuzağı

Windows, geri çağrımın `LowLevelHooksTimeout` (varsayılan 300 ms) içinde
dönmesini bekler. Geç dönen kanca **sessizce kaldırılır**: kısayol çalışmayı
bırakır ve hiçbir hata görünmez. Bu yüzden geri çağrım yalnız bayrak
değiştirip dönüyor; asıl iş olay döngüsüne aktarılıyor.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

log = logging.getLogger(__name__)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_SPACE = 0x20
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12  # Alt
VK_LMENU = 0xA4
VK_RMENU = 0xA5

_CONTROL_KEYS = frozenset({VK_CONTROL, VK_LCONTROL, VK_RCONTROL})
_ALT_KEYS = frozenset({VK_MENU, VK_LMENU, VK_RMENU})


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    _HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
_user32.CallNextHookEx.restype = ctypes.c_long
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

# `argtypes`/`restype` vermek şart. Verilmezse ctypes dönüş değerini 32 bit
# `int` sanıyor ve 64 bitlik tanıtıcıyı kırpıyor; `SetWindowsHookExW` o zaman
# geçersiz bir modül tanıtıcısı görüp `ERROR_MOD_NOT_FOUND` (126) veriyor.
# Ölçtük — kanca hiç kurulmuyordu ve hata mesajı yanıltıcıydı.
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD
_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
_user32.GetMessageW.restype = ctypes.c_int


class PushToTalkHook:
    """Ctrl+Alt+Space basılı tutulduğu sürece kaydı sürdüren kanca.

    Kancanın kurulumu ve mesaj döngüsü **aynı iş parçacığında** olmak zorunda:
    `WH_KEYBOARD_LL` geri çağrımı, kancayı kuran iş parçacığının mesaj
    kuyruğuna gönderiliyor. Kuyruk pompalanmazsa geri çağrım hiç çalışmaz.
    """

    def __init__(
        self,
        *,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        key: int = VK_SPACE,
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._key = key

        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook: int | None = None
        self._proc: _HOOKPROC | None = None
        self._ready = threading.Event()

        # Yalnız izlediğimiz tuşların durumu. Başka hiçbir tuş burada yer
        # almıyor ve hiçbir yere yazılmıyor.
        self._ctrl_down = False
        self._alt_down = False
        self._key_down = False
        self._active = False

    # ── Yaşam döngüsü ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Kancayı kurar. Zaten çalışıyorsa hiçbir şey yapmaz."""
        if self.is_running:
            return True

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, name="omnivoice-ptt-hook", daemon=True
        )
        self._thread.start()
        # Kurulumun gerçekten başarılı olduğunu bilmeden `True` dönmek,
        # kullanıcıya çalışmayan bir özelliği açık göstermek olurdu.
        self._ready.wait(timeout=2.0)
        return self._hook is not None

    def stop(self) -> None:
        """Kancayı kaldırır ve iş parçacığını sonlandırır."""
        if not self.is_running or not self._thread_id:
            return
        # Mesaj döngüsünü kendi iş parçacığından çıkarmanın yolu bu:
        # `WM_QUIT` gönderiyoruz.
        _user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._reset_state()

    def _reset_state(self) -> None:
        self._ctrl_down = False
        self._alt_down = False
        self._key_down = False
        self._active = False

    # ── Kanca iş parçacığı ────────────────────────────────────────────────

    def _run(self) -> None:
        # Geri çağrımı örnek üzerinde tutuyoruz: çöp toplayıcı toplarsa
        # Windows serbest bırakılmış belleğe atlar ve süreç çöker.
        self._proc = _HOOKPROC(self._callback)

        module = _kernel32.GetModuleHandleW(None)
        self._hook = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, module, 0
        )
        if not self._hook:
            log.error(
                "Klavye kancası kurulamadı (hata %d) — basılı tut kipi devre dışı",
                ctypes.get_last_error(),
            )
            self._hook = None
            self._ready.set()
            return

        self._thread_id = _kernel32.GetCurrentThreadId()
        self._ready.set()
        log.info("Basılı tut kancası kuruldu")

        message = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(message))
            _user32.DispatchMessageW(ctypes.byref(message))

        _user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        log.info("Basılı tut kancası kaldırıldı")

    def _callback(self, code: int, wparam: int, lparam: int) -> int:
        """Windows geri çağrımı — **hızlı dönmek zorunda**.

        300 ms'yi aşarsa Windows kancayı sessizce kaldırır. Bu yüzden burada
        yalnız bayrak güncelleniyor; geri çağrımlar (`on_press` / `on_release`)
        kuyruğa iş bırakan ince fonksiyonlar olmalı.
        """
        # Hiçbir tuş yutulmuyor: `code < 0` durumunda işlem yapmadan geçmek
        # Windows'un kuralı.
        if code < 0:
            return _user32.CallNextHookEx(self._hook or 0, code, wparam, lparam)

        try:
            data = ctypes.cast(lparam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
            vk = int(data.vkCode)
            pressed = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            released = wparam in (WM_KEYUP, WM_SYSKEYUP)

            if vk in _CONTROL_KEYS:
                self._ctrl_down = pressed
            elif vk in _ALT_KEYS:
                self._alt_down = pressed
            elif vk == self._key:
                if pressed and not self._key_down:
                    self._key_down = True
                    if self._ctrl_down and self._alt_down and not self._active:
                        self._active = True
                        self._on_press()
                elif released:
                    self._key_down = False
                    if self._active:
                        self._active = False
                        self._on_release()

            # Değiştirici bırakılırsa da kaydı bitiriyoruz: kullanıcı Ctrl'ü
            # bırakıp Space'i tutmaya devam edebilir ve o an konuşmayı
            # bitirmiş sayılır.
            if self._active and released and (vk in _CONTROL_KEYS or vk in _ALT_KEYS):
                self._active = False
                self._key_down = False
                self._on_release()

        except Exception:  # noqa: BLE001
            # Geri çağrımdan istisna sızdırmak süreci düşürebilir. Tuş kodu
            # ASLA günlüğe yazılmıyor — yalnız bir şeyin ters gittiği.
            log.exception("Klavye kancası geri çağrımında hata")

        return _user32.CallNextHookEx(self._hook or 0, code, wparam, lparam)
