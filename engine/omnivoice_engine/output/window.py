"""Aktif pencere takibi.

Dikte başladığı anda kullanıcının hangi uygulamada olduğunu kaydeder. İki işe
yarar:

1. **Yapıştırma** — çıktı, dikte başladığındaki pencereye gider. Kullanıcı
   arada başka bir yere tıklarsa metin yanlış yere düşmez.
2. **Bağlam farkındalığı** (Faz 3.1) — hangi uygulamada olduğuna göre çıktı
   biçimi değişecek.
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

import win32api
import win32con
import win32gui
import win32process

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """Bir pencerenin kimliği."""

    handle: int
    title: str
    process_name: str

    @property
    def app_name(self) -> str:
        """Uygulamanın gösterilecek adı: `Code.exe` → `Code`."""
        return self.process_name.removesuffix(".exe") or "bilinmiyor"


def _process_name(handle: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(handle)
    except Exception:  # noqa: BLE001 - win32 çağrıları çeşitli hata üretir
        return ""

    try:
        import psutil  # noqa: PLC0415 - isteğe bağlı bağımlılık

        return psutil.Process(pid).name()
    except Exception:  # noqa: BLE001
        pass

    # psutil yoksa doğrudan Win32 ile dene.
    try:
        import win32api  # noqa: PLC0415

        handle_proc = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid
        )
        try:
            import win32process as wp  # noqa: PLC0415

            path = wp.GetModuleFileNameEx(handle_proc, 0)
            return str(path).rsplit("\\", 1)[-1]
        finally:
            win32api.CloseHandle(handle_proc)
    except Exception:  # noqa: BLE001
        return ""


def get_foreground_window() -> WindowInfo | None:
    """Şu anda odakta olan pencere. Bulunamazsa `None`."""
    try:
        handle = win32gui.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        return None

    if not handle:
        return None

    try:
        title = win32gui.GetWindowText(handle) or ""
    except Exception:  # noqa: BLE001
        title = ""

    return WindowInfo(handle=handle, title=title, process_name=_process_name(handle))


def focus_window(handle: int) -> bool:
    """Verilen pencereyi öne getirir.

    Windows "odak çalma" korumasına sahiptir: ön planda olmayan bir sürecin
    `SetForegroundWindow` çağrısı sessizce reddedilir. Bu bizim tam olarak
    içinde bulunduğumuz durum — pre-flight sırasında ön planda HUD vardır,
    yapıştırmayı isteyense motor sürecidir. Ölçtük: düz çağrı
    `SetForegroundWindow` hatası veriyor ve yapıştırma hiç çalışmıyordu.

    Çözüm, ön plandaki pencerenin giriş kuyruğuna geçici olarak bağlanmak
    (`AttachThreadInput`). Böylece Windows çağrıyı kullanıcının kendi
    eylemiymiş gibi görür. Bağlantı her durumda geri sökülür; sökülmezse iki
    süreç birbirinin klavye durumunu paylaşmaya devam eder.
    """
    if not handle:
        return False

    try:
        if not win32gui.IsWindow(handle):
            return False
    except Exception:  # noqa: BLE001
        return False

    try:
        if win32gui.IsIconic(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
    except Exception:  # noqa: BLE001
        pass

    # Önce düz yol: pencere zaten öndeyse veya izin varsa fazlası gerekmez.
    if _try_set_foreground(handle):
        return True

    foreground = win32gui.GetForegroundWindow()
    if not foreground or foreground == handle:
        return win32gui.GetForegroundWindow() == handle

    try:
        target_thread, _ = win32process.GetWindowThreadProcessId(handle)
        foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground)
        current_thread = win32api.GetCurrentThreadId()
    except Exception:  # noqa: BLE001
        log.warning("Pencere iş parçacığı bilgisi alınamadı", exc_info=True)
        return False

    attached: list[int] = []
    try:
        for thread in {foreground_thread, target_thread}:
            if thread and thread != current_thread:
                try:
                    win32process.AttachThreadInput(current_thread, thread, True)
                    attached.append(thread)
                except Exception:  # noqa: BLE001
                    pass

        try:
            win32gui.BringWindowToTop(handle)
        except Exception:  # noqa: BLE001
            pass
        _try_set_foreground(handle)
    finally:
        for thread in attached:
            try:
                win32process.AttachThreadInput(current_thread, thread, False)
            except Exception:  # noqa: BLE001
                pass

    return win32gui.GetForegroundWindow() == handle


# ── Bütünlük seviyesi (UIPI) ──────────────────────────────────────────────
#
# Windows'un "User Interface Privilege Isolation" kuralı: bir süreç, yalnız
# kendisiyle **aynı ya da daha düşük** bütünlük seviyesindeki pencerelere
# girdi enjekte edebilir. Yönetici olarak çalışan bir uygulamaya `SendInput`
# göndermek engellenir — ve kritik olan şu: `SendInput` bu durumda da
# **başarı döndürür**. Olaylar sessizce yutulur.
#
# Bu yüzden gönderdikten sonra doğrulamak yerine, göndermeden ÖNCE bakıyoruz.

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_TOKEN_INTEGRITY_LEVEL = 25
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TOKEN_QUERY = 0x0008
_ERROR_ACCESS_DENIED = 5

#: Bilinen bütünlük seviyeleri (`SECURITY_MANDATORY_*_RID`).
INTEGRITY_MEDIUM = 0x2000
INTEGRITY_HIGH = 0x3000


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.HANDLE),
]
_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
# `argtypes` şart: SID bir işaretçi ve ctypes onu varsayılan olarak `int`
# sanıp x64'te `OverflowError` veriyor. Ölçtük.
_advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
_advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
_advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


def _integrity_level(pid: int) -> int | None:
    """Sürecin bütünlük seviyesi. Okunamazsa `None`."""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # Erişim reddi tek başına bir bilgidir: bizden yüksek bir süreç.
        # Ölçtük — `winlogon.exe` ve `csrss.exe` burada hata 5 veriyor.
        if ctypes.get_last_error() == _ERROR_ACCESS_DENIED:
            return INTEGRITY_HIGH
        return None

    try:
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(handle, _TOKEN_QUERY, ctypes.byref(token)):
            return INTEGRITY_HIGH if ctypes.get_last_error() == _ERROR_ACCESS_DENIED else None
        try:
            size = wintypes.DWORD()
            _advapi32.GetTokenInformation(
                token, _TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size)
            )
            buffer = ctypes.create_string_buffer(size.value)
            if not _advapi32.GetTokenInformation(
                token, _TOKEN_INTEGRITY_LEVEL, buffer, size, ctypes.byref(size)
            ):
                return None
            label = ctypes.cast(buffer, ctypes.POINTER(_TOKEN_MANDATORY_LABEL)).contents
            count = _advapi32.GetSidSubAuthorityCount(label.Label.Sid).contents.value
            return int(_advapi32.GetSidSubAuthority(label.Label.Sid, count - 1).contents.value)
        finally:
            _kernel32.CloseHandle(token)
    finally:
        _kernel32.CloseHandle(handle)


def can_send_input_to(handle: int) -> bool:
    """Bu pencereye girdi enjekte edebilir miyiz?

    `False` ise `SendInput` **sessizce yutulacak** demektir: fonksiyon başarı
    döner ama tuşlar hedefe ulaşmaz. Bunu önceden bilmek, metni kaybetmek
    yerine panoya düşürebilmemizi sağlıyor.

    Bilinmeyen durumda `True` dönüyoruz: seviye okunamadığı için yapıştırmayı
    hiç denememek, çalışacak bir yapıştırmayı engellerdi. Yanlış tarafta
    kalmak yerine deneyip sonucu bildirmek daha iyi.
    """
    if not handle:
        return True

    try:
        _, pid = win32process.GetWindowThreadProcessId(handle)
    except Exception:  # noqa: BLE001
        return True
    if not pid:
        return True

    target = _integrity_level(pid)
    if target is None:
        return True

    own = _integrity_level(win32api.GetCurrentProcessId())
    if own is None:
        own = INTEGRITY_MEDIUM

    if target > own:
        log.warning(
            "Hedef pencere daha yüksek bütünlük seviyesinde (%#x > %#x); "
            "girdi enjeksiyonu UIPI tarafından engellenecek",
            target,
            own,
        )
        return False
    return True


def _try_set_foreground(handle: int) -> bool:
    try:
        win32gui.SetForegroundWindow(handle)
    except Exception:  # noqa: BLE001 - reddedilmesi beklenen bir durum
        return False
    return win32gui.GetForegroundWindow() == handle
