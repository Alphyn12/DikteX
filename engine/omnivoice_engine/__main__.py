"""Motorun giriş noktası.

Electron kabuğu bu modülü `python -m omnivoice_engine` ile başlatır. Elle
çalıştırmak da mümkündür; motor kabuk olmadan da ayakta kalır.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from omnivoice_engine import __version__
from omnivoice_engine.config import get_settings
from omnivoice_engine.server.app import create_app


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
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
