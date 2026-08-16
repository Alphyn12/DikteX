"""FastAPI uygulaması — REST + WebSocket.

Aynı sunucu iki işi görür:
  1. Electron kabuğuyla WebSocket üzerinden konuşmak,
  2. dış betiklerin motoru tetikleyebileceği yerel REST arayüzü
     (Properties VI.5 — Yerel REST / Webhook Sunucusu, Faz 6.4).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from omnivoice_engine import __version__
from omnivoice_engine.config import get_settings

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="OmniVoice Engine",
        version=__version__,
        docs_url=None,  # Yerel motor; dışa dönük belge sunmasına gerek yok.
        redoc_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Hafif sağlık kontrolü. Anahtar değeri değil, yalnız varlığı bildirilir."""
        settings = get_settings()
        return {
            "status": "ok",
            "version": __version__,
            "providers": settings.configured_providers,
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        settings = get_settings()
        log.info("İstemci bağlandı")

        try:
            # El sıkışma: kabuk `hello` gönderir, motor `ready` ile cevaplar.
            # Kabuk bu mesajı görene kadar motoru "bağlandı" saymaz.
            await websocket.send_json(
                {
                    "type": "ready",
                    "version": __version__,
                    "providers": settings.configured_providers,
                }
            )

            while True:
                message = await websocket.receive_json()
                await _handle_message(websocket, message)

        except WebSocketDisconnect:
            log.info("İstemci ayrıldı")
        except Exception:
            log.exception("WebSocket oturumu hatayla sonlandı")

    return app


async def _handle_message(websocket: WebSocket, message: Any) -> None:
    """Gelen kareleri işler.

    Faz 0'da yalnız el sıkışma ve ping var; boru hattı komutları Faz 2'de
    buraya eklenecek.
    """
    if not isinstance(message, dict):
        return

    match message.get("type"):
        case "hello":
            client = message.get("client", "bilinmiyor")
            log.info("El sıkışıldı: %s", client)
        case "ping":
            await websocket.send_json({"type": "pong"})
        case unknown:
            log.warning("Bilinmeyen mesaj tipi: %r", unknown)
