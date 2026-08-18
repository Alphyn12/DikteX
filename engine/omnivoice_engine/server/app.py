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
from omnivoice_engine.audio.loopback import list_loopback_devices, loopback_available
from omnivoice_engine.audio.capture import (
    AudioDeviceError,
    MicrophoneCapture,
    list_input_devices,
    refresh_devices,
)
from omnivoice_engine.config import get_settings
from omnivoice_engine.llm.gemini import GeminiLlm
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.pipeline.dictation import (
    DEFAULT_AUTO_STOP_SECONDS,
    DictationPipeline,
    DictationState,
)
from omnivoice_engine.pipeline.meeting import MeetingPipeline
from omnivoice_engine.pipeline.modes import MODES, get_mode
from omnivoice_engine.pipeline.numbers import normalize_numbers
from omnivoice_engine.pipeline.replacements import ReplacementLibrary
from omnivoice_engine.pipeline.style import StyleLibrary
from omnivoice_engine.providers import ProviderError
from omnivoice_engine.storage.db import Database
from omnivoice_engine.storage.export import to_json, to_markdown
from omnivoice_engine.input.hotkey_hook import PushToTalkHook
from omnivoice_engine.llm.catalog import ModelCatalog, fetch_gemini_models
from omnivoice_engine.storage.queue import ClipQueue
from omnivoice_engine.storage.settings_store import SettingsStore
from omnivoice_engine.storage.snippets import SnippetLibrary
from omnivoice_engine.storage.vocabulary import Vocabulary
from omnivoice_engine.stt.router import SttRouter
from omnivoice_engine.output.paste import write_clipboard_text
from omnivoice_engine.output.window import get_foreground_window
from omnivoice_engine.vault import get_key, list_entries

log = logging.getLogger(__name__)


