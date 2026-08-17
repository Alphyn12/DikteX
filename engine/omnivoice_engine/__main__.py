"""Motorun giriş noktası.

Electron kabuğu bu modülü `python -m omnivoice_engine` ile başlatır. Elle
çalıştırmak da mümkündür; motor kabuk olmadan da ayakta kalır.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from omnivoice_engine import __version__
from omnivoice_engine.config import get_settings
from omnivoice_engine.storage.db import default_db_path
from omnivoice_engine.server.app import create_app


#: Günlük dosyası kaç tur saklanıyor. Küçük tutuluyor: içinde dikte metni
#: yok ama pencere başlıkları var ve onlar da kişisel bilgi taşıyabiliyor.
_LOG_BACKUPS = 3
_LOG_MAX_BYTES = 2_000_000


def log_path() -> Path:
    """Günlük dosyasının yeri — veritabanının yanında."""
    return default_db_path().parent / "diktex.log"


def _configure_logging() -> None:
    """Konsola VE dosyaya yazar.

    Dosya şart: paketlenmiş uygulama Windows'un GUI alt sisteminde çalışıyor
    ve stdout'u hiçbir yere bağlı değil. Bir şey ters gittiğinde tanı
    koyacak tek iz bu dosya oluyor — kullanıcı "çalışmıyor" dediğinde
    bakılacak bir yer olmalı.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                path, maxBytes=_LOG_MAX_BYTES, backupCount=_LOG_BACKUPS, encoding="utf-8"
            )
        )
    except OSError:
        # Günlük yazılamıyorsa motor yine de açılmalı; konsol yeter.
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main() -> int:
    _configure_logging()
    log = logging.getLogger("omnivoice")

    settings = get_settings()
    providers = settings.configured_providers

    log.info("OmniVoice motoru %s", __version__)
    log.info("Dinlenen adres: 127.0.0.1:%d", settings.port)

    if providers:
        log.info("Yapılandırılmış sağlayıcılar: %s", ", ".join(providers))
    else:
        # Faz 0'da anahtar gerekmez; uyarıp devam ediyoruz.
        log.warning("Hiçbir sağlayıcı anahtarı bulunamadı — .env.local dosyasına bakın")

    uvicorn.run(
        create_app(),
        # Yalnız yerel arayüz. Motor dış ağdan erişilebilir olmamalı.
        host="127.0.0.1",
        port=settings.port,
        log_level="warning",  # Uygulama günlükleri yukarıdaki biçimden geçer.
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
