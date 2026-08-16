"""Seçili metni okuma (Properties V.1 — Highlight & Transform).

Windows'ta başka bir uygulamadaki seçili metni okumanın taşınabilir bir yolu
yok. Uygulamalar seçimi kendi içinde tutar; dışarıdan okumak ancak UI
Automation ile ve her uygulamada farklı biçimde mümkün.

Pratikte herkesin kullandığı yol: hedef pencereye **Ctrl+C** gönderip panoyu
okumak. Bu güvenilir çünkü her metin alanı Ctrl+C'yi destekler.

Bedeli: kullanıcının panosu geçici olarak değişir. Bu yüzden eski içerik
saklanır ve okuma biter bitmez geri konur — kullanıcı bir şey kaybetmez.
"""

from __future__ import annotations

import logging
import time

from omnivoice_engine.output.paste import (
    _send_copy,
    read_clipboard_text,
    write_clipboard_text,
)
from omnivoice_engine.output.window import focus_window

log = logging.getLogger(__name__)

#: Ctrl+C sonrası hedef uygulamanın panoyu doldurması için beklenen süre.
_COPY_SETTLE_SECONDS = 0.14
#: Odak değişimi ile tuş gönderimi arasındaki pay.
_FOCUS_SETTLE_SECONDS = 0.06

#: Seçim bu uzunluğu aşarsa isteme tamamı değil, başı ve sonu eklenir.
#: Sınırsız metin göndermek hem pahalı hem de modelin bağlamını boğuyor.
MAX_SELECTION_CHARS = 12_000


def read_selection(window_handle: int | None = None) -> str:
    """Hedef penceredeki seçili metni okur.

    Seçim yoksa boş dize döner: Ctrl+C boş seçimde panoyu değiştirmez, bu
    yüzden panonun aynı kalması "seçim yok" demektir.
    """
    previous = read_clipboard_text()

    # Panoyu bilinen bir imle işaretliyoruz. Ctrl+C sonrası bu im hâlâ
    # duruyorsa hedef uygulama kopyalamadı, yani seçim yoktu.
    sentinel = "\x00omnivoice-selection-probe\x00"
    if not write_clipboard_text(sentinel):
        log.warning("Seçim okunamadı: pano kilitli")
        return ""

    try:
        if window_handle and not focus_window(window_handle):
            log.info("Seçim okunamadı: hedef pencere öne getirilemedi")
            return ""

        time.sleep(_FOCUS_SETTLE_SECONDS)
        if not _send_copy():
            return ""

        time.sleep(_COPY_SETTLE_SECONDS)
        copied = read_clipboard_text() or ""

        if copied == sentinel:
            return ""  # Seçim yoktu.
        return copied

    finally:
        # Kullanıcının panosu her durumda geri gelmeli.
        if previous is not None:
            write_clipboard_text(previous)
        elif read_clipboard_text() == sentinel:
            write_clipboard_text("")


def truncate_selection(text: str, limit: int = MAX_SELECTION_CHARS) -> str:
    """Çok uzun seçimi baş ve son parçasına indirir.

    Ortayı atmak baştan kesmekten iyidir: kodun hem başlangıcı hem bitişi
    bağlam taşır, ortadaki tekrar eden bloklar taşımaz.
    """
    if len(text) <= limit:
        return text

    head = limit * 2 // 3
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n\n… [{omitted} karakter atlandı] …\n\n{text[-tail:]}"
