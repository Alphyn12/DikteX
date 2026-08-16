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


def _try_set_foreground(handle: int) -> bool:
    try:
        win32gui.SetForegroundWindow(handle)
    except Exception:  # noqa: BLE001 - reddedilmesi beklenen bir durum
        return False
    return win32gui.GetForegroundWindow() == handle
