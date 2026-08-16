"""FastAPI uygulaması — REST + WebSocket.

Aynı sunucu iki işi görür:
  1. Electron kabuğuyla WebSocket üzerinden konuşmak,
  2. dış betiklerin motoru tetikleyebileceği yerel REST arayüzü
     (Properties VI.5 — Yerel REST / Webhook Sunucusu, Faz 6.4).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from omnivoice_engine import __version__
from omnivoice_engine.audio.capture import (
    AudioDeviceError,
    MicrophoneCapture,
    list_input_devices,
)
from omnivoice_engine.config import get_settings
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.pipeline.dictation import DictationPipeline
from omnivoice_engine.storage.db import Database
from omnivoice_engine.stt.router import SttRouter
from omnivoice_engine.vault import list_entries

log = logging.getLogger(__name__)


class EngineContext:
    """Motorun uzun ömürlü parçaları.

    Tek örnek: mikrofon akışı, veritabanı bağlantısı ve boru hattı uygulama
    ömrü boyunca yaşar. WebSocket bağlantıları gelip gider, bunlar kalır.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.mic = MicrophoneCapture(pre_roll_seconds=1.0)
        self.stt = SttRouter()
        self.llm = OpenRouterLlm()
        self.db = Database()
        self.budget_usd = settings.budget_usd

        #: Bağlı arayüz istemcileri. Olaylar hepsine yayınlanır.
        self._clients: set[WebSocket] = set()

        self.pipeline = DictationPipeline(
            mic=self.mic,
            stt=self.stt,
            llm=self.llm,
            db=self.db,
            emit=self.broadcast,
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Olayı bağlı tüm istemcilere gönderir."""
        if not self._clients:
            return
        dead: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_json(message)
            except Exception:  # noqa: BLE001 - kopan bağlantı yayını durdurmasın
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    def add_client(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)

    def remove_client(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    def shutdown(self) -> None:
        self.mic.stop_stream()
        self.db.close()


def create_app() -> FastAPI:
    context = EngineContext()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Mikrofon akışını açılışta başlatıyoruz: pre-roll tamponunun kısayola
        # basıldığı anda dolu olması gerekiyor (Properties I.3).
        try:
            context.mic.start_stream()
        except AudioDeviceError as exc:
            # Mikrofonsuz da açılabilmeli: kullanıcı geçmişe bakmak veya
            # ayarları değiştirmek için uygulamayı açmış olabilir.
            log.warning("Mikrofon akışı açılamadı; dikte devre dışı — %s", exc)
        yield
        context.shutdown()

    app = FastAPI(
        title="OmniVoice Engine",
        version=__version__,
        docs_url=None,  # Yerel motor; dışa dönük belge sunmasına gerek yok.
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.context = context

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Hafif sağlık kontrolü. Anahtar değeri değil, yalnız varlığı bildirilir."""
        return {
            "status": "ok",
            "version": __version__,
            "providers": get_settings().configured_providers,
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        context.add_client(websocket)
        log.info("İstemci bağlandı")

        try:
            await websocket.send_json(
                {
                    "type": "ready",
                    "version": __version__,
                    "providers": get_settings().configured_providers,
                    "state": context.pipeline.state.value,
                }
            )

            while True:
                message = await websocket.receive_json()
                await _handle_message(websocket, context, message)

        except WebSocketDisconnect:
            log.info("İstemci ayrıldı")
        except Exception:
            log.exception("WebSocket oturumu hatayla sonlandı")
        finally:
            context.remove_client(websocket)

    return app


async def _handle_message(
    websocket: WebSocket, context: EngineContext, message: Any
) -> None:
    """Gelen komutları işler."""
    if not isinstance(message, dict):
        return

    kind = message.get("type")
    request_id = message.get("id")

    async def reply(payload: dict[str, Any]) -> None:
        """İstek/yanıt eşleşmesi için `id` geri yansıtılır."""
        await websocket.send_json({**payload, "id": request_id} if request_id else payload)

    match kind:
        case "hello":
            log.info("El sıkışıldı: %s", message.get("client", "bilinmiyor"))

        case "ping":
            await reply({"type": "pong"})

        # ── Dikte ─────────────────────────────────────────────────────────
        case "dictation:toggle":
            await context.pipeline.toggle()

        case "dictation:start":
            await context.pipeline.start()

        case "dictation:stop":
            await context.pipeline.stop()

        case "dictation:cancel":
            await context.pipeline.cancel()

        case "dictation:paste":
            await context.pipeline.paste(message.get("text"))

        # ── Mikrofon ──────────────────────────────────────────────────────
        case "devices:list":
            await reply(
                {
                    "type": "devices:list",
                    "devices": await asyncio.to_thread(list_input_devices),
                    "current": context.mic.device,
                    "streaming": context.mic.is_streaming,
                }
            )

        case "devices:set":
            device = message.get("device")
            index = None if device is None else int(device)
            try:
                await asyncio.to_thread(context.mic.set_device, index)
                error = None
            except AudioDeviceError as exc:
                # Aygıt açılamadı; mikrofon eskisine geri döndü. Hata arayüze
                # taşınır, motor ayakta kalır.
                log.warning("Mikrofon değiştirilemedi: %s", exc)
                error = str(exc)

            await reply(
                {
                    "type": "devices:set",
                    "current": context.mic.device,
                    "streaming": context.mic.is_streaming,
                    "error": error,
                }
            )

        # ── Kasa ──────────────────────────────────────────────────────────
        case "vault:list":
            entries = await asyncio.to_thread(list_entries)
            await reply(
                {
                    "type": "vault:list",
                    "entries": [
                        {
                            "provider": e.provider,
                            "configured": e.configured,
                            "masked": e.masked,
                        }
                        for e in entries
                    ],
                }
            )

        # ── İstatistik ve geçmiş ──────────────────────────────────────────
        case "stats:get":
            stats = await asyncio.to_thread(context.db.today_stats)
            spend = await asyncio.to_thread(context.db.spend_summary)
            await reply(
                {
                    "type": "stats:get",
                    "today": stats,
                    "spend": {
                        "todayUsd": spend.today_usd,
                        "monthUsd": spend.month_usd,
                        "totalUsd": spend.total_usd,
                        "callCount": spend.call_count,
                        "budgetUsd": context.budget_usd,
                    },
                }
            )

        case "history:search":
            query = str(message.get("query", ""))
            rows = await asyncio.to_thread(context.db.search_dictations, query, 50)
            await reply({"type": "history:search", "items": rows})

        case unknown:
            log.warning("Bilinmeyen mesaj tipi: %r", unknown)