class EngineContext:
    """Motorun uzun ömürlü parçaları.

    Tek örnek: mikrofon akışı, veritabanı bağlantısı ve boru hattı uygulama
    ömrü boyunca yaşar. WebSocket bağlantıları gelip gider, bunlar kalır.
    """

    def __init__(self) -> None:
        settings = get_settings()
        # Kullanıcı ayarları EN ÖNCE yükleniyor: mikrofon ve model seçimleri
        # boru hatları kurulmadan uygulanmalı, yoksa ilk dikte yanlış
        # yapılandırmayla çalışır.
        self.user_settings = SettingsStore.load()
        self.catalog = ModelCatalog()
        self.mic = MicrophoneCapture(pre_roll_seconds=1.0)
        self.stt = SttRouter()
        # Sağlayıcı seçimi kalıcı; varsayılan OpenRouter çünkü eğitime
        # kapalı. Gemini'nin ücretsiz katmanı eğitime açık ve bunu kullanıcı
        # bilerek seçmeli.
        self.llm_provider_name = self.user_settings.settings.llm_provider or "openrouter"
        self.llm = self._make_llm(self.llm_provider_name)
        self.db = Database()
        self.vocabulary = Vocabulary.load()
        self.snippets = SnippetLibrary.load()
        self.replacements = ReplacementLibrary.load()
        self.style = StyleLibrary.load(
            enabled=bool(self.user_settings.settings.style_learning)
        )
        self.queue = ClipQueue()
        self.budget_usd = settings.budget_usd
        #: Basılı tut kancası — yalnız kip açıkken kuruluyor (Faz 7.7).
        self.ptt: PushToTalkHook | None = None

        saved = self.user_settings.settings
        self.llm.set_default_model(saved.llm_model)
        if saved.stt_model:
            for provider in self.stt.providers:
                # Sağlayıcıların model alanı ortak değil; olanı ayarlıyoruz.
                if hasattr(provider, "model"):
                    provider.model = saved.stt_model

        #: Bağlı arayüz istemcileri. Olaylar hepsine yayınlanır.
        self._clients: set[WebSocket] = set()

        self.pipeline = DictationPipeline(
            mic=self.mic,
            stt=self.stt,
            llm=self.llm,
            db=self.db,
            emit=self.broadcast,
            vocabulary=self.vocabulary,
            snippets=self.snippets,
            queue=self.queue,
            mask_pii=True if saved.mask_pii is None else saved.mask_pii,
            auto_stop_seconds=(
                DEFAULT_AUTO_STOP_SECONDS
                if saved.auto_stop_seconds is None
                else saved.auto_stop_seconds
            ),
            app_modes=saved.app_modes,
            preflight_enabled=True if saved.preflight is None else saved.preflight,
            replacements=self.replacements,
            style=self.style,
            normalize_numbers_enabled=(
                True if saved.normalize_numbers is None else saved.normalize_numbers
            ),
        )

        # Toplantı boru hattı aynı mikrofonu paylaşıyor; ikisi aynı anda
        # çalışamaz ve bu `_handle_message` içinde engelleniyor.
        self.meeting = MeetingPipeline(
            mic=self.mic,
            stt=self.stt,
            llm=self.llm,
            db=self.db,
            emit=self.broadcast,
            mask_pii=True if saved.mask_pii is None else saved.mask_pii,
        )

    # ── Metin işleme sağlayıcısı ──────────────────────────────────────────

    @staticmethod
    def _make_llm(name: str) -> Any:
        return GeminiLlm() if name == "gemini" else OpenRouterLlm()

    def set_llm_provider(self, name: str) -> bool:
        """Metin işleme sağlayıcısını değiştirir.

        Anahtarı olmayan bir sağlayıcıya geçmeyi reddediyoruz: kullanıcı
        seçimin tuttuğunu sanıp her diktede hata alırdı.
        """
        if name not in {"openrouter", "gemini"}:
            return False

        candidate = self._make_llm(name)
        if not candidate.is_available():
            log.warning("Sağlayıcı seçilemedi, anahtarı yok: %s", name)
            return False

        # Model seçimi sağlayıcıya özgü; geçişte sıfırlanıyor, yoksa
        # OpenRouter kimliği (`google/gemini-...`) Gemini API'sine gider ve
        # her dikte 404 verirdi.
        self.llm = candidate
        self.llm_provider_name = name
        self.pipeline._llm = candidate  # noqa: SLF001
        self.meeting._llm = candidate  # noqa: SLF001
        log.info("Metin işleme sağlayıcısı: %s", name)
        return True

    # ── Basılı tut kipi (Faz 7.7) ─────────────────────────────────────────

    def set_push_to_talk(self, enabled: bool) -> bool:
        """Kancayı kurar veya kaldırır. Kurulamadıysa `False` döner.

        Kanca **yalnız kip açıkken** yaşıyor. Kapalıyken hiç yüklenmiyor:
        sistemdeki her tuşu gören bir kancayı kullanılmadığı hâlde taşımanın
        savunması yok.
        """
        if not enabled:
            if self.ptt is not None:
                self.ptt.stop()
                self.ptt = None
            return True

        if self.ptt is not None and self.ptt.is_running:
            return True

        loop = asyncio.get_running_loop()

        def fire(coro_factory: Any) -> None:
            # Kanca geri çağrımı Windows'un iş parçacığında ve **300 ms
            # içinde dönmek zorunda**; geç dönen kanca sessizce kaldırılıyor.
            # Bu yüzden burada yalnız olay döngüsüne iş bırakılıyor.
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(coro_factory()))

        self.ptt = PushToTalkHook(
            on_press=lambda: fire(lambda: self.pipeline.start()),
            on_release=lambda: fire(lambda: self.pipeline.stop()),
        )
        if not self.ptt.start():
            self.ptt = None
            return False
        return True

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
        if self.ptt is not None:
            # Kanca kaldırılmazsa süreç kapansa bile Windows bir süre
            # tutmaya devam ediyor.
            self.ptt.stop()
            self.ptt = None
        self.mic.stop_stream()
        self.db.close()


