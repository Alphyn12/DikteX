"""Ekran bölgesi yakalama (Properties V.2 — Bölgesel Ekran Gözü).

Kullanıcı ekranda bir hata penceresi, bir grafik veya bir kod parçası seçip
sesle soru sorar. Bölge Electron'daki saydam kaplama ile seçilir, görüntüyü
burada yakalar ve doğrudan görsel kabul eden modele göndeririz.

Ayrı bir OCR motoru **kullanmıyoruz**: modern görsel modeller metni zaten
okuyor ve üstelik bağlamı da anlıyor. Tesseract gibi bir OCR eklemek hem ek
bağımlılık hem de "metni oku ama ne anlama geldiğini bilme" demek olurdu.
"""

from __future__ import annotations

import base64
import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass
from io import BytesIO

log = logging.getLogger(__name__)

#: Modele gönderilecek en büyük kenar. Daha büyüğü hem pahalı hem gereksiz;
#: metin okunabilirliği için 1600 px fazlasıyla yeterli.
MAX_EDGE = 1600

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class ScreenCaptureError(RuntimeError):
    """Ekran bölgesi yakalanamadı."""


@dataclass(frozen=True, slots=True)
class Region:
    """Ekran koordinatlarında bir dikdörtgen."""

    x: int
    y: int
    width: int
    height: int

    @property
    def is_valid(self) -> bool:
        # Kazara yapılan tek tıklama sıfıra yakın bir bölge üretir; onu
        # yakalamaya çalışmak anlamsız.
        return self.width >= 8 and self.height >= 8


@dataclass(frozen=True, slots=True)
class Capture:
    """Yakalanmış görüntü."""

    png: bytes
    width: int
    height: int

    def to_data_url(self) -> str:
        return f"data:image/png;base64,{base64.b64encode(self.png).decode('ascii')}"


def capture_region(region: Region) -> Capture:
    """Ekranın verilen bölgesini yakalar ve PNG olarak döndürür.

    Win32 BitBlt kullanılıyor: Electron'un `desktopCapturer`'ı tüm ekranı
    alıp kırpardı, bu ise doğrudan istenen bölgeyi okur.
    """
    if not region.is_valid:
        raise ScreenCaptureError("Seçilen bölge çok küçük")

    screen_dc = _user32.GetDC(0)
    if not screen_dc:
        raise ScreenCaptureError("Ekran bağlamı alınamadı")

    memory_dc = None
    bitmap = None
    try:
        memory_dc = _gdi32.CreateCompatibleDC(screen_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(screen_dc, region.width, region.height)
        if not memory_dc or not bitmap:
            raise ScreenCaptureError("Bellek yüzeyi oluşturulamadı")

        _gdi32.SelectObject(memory_dc, bitmap)
        copied = _gdi32.BitBlt(
            memory_dc, 0, 0, region.width, region.height,
            screen_dc, region.x, region.y, SRCCOPY,
        )
        if not copied:
            raise ScreenCaptureError(f"Ekran kopyalanamadı (hata {ctypes.get_last_error()})")

        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = region.width
        # Negatif yükseklik: satırlar yukarıdan aşağı gelsin. Pozitif olursa
        # görüntü baş aşağı çıkar.
        header.biHeight = -region.height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0

        info = _BITMAPINFO()
        info.bmiHeader = header

        buffer_size = region.width * region.height * 4
        buffer = ctypes.create_string_buffer(buffer_size)
        rows = _gdi32.GetDIBits(
            memory_dc, bitmap, 0, region.height, buffer, ctypes.byref(info), DIB_RGB_COLORS
        )
        if rows == 0:
            raise ScreenCaptureError("Piksel verisi okunamadı")

        return _encode_png(buffer.raw, region.width, region.height)

    finally:
        if bitmap:
            _gdi32.DeleteObject(bitmap)
        if memory_dc:
            _gdi32.DeleteDC(memory_dc)
        _user32.ReleaseDC(0, screen_dc)


def _encode_png(bgra: bytes, width: int, height: int) -> Capture:
    """BGRA arabelleğini PNG'ye çevirir ve gerekiyorsa küçültür."""
    import numpy as np
    from PIL import Image

    array = np.frombuffer(bgra, dtype=np.uint8).reshape(height, width, 4)
    # Windows BGRA veriyor; PIL RGB bekliyor. Alfa kanalı ekran görüntüsünde
    # anlamsız (hep 0 geliyor), atıyoruz.
    image = Image.fromarray(array[:, :, [2, 1, 0]], mode="RGB")

    longest = max(image.width, image.height)
    if longest > MAX_EDGE:
        scale = MAX_EDGE / longest
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.LANCZOS,
        )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return Capture(png=buffer.getvalue(), width=image.width, height=image.height)


def virtual_screen_bounds() -> Region:
    """Tüm ekranları kapsayan sanal masaüstünün sınırları.

    Çoklu ekranda bölge seçimi kaplaması bu alanı kaplamalı; yalnız birincil
    ekranı kaplamak ikinci ekrandaki seçimi imkânsız kılardı.
    """
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    return Region(
        x=_user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        y=_user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        width=_user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        height=_user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )
