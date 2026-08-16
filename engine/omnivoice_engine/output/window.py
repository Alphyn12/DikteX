"""Aktif pencere takibi.

Dikte başladığı anda kullanıcının hangi uygulamada olduğunu kaydeder. İki işe
yarar:

1. **Yapıştırma** — çıktı, dikte başladığındaki pencereye gider. Kullanıcı
   arada başka bir yere tıklarsa metin yanlış yere düşmez.
2. **Bağlam farkındalığı** (Faz 3.1) — hangi uygulamada olduğuna göre çıktı
   biçimi değişecek.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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

    Windows, arka plandaki bir sürecin odak çalmasını engeller. Pencere simge
    durumundaysa önce geri yükleriz; `SetForegroundWindow` yine de reddedilirse
    yapıştırma yapılmamalı — bu yüzden sonuç döndürüyoruz.
    """
    if not handle:
        return False

    try:
        if not win32gui.IsWindow(handle):
            return False
        if win32gui.IsIconic(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(handle)
        return win32gui.GetForegroundWindow() == handle
    except Exception:  # noqa: BLE001
        log.warning("Pencere öne getirilemedi: %s", handle, exc_info=True)
        return False