def create_app() -> FastAPI:
    context = EngineContext()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Kaydedilen mikrofon, akış AÇILMADAN ÖNCE uygulanıyor. Sonra
        # uygulamak akışı kapatıp yeniden açmayı gerektirirdi ve o aralıkta
        # pre-roll tamponu boş kalırdı.
        #
        # Aygıt ADLA çözümleniyor: PortAudio indeksleri aygıt takılıp
        # çıkarıldıkça kayıyor, kaydedilen indeks bir sonraki açılışta
        # bambaşka bir mikrofon olabilir.
        saved_name = context.user_settings.settings.microphone_name
        if saved_name:
            try:
                resolved = await asyncio.to_thread(
                    context.mic.resolve_device_by_name, saved_name
                )
                if resolved is None:
                    log.warning(
                        "Kaydedilen mikrofon bulunamadı (%s); sistem varsayılanı kullanılıyor",
                        saved_name,
                    )
                else:
                    # Akış henüz açık değil; `set_device` bu durumda yalnız
                    # indeksi ayarlıyor, aygıt açmaya çalışmıyor.
                    await asyncio.to_thread(context.mic.set_device, resolved)
                    log.info("Kaydedilen mikrofon uygulandı: %s", saved_name)
            except Exception:  # noqa: BLE001 - ayar hatası motoru düşürmemeli
                log.warning("Kaydedilen mikrofon uygulanamadı", exc_info=True)

        # Mikrofon akışını açılışta başlatıyoruz: pre-roll tamponunun kısayola
        # basıldığı anda dolu olması gerekiyor (Properties I.3).
        try:
            context.mic.start_stream()
        except AudioDeviceError as exc:
            # Kaydedilen aygıt artık açılamıyorsa (çıkarılmış, başka bir
            # uygulama tutuyor) kullanıcıyı mikrofonsuz bırakmıyoruz: sistem
            # varsayılanıyla bir kez daha deniyoruz. Aksi hâlde bir kez
            # kaydedilen bozuk seçim, dikteyi kalıcı olarak öldürürdü.
            if context.mic.device is not None:
                log.warning(
                    "Kaydedilen mikrofon açılamadı (%s); sistem varsayılanına dönülüyor",
                    exc,
                )
                try:
                    await asyncio.to_thread(context.mic.set_device, None)
                    context.mic.start_stream()
                except AudioDeviceError as fallback_exc:
                    log.warning(
                        "Mikrofon akışı açılamadı; dikte devre dışı — %s", fallback_exc
                    )
            else:
                # Mikrofonsuz da açılabilmeli: kullanıcı geçmişe bakmak veya
                # ayarları değiştirmek için uygulamayı açmış olabilir.
                log.warning("Mikrofon akışı açılamadı; dikte devre dışı — %s", exc)
        # Basılı tut kipi kaydedilmişse kancayı kur (Faz 7.7). Olay döngüsü
        # burada çalışıyor; `set_push_to_talk` ona ihtiyaç duyuyor.
        if context.user_settings.settings.push_to_talk:
            if not context.set_push_to_talk(True):
                log.warning("Basılı tut kipi kurulamadı; kip kapalı kalıyor")

        yield
        context.shutdown()

    app = FastAPI(
        title="DikteX Engine",
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
            await context.pipeline.toggle(
                str(message.get("mode", "quick")), region=message.get("region")
            )

        case "dictation:start":
            await context.pipeline.start(
                str(message.get("mode", "quick")), region=message.get("region")
            )

        case "dictation:stop":
            await context.pipeline.stop()

        case "dictation:pause":
            await context.pipeline.toggle_pause()

        case "dictation:cancel":
            await context.pipeline.cancel()

        case "dictation:retry-paste":
            # Yeniden yapıştırma (Faz 7.16). Global kısayoldan geliyor:
            # kullanıcı hedef pencereye tıkladıktan sonra basıyor, böylece
            # ön plandaki pencere doğru oluyor.
            await context.pipeline.paste(message.get("text"))

        case "dictation:draft":
            # Pre-flight'taki güncel metin (Faz 7.15). Sesli düzeltme global
            # kısayolla başlıyor ve o an arayüzden metin istemenin yolu yok.
            context.pipeline.set_draft(message.get("text"))

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
            # Arayüz indeksi listeden aldı; ama liste alındıktan sonra aygıtlar
            # değişmiş olabilir. Adla yeniden çözümlemek, kullanıcının seçtiği
            # aygıtın açılmasını garanti eder — indeks kaymışsa bile.
            device = message.get("device")
            name = message.get("name")
            index = None if device is None else int(device)
            try:
                if name and index is not None:
                    resolved = await asyncio.to_thread(
                        context.mic.resolve_device_by_name, str(name)
                    )
                    if resolved is not None:
                        index = resolved
                await asyncio.to_thread(context.mic.set_device, index)
                error = None
                # Seçim kalıcı: motor yeniden başladığında aynı mikrofon
                # açılmalı. Bu, kullanıcının bildirdiği "varsayılan mikrofonu
                # değiştiremiyorum" hatasının kalan yarısıydı — değiştirme
                # çalışıyordu ama her açılışta sıfırlanıyordu.
                await asyncio.to_thread(
                    context.user_settings.update,
                    microphone_name=str(name) if name and index is not None else None,
                )
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

        # ── Toplantı ──────────────────────────────────────────────────────
        case "meeting:toggle" | "meeting:start":
            # Dikte ve toplantı aynı mikrofonu kullanıyor; ikisi aynı anda
            # çalışırsa biri diğerinin kaydını çalar.
            if context.pipeline.state is not DictationState.IDLE:
                await reply(
                    {
                        "type": "meeting:state",
                        "state": "error",
                        "message": "Dikte sürerken toplantı kaydı başlatılamaz",
                    }
                )
            elif kind == "meeting:start":
                await context.meeting.start(system_device=message.get("device"))
            else:
                await context.meeting.toggle(system_device=message.get("device"))

        case "meeting:stop":
            await context.meeting.stop()

        case "meeting:cancel":
            await context.meeting.cancel()

        case "meeting:dismiss":
            await context.meeting.dismiss()

        case "meeting:devices":
            await reply(
                {
                    "type": "meeting:devices",
                    "devices": await asyncio.to_thread(list_loopback_devices),
                    "available": await asyncio.to_thread(loopback_available),
                }
            )

        case "meeting:history":
            rows = await asyncio.to_thread(context.db.recent_meetings, 20)
            await reply({"type": "meeting:history", "items": rows})

        # ── Modlar ────────────────────────────────────────────────────────
        case "modes:list":
            await reply(
                {
                    "type": "modes:list",
                    "modes": [
                        {
                            "id": mode.id.value,
                            "chordKey": mode.chord_key,
                            "module": mode.module,
                            "model": mode.model,
                            "requirePreflight": mode.require_preflight,
                            "usesSelection": mode.uses_selection,
                        }
                        for mode in MODES.values()
                    ],
                    "defaultModel": context.llm.default_model,
                }
            )

        # ── Sözlük ────────────────────────────────────────────────────────
        case "vocabulary:list":
            await reply({"type": "vocabulary:list", **context.vocabulary.to_payload()})

        case "vocabulary:add":
            text = str(message.get("text", ""))
            added = await asyncio.to_thread(context.vocabulary.add, text)
            await reply(
                {
                    "type": "vocabulary:add",
                    "added": added,
                    **context.vocabulary.to_payload(),
                }
            )

        case "vocabulary:remove":
            text = str(message.get("text", ""))
            removed = await asyncio.to_thread(context.vocabulary.remove, text)
            await reply(
                {
                    "type": "vocabulary:remove",
                    "removed": removed,
                    **context.vocabulary.to_payload(),
                }
            )

        # ── Snippet kütüphanesi ───────────────────────────────────────────
        case "snippets:list":
            await reply({"type": "snippets:list", **context.snippets.to_payload()})

        case "snippets:add":
            added = await asyncio.to_thread(
                context.snippets.add,
                str(message.get("name", "")),
                str(message.get("body", "")),
                [str(t) for t in message.get("triggers", []) if str(t).strip()],
            )
            await reply(
                {
                    "type": "snippets:add",
                    "added": added,
                    **context.snippets.to_payload(),
                }
            )

        case "snippets:remove":
            removed = await asyncio.to_thread(
                context.snippets.remove, str(message.get("name", ""))
            )
            await reply(
                {
                    "type": "snippets:remove",
                    "removed": removed,
                    **context.snippets.to_payload(),
                }
            )

        case "snippets:test":
            # Kullanıcı bir cümle yazıp hangi snippet'in tetikleneceğini
            # görebiliyor. Bulanık eşleşmede bu şart: aksi hâlde ayarı
            # ancak canlı dikte sırasında sınayabilir.
            match = context.snippets.find(str(message.get("text", "")))
            await reply(
                {
                    "type": "snippets:test",
                    "match": match.to_payload() if match else None,
                }
            )

        # ── Başarısız kayıt kuyruğu ───────────────────────────────────────
        case "queue:list":
            await reply({"type": "queue:list", **context.queue.to_payload()})

        case "queue:flush":
            stats = await context.pipeline.flush_queue()
            await reply({"type": "queue:flush", **stats, **context.queue.to_payload()})

        case "queue:remove":
            removed = await asyncio.to_thread(
                context.queue.remove_by_id, str(message.get("id", ""))
            )
            await reply(
                {"type": "queue:remove", "removed": removed, **context.queue.to_payload()}
            )

        case "queue:clear":
            count = await asyncio.to_thread(context.queue.clear)
            await reply({"type": "queue:clear", "cleared": count, **context.queue.to_payload()})

        # ── Öğrenen kişisel stil (Faz 3.13) ───────────────────────────────
        case "style:get":
            await reply({"type": "style:get", **context.style.to_payload()})

        case "style:set-enabled":
            enabled = bool(message.get("enabled", False))
            context.style.enabled = enabled
            await asyncio.to_thread(
                context.user_settings.update, style_learning=enabled
            )
            log.info("Stil öğrenme %s", "açık" if enabled else "KAPALI")
            await reply({"type": "style:get", **context.style.to_payload()})

        case "style:clear":
            cleared = await asyncio.to_thread(context.style.clear)
            await reply(
                {"type": "style:get", "cleared": cleared, **context.style.to_payload()}
            )

        # ── Değiştirme kuralları (Faz 7.8) ────────────────────────────────
        case "replacements:list":
            await reply({"type": "replacements:list", **context.replacements.to_payload()})

        case "replacements:add":
            added = await asyncio.to_thread(
                context.replacements.add,
                str(message.get("find", "")),
                str(message.get("replace", "")),
                whole_word=bool(message.get("wholeWord", True)),
            )
            await reply(
                {
                    "type": "replacements:add",
                    "added": added,
                    **context.replacements.to_payload(),
                }
            )

        case "replacements:remove":
            removed = await asyncio.to_thread(
                context.replacements.remove, str(message.get("find", ""))
            )
            await reply(
                {
                    "type": "replacements:remove",
                    "removed": removed,
                    **context.replacements.to_payload(),
                }
            )

        case "replacements:test":
            # Kural metni doğrudan değiştirdiği için deneme alanı şart:
            # kullanıcı kuralını canlı diktede sınamak zorunda kalmamalı.
            probe = str(message.get("text", ""))
            outcome = context.replacements.apply(probe)
            normalized = (
                normalize_numbers(outcome.text)
                if context.pipeline.normalize_numbers
                else outcome.text
            )
            await reply(
                {
                    "type": "replacements:test",
                    "input": probe,
                    "output": normalized,
                    "applied": list(outcome.applied),
                }
            )

        case "replacements:set-numbers":
            enabled = bool(message.get("enabled", True))
            context.pipeline.set_normalize_numbers(enabled)
            await asyncio.to_thread(
                context.user_settings.update, normalize_numbers=enabled
            )
            # Yanıt olarak tüm gizlilik yükü dönüyor: arayüz tek bir
            # kaynaktan okusun, iki ayrı durum tutmasın.
            await reply(_privacy_payload(context))

        # ── Basılı tut kipi (Faz 7.7) ─────────────────────────────────────
        case "ptt:get":
            await reply(_ptt_payload(context))

        case "ptt:set":
            enabled = bool(message.get("enabled", False))
            ok = context.set_push_to_talk(enabled)
            await asyncio.to_thread(
                context.user_settings.update, push_to_talk=enabled and ok
            )
            await reply(_ptt_payload(context))

        # ── Aygıt tak-çıkar (Faz 7.6) ─────────────────────────────────────
        case "devices:changed":
            result = await _handle_device_change(context)
            await reply({"type": "devices:changed", **result})

        # ── Uygulama başına mod (Faz 7.5) ─────────────────────────────────
        case "appmodes:get":
            await reply(_app_modes_payload(context))

        case "appmodes:set":
            app = str(message.get("app", "")).lower().removesuffix(".exe").strip()
            mode_id = message.get("mode")
            mapping = context.pipeline.app_modes

            if not app:
                await reply({"type": "appmodes:set", "error": "uygulama adı boş"})
                return

            if mode_id:
                try:
                    # Mod kimliğini burada doğruluyoruz: geçersiz bir değeri
                    # kaydetmek, dikte anında sessizce yok sayılmasına yol
                    # açardı ve kullanıcı ayarın çalışmadığını görürdü.
                    get_mode(str(mode_id))
                except (KeyError, ValueError):
                    await reply(
                        {"type": "appmodes:set", "error": f"bilinmeyen mod: {mode_id}"}
                    )
                    return
                mapping[app] = str(mode_id)
            else:
                mapping.pop(app, None)

            context.pipeline.set_app_modes(mapping)
            await asyncio.to_thread(context.user_settings.update, app_modes=mapping)
            await reply(_app_modes_payload(context))

        # ── Modeller (Faz 3.15) ───────────────────────────────────────────
        case "models:catalog":
            try:
                if context.llm_provider_name == "gemini":
                    # Sağlayıcıya göre farklı katalog: Gemini seçiliyken
                    # OpenRouter kimlikleri (`google/gemini-...`) göstermek,
                    # seçildiklerinde her diktede 404 üretirdi.
                    key = get_key("gemini")
                    models = await fetch_gemini_models(key) if key else []
                else:
                    models = await context.catalog.models(force=bool(message.get("force")))
                await reply(
                    {
                        "type": "models:catalog",
                        "models": [m.to_payload() for m in models],
                        "error": None,
                    }
                )
            except ProviderError as exc:
                # Katalog alınamazsa arayüz boş bir liste yerine sebebi
                # göstermeli; kullanıcı mevcut seçimini yine de görüyor.
                await reply({"type": "models:catalog", "models": [], "error": str(exc)})

        case "models:get":
            await reply(_models_payload(context))

        case "models:set-provider":
            name = str(message.get("provider", ""))
            ok = context.set_llm_provider(name)
            if ok:
                await asyncio.to_thread(
                    context.user_settings.update, llm_provider=name, llm_model=None
                )
                context.llm.set_default_model(None)
            await reply({**_models_payload(context), "changed": ok})

        case "models:set":
            role = str(message.get("role", ""))
            model = message.get("model")
            value = (str(model).strip() or None) if model is not None else None

            if role == "llm":
                context.llm.set_default_model(value)
                await asyncio.to_thread(context.user_settings.update, llm_model=value)
            elif role == "stt":
                for provider in context.stt.providers:
                    if hasattr(provider, "model") and value:
                        provider.model = value
                await asyncio.to_thread(context.user_settings.update, stt_model=value)
            elif role == "vision":
                await asyncio.to_thread(context.user_settings.update, vision_model=value)
            else:
                await reply({"type": "models:set", "error": f"bilinmeyen rol: {role}"})
                return

            log.info("Model değişti — %s: %s", role, value or "varsayılan")
            await reply(_models_payload(context))

        # ── Gizlilik ──────────────────────────────────────────────────────
        case "privacy:get":
            await reply(_privacy_payload(context))

        case "dictation:set-auto-stop":
            context.pipeline.set_auto_stop_seconds(float(message.get("seconds", 0)))
            await asyncio.to_thread(
                context.user_settings.update,
                auto_stop_seconds=context.pipeline.auto_stop_seconds,
            )
            await reply(_privacy_payload(context))

        case "dictation:set-preflight":
            enabled = bool(message.get("enabled", True))
            context.pipeline.set_preflight_enabled(enabled)
            await asyncio.to_thread(context.user_settings.update, preflight=enabled)
            await reply(_privacy_payload(context))

        case "privacy:set-masking":
            enabled = bool(message.get("enabled", True))
            # Aynı bayrak iki boru hattında da var; ikisi ayrışırsa toplantı
            # dökümü sessizce korumasız kalırdı.
            context.pipeline.set_pii_masking(enabled)
            context.meeting.set_pii_masking(enabled)
            await asyncio.to_thread(context.user_settings.update, mask_pii=enabled)
            log.info("PII maskeleme %s", "açık" if enabled else "KAPALI")
            await reply(_privacy_payload(context))

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
            stats["meetings"] = await asyncio.to_thread(context.db.meeting_count_today)
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

        case "history:delete":
            record_id = int(message.get("recordId", 0) or 0)
            deleted = await asyncio.to_thread(context.db.delete_dictation, record_id)
            log.info("Geçmiş kaydı silindi: %s (%s)", record_id, deleted)
            await reply({"type": "history:delete", "deleted": deleted})

        case "history:delete-all":
            count = await asyncio.to_thread(context.db.delete_all_dictations)
            log.info("Tüm dikte geçmişi silindi: %d kayıt", count)
            await reply({"type": "history:delete-all", "deleted": count})

        case "history:export":
            # Dosyayı motor DEĞİL, Electron yazıyor: kaydetme yeri kullanıcının
            # kararı ve yerli dosya penceresi orada. Motor yalnız içeriği
            # üretiyor.
            fmt = str(message.get("format", "markdown"))
            rows = await asyncio.to_thread(context.db.all_dictations)
            content = (
                to_json(rows) if fmt == "json" else to_markdown(rows)
            )
            log.info("Geçmiş dışa aktarıldı: %d kayıt, %s", len(rows), fmt)
            await reply(
                {
                    "type": "history:export",
                    "format": fmt,
                    "count": len(rows),
                    "content": content,
                }
            )

        case "history:paste":
            # Geçmişten yeniden yapıştırma (Faz 7.12).
            #
            # Dikte akışının aksine burada HEDEF PENCERE YOK: kullanıcı
            # uygulamanın içinde, arama ekranında. Metin o an odaktaki
            # pencereye gönderilemez — odakta DikteX var. Bu yüzden
            # doğrudan panoya yazılıyor ve kullanıcı istediği yere
            # Ctrl+V ile koyuyor.
            # `recordId`, `id` DEĞİL: `id` alanı istek/yanıt eşleştirmesi için
            # ayrılmış (bkz. `reply`). Kayıt kimliğini oraya koymak yanıtın
            # yanlış isteğe eşlenmesine yol açardı.
            record_id = int(message.get("recordId", 0) or 0)
            row = await asyncio.to_thread(context.db.get_dictation, record_id)
            if row is None:
                await reply({"type": "history:paste", "ok": False, "error": "kayıt yok"})
                return
            ok = await asyncio.to_thread(write_clipboard_text, str(row["final_text"]))
            log.info("Geçmiş kaydı panoya kopyalandı: %s", record_id)
            await reply(
                {
                    "type": "history:paste",
                    "ok": ok,
                    "chars": len(str(row["final_text"])),
                }
            )

        case "history:search":
            query = str(message.get("query", ""))
            rows = await asyncio.to_thread(context.db.search_dictations, query, 50)
            await reply({"type": "history:search", "items": rows})

        case unknown:
            log.warning("Bilinmeyen mesaj tipi: %r", unknown)


def _privacy_payload(context: EngineContext) -> dict[str, Any]:
    """Gizlilik ayarları ve **sınırları**.

    `sttCovered: False` bilinçli olarak yayınlanıyor. Maskeleme yalnız LLM
    ayağını koruyor; ses kaydı konuşma tanıma sağlayıcısına maskelenmeden
    gidiyor, çünkü maskelenecek metin oradan geliyor. Arayüzün bunu
    kullanıcıya söylemesi gerekiyor — "korunuyorsun" demek yanlış olurdu.
    """
    return {
        "type": "privacy:get",
        "maskPii": context.pipeline.pii_masking,
        "autoStopSeconds": context.pipeline.auto_stop_seconds,
        "preflight": context.pipeline.preflight_enabled,
        # Sayı normalizasyonu buraya sonradan eklendi. Motor değeri
        # kaydediyordu ama hiçbir yerden yayınlamıyordu; arayüz de her
        # açılışta "açık" varsayıyordu. Kullanıcı kapatıp uygulamayı yeniden
        # başlattığında anahtar açık görünüyor, boru hattı kapalı
        # çalışıyordu — anahtar durumu hakkında yalan söylüyordu.
        "normalizeNumbers": context.pipeline.normalize_numbers,
        "sttCovered": False,
        "llmCovered": context.pipeline.pii_masking,
    }


def _models_payload(context: EngineContext) -> dict[str, Any]:
    """Rol başına etkin model ve nereden geldiği.

    `source` alanı önemli: kullanıcı bir model seçtiğini sanıp aslında
    varsayılanı kullanıyor olabilir. Hangi değerin nereden geldiğini
    göstermek bu karışıklığı kapatıyor.
    """
    saved = context.user_settings.settings
    settings = get_settings()
    privacy = context.llm.info.privacy.value
    stt_model = next(
        (p.model for p in context.stt.providers if hasattr(p, "model")), settings.stt_model
    )
    return {
        "type": "models:get",
        "provider": context.llm_provider_name,
        # Gizlilik sınıfı arayüze taşınıyor: aynı model iki sağlayıcıda
        # farklı sınıfta olabiliyor ve kullanıcı bunu görmeli.
        "providerPrivacy": privacy,
        "llm": {
            "model": context.llm.default_model,
            "source": "user" if saved.llm_model else "default",
        },
        "stt": {
            "model": stt_model,
            "source": "user" if saved.stt_model else "default",
        },
        "vision": {
            # Görsel için ayrı seçim yoksa LLM modeli kullanılıyor.
            "model": saved.vision_model or context.llm.default_model,
            "source": "user" if saved.vision_model else "llm",
        },
    }


def _app_modes_payload(context: EngineContext) -> dict[str, Any]:
    """Uygulama → mod eşlemesi ve o an odaktaki uygulama.

    Odaktaki uygulama da gönderiliyor: kullanıcının süreç adını (`Code.exe`)
    elle yazması beklenemez, arayüz "şu an açık olanı ekle" diyebilmeli.
    """
    focused = get_foreground_window()
    return {
        "type": "appmodes:get",
        "modes": context.pipeline.app_modes,
        "focused": (
            {
                "process": focused.process_name,
                "name": focused.app_name,
            }
            if focused
            else None
        ),
    }


async def _handle_device_change(context: EngineContext) -> dict[str, Any]:
    """Ses aygıtları değiştiğinde mikrofonu düzeltir (Faz 7.6).

    Sinyal arayüzden geliyor: Chromium'un `navigator.mediaDevices.devicechange`
    olayı. Motor tarafında yoklama yapmak mümkün değil — PortAudio'nun aygıt
    listesini tazelemek (`refresh_devices`) kütüphaneyi yeniden başlatıyor ve
    **açık akışları geçersiz kılıyor**. Saniyede bir bunu yapmak mikrofonu
    sürekli kesintiye uğratırdı.

    İki iş yapılıyor:

    1. **Tercih edilen aygıt geri geldiyse ona dönülür.** Kullanıcı kulaklığını
       çıkarıp taktığında elle yeniden seçmek zorunda kalmamalı.
    2. **Kullanılan aygıt kaybolduysa** sistem varsayılanına düşülür. Aksi
       hâlde akış ölü kalır ve bu ancak boş bir kayıtla fark edilir.
    """
    # Kayıt sürerken aygıt değiştirmek kaydı bozar; kullanıcı konuşmasını
    # bitirsin, sonraki dikte doğru aygıtla başlar.
    if context.pipeline.state is not DictationState.IDLE:
        log.info("Aygıt değişikliği ertelendi: dikte sürüyor")
        return {"applied": False, "reason": "busy"}

    preferred = context.user_settings.settings.microphone_name
    current = context.mic.device

    try:
        # Akışı kapatmak zorundayız: `refresh_devices` PortAudio'yu yeniden
        # başlatıyor ve açık akış geçersiz hâle geliyor.
        was_streaming = context.mic.is_streaming
        if was_streaming:
            await asyncio.to_thread(context.mic.stop_stream)
        await asyncio.to_thread(refresh_devices)

        target: int | None = None
        if preferred:
            target = await asyncio.to_thread(context.mic.resolve_device_by_name, preferred)
            if target is None:
                log.info("Tercih edilen mikrofon hâlâ yok: %s", preferred)

        # `set_device` akış kapalıyken yalnız indeksi ayarlıyor.
        await asyncio.to_thread(context.mic.set_device, target)
        if was_streaming:
            context.mic.start_stream()

        applied = target != current
        if applied:
            log.info("Aygıt değişikliği uygulandı: %s → %s", current, target)
            await context.broadcast(
                {
                    "type": "devices:list",
                    "devices": await asyncio.to_thread(list_input_devices),
                    "current": context.mic.device,
                    "streaming": context.mic.is_streaming,
                }
            )
        return {"applied": applied, "current": context.mic.device}

    except AudioDeviceError as exc:
        # Hedef açılamadı; sistem varsayılanına düşüp kullanıcıyı mikrofonsuz
        # bırakmıyoruz.
        log.warning("Aygıt değişikliği sonrası mikrofon açılamadı: %s", exc)
        try:
            await asyncio.to_thread(context.mic.set_device, None)
            context.mic.start_stream()
        except AudioDeviceError:
            log.warning("Sistem varsayılanı da açılamadı", exc_info=True)
        return {"applied": False, "reason": str(exc)}


def _ptt_payload(context: EngineContext) -> dict[str, Any]:
    """Basılı tut kipinin gerçek durumu.

    `enabled` ile `available` ayrı: kanca kurulamamış olabilir (başka bir
    uygulama engelliyor, güvenlik yazılımı vb.). Kullanıcıya "açık" demek ama
    çalışmamak, en kötü ikisi.
    """
    running = context.ptt is not None and context.ptt.is_running
    return {
        "type": "ptt:get",
        "enabled": running,
        "requested": bool(context.user_settings.settings.push_to_talk),
    }
