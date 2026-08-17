"""Dikte boru hattı — kısayoldan yapıştırmaya kadar tüm akış.

Durum makinesi:

    idle ──start──▶ listening ──stop──▶ processing ──▶ preflight
      ▲                  │                   │             │
      └──────cancel──────┴───────────────────┴──── paste ──┘

Her aşama arayüze bir olay yayar; HUD bu olaylara göre üç durumundan birini
gösterir (mockup 1c).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from omnivoice_engine.audio.capture import AudioClip, MicrophoneCapture
from omnivoice_engine.context.apps import AppProfile, profile_for
from omnivoice_engine.context.selection import read_selection, truncate_selection
from omnivoice_engine.context.variables import VariableContext, inject, mentions_selection
from omnivoice_engine.integrations.git import read_context_for_window
from omnivoice_engine.integrations.screen import Region, ScreenCaptureError, capture_region
from omnivoice_engine.llm.openrouter import OpenRouterLlm
from omnivoice_engine.output.formats import PasteFormat, apply_format, detect_format
from omnivoice_engine.output.paste import PasteError, paste_text, read_clipboard_text
from omnivoice_engine.output.window import WindowInfo, get_foreground_window
from omnivoice_engine.pipeline.fillers import strip_fillers
from omnivoice_engine.pipeline.modes import Mode, ModeId, get_mode
from omnivoice_engine.pipeline.prompts import build_prompt, sanitize_output
from omnivoice_engine.pipeline.vision_prompts import screen_question_prompt
from omnivoice_engine.providers import ProviderError
from omnivoice_engine.storage.db import Database, DictationRecord
from omnivoice_engine.privacy.masking import MaskResult, mask_all
from omnivoice_engine.storage.queue import ClipQueue
from omnivoice_engine.storage.snippets import SnippetLibrary
from omnivoice_engine.storage.vocabulary import Vocabulary
from omnivoice_engine.stt.router import SttRouter

log = logging.getLogger(__name__)

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

#: Ses seviyesi arayüze bu sıklıkta gönderilir. 20 Hz dalga formu için akıcı,
#: WebSocket için hafif.
_LEVEL_INTERVAL = 0.05

#: Otomatik durdurma için "konuşma var" sayılan seviye (Faz 7.3).
#:
#: `is_silent()` ile aynı eşik değil ve olmamalı: orası "bu kaydı sağlayıcıya
#: göndermeye değer mi" sorusunu yanıtlıyor, burası "kullanıcı hâlâ konuşuyor
#: mu". Buradaki eşik daha yüksek, çünkü oda gürültüsünü konuşma sanıp kaydı
#: sonsuza kadar açık tutmak, erken kapatmaktan daha can sıkıcı.
_SPEECH_LEVEL = 0.012

#: Sessizlik bu kadar sürerse kayıt kendiliğinden biter. 0 = kapalı.
#:
#: 1.6 sn ölçüyle değil, konuşma ritmiyle seçildi: normal bir cümle içi
#: duraklamadan uzun, kullanıcıyı bekletmeyecek kadar kısa. Ayarlanabilir,
#: çünkü doğru değeri ancak kullanan kişi bilir.
DEFAULT_AUTO_STOP_SECONDS = 1.6


class SilenceWatcher:
    """Otomatik durdurma kararını veren durum makinesi (Faz 7.3).

    Karar mantığı bilinçli olarak seviye döngüsünden ayrı: zamana bağlı bir
    döngü içinde sınanması güvenilmez oluyor — ilk denemede iki test, döngü
    hiç dönmediği için boş yere "geçmişti".

    İki tuzak var ve ikisi de kaydı mahveder:

    1. **Konuşmadan önce durmak.** Kullanıcı kısayola basıp bir an düşünürse
       kayıt daha başlamadan biter. Sayaç bu yüzden ancak konuşma
       duyulduktan sonra işlemeye başlıyor.
    2. **Cümle arasında durmak.** İnsanlar cümle ortasında nefes alır ve
       virgülde durur.
    """

    def __init__(self, *, threshold_seconds: float, speech_level: float = _SPEECH_LEVEL) -> None:
        self.threshold_seconds = threshold_seconds
        self.speech_level = speech_level
        self.heard_speech = False
        self.silent_for = 0.0

    @property
    def enabled(self) -> bool:
        return self.threshold_seconds > 0

    def observe(self, level: float, elapsed: float) -> bool:
        """Bir ölçüm işler. Kaydın bitmesi gerekiyorsa `True` döner."""
        if not self.enabled:
            return False

        if level >= self.speech_level:
            self.heard_speech = True
            self.silent_for = 0.0
            return False

        if not self.heard_speech:
            # Henüz konuşma duyulmadı: kullanıcı düşünüyor olabilir.
            return False

        self.silent_for += elapsed
        # Kayan nokta toleransı: 0.05 on kez toplanınca 0.4999999999999999
        # çıkıyor ve eşik bir tur geç tetikleniyor. Tek başına 50 ms'lik bir
        # gecikme ama adım hızı değişirse birikerek büyür.
        return self.silent_for >= self.threshold_seconds - 1e-9


class DictationState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    PREFLIGHT = "preflight"
    SILENT = "silent"
    """Kayıtta konuşma yoktu. Hata değil ama sessizce geçilmemeli."""
    CLIPBOARD = "clipboard"
    """Doğrudan yapıştırılamadı; metin panoda bekliyor.

    Ayrı bir durum, çünkü HUD `idle` olunca kapanıyor. Kullanıcıya Ctrl+V'ye
    basması gerektiğini söylemeden kaybolursak, metnin yok olduğunu sanır —
    oysa konuşması duruyor.
    """
    ERROR = "error"


@dataclass
class DictationResult:
    """Pre-flight'ta kullanıcıya gösterilen sonuç."""

    raw_text: str
    final_text: str
    fillers_removed: int
    language: str | None
    stt_provider: str
    stt_model: str
    stt_ms: int
    llm_provider: str | None
    llm_model: str | None
    llm_ms: int
    total_ms: int
    cost_usd: float
    audio_seconds: float
    target: WindowInfo | None = None
    record_id: int | None = None
    mode: str = "quick"
    profile: str = "plain"
    app_display_name: str | None = None
    #: Seçili metnin uzunluğu — arayüzde rozet olarak gösterilir.
    selection_chars: int = 0
    #: Doldurulan dinamik değişkenler.
    variables: tuple[str, ...] = ()
    #: Kullanıcının sesle istediği yapıştırma biçimi (Properties V.7).
    paste_format: PasteFormat | None = None
    #: Buluta gitmeden önce maskelenen hassas değer sayısı.
    pii_masked: int = 0
    #: Tetiklenen snippet'in adı — arayüzde rozet olarak gösterilir.
    #:
    #: Göstermek şart: eşleşme bulanık olduğu için yanlış şablon tetiklenebilir
    #: ve kullanıcı bunu ancak çıktıya bakınca anlar. Adı pre-flight'ta
    #: görürse hatayı yapıştırmadan önce yakalar.
    snippet: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "rawText": self.raw_text,
            "finalText": self.final_text,
            "fillersRemoved": self.fillers_removed,
            "language": self.language,
            "sttProvider": self.stt_provider,
            "sttModel": self.stt_model,
            "sttMs": self.stt_ms,
            "llmProvider": self.llm_provider,
            "llmModel": self.llm_model,
            "llmMs": self.llm_ms,
            "totalMs": self.total_ms,
            "costUsd": self.cost_usd,
            "audioSeconds": round(self.audio_seconds, 2),
            "appName": self.app_display_name
            or (self.target.app_name if self.target else None),
            "windowTitle": self.target.title if self.target else None,
            "recordId": self.record_id,
            "mode": self.mode,
            "profile": self.profile,
            "selectionChars": self.selection_chars,
            "variables": list(self.variables),
            "pasteFormat": self.paste_format.value if self.paste_format else None,
            "snippet": self.snippet,
            "piiMasked": self.pii_masked,
        }


@dataclass
class _Session:
    """Tek bir dikte oturumunun geçici durumu."""

    started_at: float
    target: WindowInfo | None
    pre_roll_seconds: float
    mode: Mode
    profile: AppProfile
    level_task: asyncio.Task[None] | None = field(default=None, repr=False)
    #: Ekran modunda kaydedilen bölge görüntüsü (data URL).
    #:
    #: Görüntü kayıt BAŞLARKEN alınır, bitince değil: kullanıcı konuşurken
    #: ekran değişmiş olabilir ve o zaman sorduğu şeyin resmi elde kalmaz.
    screen_image: str | None = None
    screen_size: tuple[int, int] | None = None


class DictationPipeline:
    """Dikte akışını yöneten orkestratör."""

    def __init__(
        self,
        *,
        mic: MicrophoneCapture,
        stt: SttRouter,
        llm: OpenRouterLlm,
        db: Database,
        emit: EventSink,
        vocabulary: Vocabulary | None = None,
        snippets: SnippetLibrary | None = None,
        mask_pii: bool = True,
        queue: ClipQueue | None = None,
        auto_stop_seconds: float = DEFAULT_AUTO_STOP_SECONDS,
        app_modes: dict[str, str] | None = None,
    ) -> None:
        self._mic = mic
        self._stt = stt
        self._llm = llm
        self._db = db
        self._emit = emit
        self._vocabulary = vocabulary
        self._snippets = snippets
        #: PII maskeleme varsayılan olarak AÇIK. Kapatmak bilinçli bir karar
        #: olmalı, unutulan bir ayar değil.
        self._mask_pii = mask_pii
        self._queue = queue
        self._auto_stop_seconds = auto_stop_seconds
        #: Süreç adı → mod kimliği (Faz 7.5).
        self._app_modes = dict(app_modes or {})

        self.state = DictationState.IDLE
        self._session: _Session | None = None
        self._result: DictationResult | None = None
        #: Aynı anda tek dikte; kısayola iki kez basılırsa yarış olmasın.
        self._lock = asyncio.Lock()

    # ── Gizlilik ──────────────────────────────────────────────────────────

    @property
    def pii_masking(self) -> bool:
        """Hassas veri maskeleme açık mı (Properties VI.1)."""
        return self._mask_pii

    def set_pii_masking(self, enabled: bool) -> None:
        self._mask_pii = enabled

    # ── Otomatik durdurma (Faz 7.3) ───────────────────────────────────────

    @property
    def auto_stop_seconds(self) -> float:
        """Kaydı bitiren sessizlik süresi; 0 ise otomatik durdurma kapalı."""
        return self._auto_stop_seconds

    # ── Uygulama başına mod (Faz 7.5) ─────────────────────────────────────

    @property
    def app_modes(self) -> dict[str, str]:
        return dict(self._app_modes)

    def set_app_modes(self, mapping: dict[str, str]) -> None:
        self._app_modes = dict(mapping)

    def set_auto_stop_seconds(self, seconds: float) -> None:
        # Üst sınır var: 10 saniyeden uzun bir eşik, özelliği kapatmakla
        # aynı şey ama kullanıcı açık sanmaya devam eder.
        self._auto_stop_seconds = max(0.0, min(float(seconds), 10.0))

    # ── Durum yayını ──────────────────────────────────────────────────────

    async def _set_state(self, state: DictationState, **extra: Any) -> None:
        self.state = state
        await self._emit({"type": "dictation:state", "state": state.value, **extra})

    # ── Akış ──────────────────────────────────────────────────────────────

    async def start(
        self,
        mode: ModeId | str = ModeId.QUICK,
        *,
        region: dict[str, int] | None = None,
    ) -> None:
        """Kaydı başlatır. Zaten kayıttaysa yok sayar.

        `region` yalnız ekran modunda gelir; kaplamada seçilen dikdörtgen.
        """
        async with self._lock:
            if self.state in {
                DictationState.LISTENING,
                DictationState.PROCESSING,
                DictationState.PREFLIGHT,
            }:
                log.debug("start() yok sayıldı, durum: %s", self.state)
                return

            # Hedef pencereyi kayıt başlarken yakalıyoruz: kullanıcı konuşurken
            # başka bir pencereye geçerse metin yine doğru yere gitmeli.
            target = get_foreground_window()
            resolved_mode = get_mode(mode)

            # Uygulama başına varsayılan mod (Faz 7.5).
            #
            # YALNIZ genel kısayoldan gelindiğinde uygulanıyor. Kullanıcı
            # Ctrl+Alt+K ile kod modunu açıkça seçtiyse bunu ezmek, verdiği
            # kararı görmezden gelmek olurdu — ve neden başka bir modda
            # çalıştığını hiçbir yerde göremezdi.
            if resolved_mode.id is ModeId.QUICK and target and self._app_modes:
                key = target.process_name.lower().removesuffix(".exe").strip()
                mapped = self._app_modes.get(key)
                if mapped:
                    try:
                        resolved_mode = get_mode(mapped)
                        log.info("Uygulama modu uygulandı: %s → %s", key, mapped)
                    except (KeyError, ValueError):
                        log.warning("Bilinmeyen uygulama modu yok sayıldı: %s", mapped)
            profile = profile_for(target.process_name if target else "")

            # Ekran görüntüsü kayıttan ÖNCE alınır: kullanıcı konuşurken ekran
            # değişebilir ve sorduğu şeyin resmi elde kalmaz.
            screen_image: str | None = None
            screen_size: tuple[int, int] | None = None
            if resolved_mode.uses_screen_region and region:
                try:
                    capture = await asyncio.to_thread(
                        capture_region,
                        Region(
                            x=int(region["x"]),
                            y=int(region["y"]),
                            width=int(region["width"]),
                            height=int(region["height"]),
                        ),
                    )
                    screen_image = capture.to_data_url()
                    screen_size = (capture.width, capture.height)
                    log.info("Ekran bölgesi yakalandı: %dx%d", capture.width, capture.height)
                except ScreenCaptureError as exc:
                    await self._set_state(DictationState.ERROR, message=str(exc))
                    return

            if not self._mic.is_streaming:
                self._mic.start_stream()

            pre_roll = self._mic.start_recording()
            self._session = _Session(
                started_at=time.perf_counter(),
                target=target,
                pre_roll_seconds=pre_roll,
                mode=resolved_mode,
                profile=profile,
                screen_image=screen_image,
                screen_size=screen_size,
            )
            self._result = None

            await self._set_state(
                DictationState.LISTENING,
                preRollSeconds=round(pre_roll, 2),
                appName=profile.display_name or (target.app_name if target else None),
                windowTitle=target.title if target else None,
                mode=resolved_mode.id.value,
                profile=profile.profile.value,
            )
            self._session.level_task = asyncio.create_task(self._stream_level())
            log.info(
                "Dikte başladı (mod: %s, pre-roll %.2f sn, hedef: %s / %s)",
                resolved_mode.id.value,
                pre_roll,
                profile.display_name or "bilinmiyor",
                profile.profile.value,
            )

    async def _stream_level(self) -> None:
        """Ses seviyesini akıtır ve sessizlikte kaydı bitirir (Faz 7.3).

        Otomatik durdurmanın iki tuzağı var ve ikisi de kaydı mahveder:

        1. **Konuşmadan önce durmak.** Kullanıcı kısayola basıp bir an
           düşünürse kayıt daha başlamadan biter. Bu yüzden sayaç ancak
           **konuşma duyulduktan sonra** işlemeye başlıyor.
        2. **Cümle arasında durmak.** İnsanlar cümle ortasında nefes alır ve
           virgülde durur. Eşik bu yüzden 1.6 sn — normal bir duraklamadan
           uzun, ama "bitirdim" jestini beklemekten kısa.
        """
        watcher = SilenceWatcher(threshold_seconds=self._auto_stop_seconds)

        try:
            while self.state is DictationState.LISTENING:
                level = self._mic.level
                await self._emit(
                    {
                        "type": "dictation:level",
                        # Duraklatılmışken dalga formu ölü görünmeli; canlı bir
                        # dalga, kaydın sürdüğü izlenimini verirdi.
                        "level": 0.0 if self._mic.is_paused else round(level, 4),
                        "seconds": round(self._mic.recorded_seconds, 2),
                        "paused": self._mic.is_paused,
                    }
                )

                # Duraklatılmışken sessizlik sayılmamalı: kullanıcı zaten
                # bilerek susuyor ve dönmeyi bekliyor.
                if self._mic.is_paused:
                    await asyncio.sleep(_LEVEL_INTERVAL)
                    continue

                if watcher.observe(level, _LEVEL_INTERVAL):
                    log.info(
                        "Sessizlik %.1f sn sürdü — kayıt otomatik bitiriliyor",
                        watcher.silent_for,
                    )
                    await self._emit({"type": "dictation:auto-stop"})
                    # `stop()` kilidi alıyor ve bu görevi iptal ediyor; ayrı bir
                    # görevde çağırmak kendini iptal eden bir kilitlenmeyi önler.
                    asyncio.create_task(self.stop())
                    return

                await asyncio.sleep(_LEVEL_INTERVAL)
        except asyncio.CancelledError:
            # Beklenen: `stop()` ve `cancel()` bu görevi iptal ediyor.
            pass
        except Exception:  # noqa: BLE001
            # Bu görevi kimse beklemiyor, yani buradaki bir istisna SESSİZCE
            # yutulurdu: dalga formu donar ve otomatik durdurma çalışmaz ama
            # hiçbir yerde iz kalmaz. Testte tam olarak bu oldu — sahte
            # mikrofonda eksik bir alan, yeşil bir test paketi altında
            # gizlendi.
            log.exception("Seviye döngüsü beklenmedik şekilde durdu")

    async def toggle_pause(self) -> None:
        """Kaydı duraklatır veya sürdürür (Faz 7.4).

        Duraklatma ayrı bir durum DEĞİL, `listening` içinde bir alt durum:
        HUD'un yerinde kalması ve kullanıcının kaydın sürdüğünü görmesi
        gerekiyor. Ayrı bir durum yapmak, bitmiş bir kayıtla karıştırılırdı.
        """
        if self.state is not DictationState.LISTENING or self._session is None:
            return

        if self._mic.is_paused:
            changed = self._mic.resume_recording()
        else:
            changed = self._mic.pause_recording()
        if not changed:
            return

        paused = self._mic.is_paused
        log.info("Kayıt %s", "duraklatıldı" if paused else "sürdürüldü")
        await self._emit(
            {
                "type": "dictation:state",
                "state": DictationState.LISTENING.value,
                "paused": paused,
                "seconds": round(self._mic.recorded_seconds, 2),
            }
        )

    async def stop(self) -> None:
        """Kaydı bitirir ve işlemeye geçer."""
        async with self._lock:
            if self.state is not DictationState.LISTENING or self._session is None:
                return
            session = self._session
            if session.level_task:
                session.level_task.cancel()

            clip = self._mic.stop_recording()

            # Sessiz kaydı sağlayıcıya göndermiyoruz: Whisper boş sese metin
            # uydurur ("Thank you.", "Altyazı M.K."). Kullanıcı kısayola yanlışlıkla
            # basmış olabilir; ona uydurma bir cümle yapıştırmak yerine sessizce
            # boşa dönüyoruz.
            if clip.is_silent():
                log.info(
                    "Kayıt sessiz (tepe %.6f, rms %.6f) — sağlayıcıya gönderilmedi",
                    clip.peak,
                    clip.rms,
                )
                self._session = None
                # Sessizce boşa dönmek kullanıcıya uygulamanın çöktüğünü
                # düşündürüyordu. Mutlak sessizlik (tepe ≈ 0) mikrofonun ölü
                # olduğunu gösterir; sadece kısık olmasından ayırıyoruz ki
                # doğru çözümü söyleyebilelim.
                await self._set_state(
                    DictationState.SILENT,
                    peak=round(clip.peak, 6),
                    deadMicrophone=clip.peak < 0.0005,
                    seconds=round(clip.duration_seconds, 1),
                )
                return

            await self._set_state(DictationState.PROCESSING, step="stt")

        # Ağ işleri kilidin dışında; kullanıcı bu sırada iptal edebilmeli.
        try:
            result = await self._process(clip_seconds=clip.duration_seconds, clip=clip, session=session)
        except ProviderError as exc:
            log.error("Dikte işlenemedi: %s", exc)
            self._session = None

            # Geçici hata (ağ kesikse, sağlayıcı 5xx/429 verdiyse) kaydı
            # kuyruğa alıyoruz. Kalıcı hatada (yanlış anahtar) ALMIYORUZ:
            # asla başarılı olmayacak bir kaydı diskte tutmak, kullanıcının
            # sesini boşuna saklamak olurdu.
            queued = False
            if exc.retryable and self._queue is not None:
                queued = await self._enqueue(clip, session.mode, str(exc))

            await self._set_state(
                DictationState.ERROR, message=str(exc), queued=queued
            )
            return
        except Exception as exc:  # noqa: BLE001 - beklenmedik hata arayüze taşınmalı
            log.exception("Dikte boru hattında beklenmedik hata")
            self._session = None
            await self._set_state(DictationState.ERROR, message=str(exc))
            return

        self._result = result
        self._session = None

        # Başarılı bir dikte bağlantının geri geldiğini kanıtlıyor; bekleyen
        # kayıtları denemek için ayrı bir yoklayıcı kurmaya gerek yok.
        # Arka planda: kullanıcı pre-flight'ta beklememeli.
        if self._queue is not None:
            asyncio.create_task(self._flush_queue_quietly())
        await self._set_state(DictationState.PREFLIGHT, result=result.to_payload())

    async def _process(
        self, *, clip_seconds: float, clip: Any, session: _Session
    ) -> DictationResult:
        started = session.started_at
        mode = session.mode

        # 1) Konuşma → metin. Sözlük STT'ye bağlam ipucu olarak gider;
        #    ölçtük, tireli terimlerin yazımı böyle korunuyor.
        stt_terms = self._vocabulary.stt_terms() if self._vocabulary else None
        transcript = await self._stt.transcribe(clip, language=None, vocabulary=stt_terms)
        self._db.add_spend(
            provider=transcript.provider,
            model=transcript.model,
            kind="stt",
            cost_usd=transcript.usage.cost_usd,
            latency_ms=transcript.usage.latency_ms,
            meta={"audioSeconds": round(clip_seconds, 2)},
        )

        # 2) Yerel dolgu temizliği — anlık ve bedava
        local = strip_fillers(transcript.text)

        # 3) Bağlam: seçili metin ve dinamik değişkenler
        selection = ""
        wants_selection = mode.uses_selection or mentions_selection(local.text)
        if wants_selection and session.target:
            # Ctrl+C göndermek bloklayıcı Win32 çağrıları içeriyor.
            selection = await asyncio.to_thread(read_selection, session.target.handle)
            selection = truncate_selection(selection)
            if selection:
                log.info("Seçili metin okundu: %d karakter", len(selection))

        # Git bağlamı: kullanıcı ne değiştirdiğini anlatmak zorunda kalmasın
        # (Properties V.5). Depo bulunamazsa mod diff'siz çalışmaya devam eder.
        git_diff: str | None = None
        git_summary: str | None = None
        if mode.uses_git_diff and session.target:
            context = await asyncio.to_thread(
                read_context_for_window,
                session.target.title,
                session.target.process_name,
            )
            if context and not context.is_empty:
                git_diff = context.diff
                git_summary = context.summary_line()
                log.info("Git bağlamı okundu: %s", git_summary)
            else:
                await self._emit(
                    {"type": "dictation:warning", "message": "Bekleyen git değişikliği bulunamadı"}
                )

        # Snippet tetikleme (Properties V.3). HAM metinden değil, dolgu
        # temizlenmiş metinden aranıyor: "şey, kod inceleme yap" içindeki
        # "şey" eşleşme oranını gereksiz yere düşürürdü.
        snippet = self._snippets.find(local.text) if self._snippets else None
        if snippet is not None:
            log.info("Snippet tetiklendi: %s", snippet.name)

        variables = VariableContext(
            app_name=session.profile.display_name
            or (session.target.app_name if session.target else ""),
            window_title=session.target.title if session.target else "",
            selected_text=selection,
            clipboard=await asyncio.to_thread(read_clipboard_text) or "",
        )
        injected = inject(local.text, variables)

        # PII maskeleme (Properties VI.1) — buluta çıkmadan HEMEN önce.
        #
        # Dört parça birlikte maskeleniyor, çünkü ortak bir yer tutucu
        # haritası gerekiyor: aynı anahtar hem seçili metinde hem git diff'te
        # geçebilir ve ona iki farklı numara vermek geri çevirmeyi bozardı.
        #
        # En değerli hedef dikte metni DEĞİL: kullanıcı bir API anahtarını
        # sesli okumaz, ama `{ClipboardContent}` ve `{SelectedText}` gerçek
        # anahtar taşır, git diff'inde `.env` satırı çıkabilir.
        pii = MaskResult(text="")
        if self._mask_pii:
            (masked_text, masked_selection, masked_diff), pii = mask_all(
                injected.text, selection or None, git_diff
            )
            if pii.masked_count:
                log.info("PII maskelendi: %d değer", pii.masked_count)
                await self._emit(
                    {
                        "type": "dictation:pii",
                        "count": pii.masked_count,
                        "kinds": [kind.value for kind in pii.kinds],
                    }
                )
        else:
            masked_text, masked_selection, masked_diff = (
                injected.text,
                selection or None,
                git_diff,
            )

        await self._emit(
            {
                "type": "dictation:progress",
                "step": "llm",
                "rawText": transcript.text,
                "fillersRemoved": local.removed_count,
                "sttMs": transcript.usage.latency_ms,
                "selectionChars": len(selection),
                "variables": list(injected.used),
                "snippet": snippet.name if snippet else None,
            }
        )

        # 4) LLM ile moda ve ortama duyarlı işleme
        llm_provider: str | None = None
        llm_model: str | None = None
        llm_ms = 0
        llm_cost = 0.0
        final_text = injected.text

        if self._llm.is_available() and injected.text:
            try:
                if session.screen_image:
                    # Ekran modunun istemi ayrı: burada iş metni temizlemek
                    # değil, görüntüyü okuyup soruyu yanıtlamak.
                    prompt = screen_question_prompt(
                        masked_text,
                        session.screen_image,
                        language=transcript.language,
                    )
                else:
                    prompt = build_prompt(
                        masked_text,
                        mode=mode,
                        profile=session.profile.profile,
                        app_name=session.profile.display_name or None,
                        vocabulary=self._vocabulary.llm_terms() if self._vocabulary else None,
                        language=transcript.language,
                        selection=masked_selection,
                        git_diff=masked_diff,
                        git_summary=git_summary,
                        snippet=snippet.body if snippet else None,
                    )
                completion = await self._llm.complete(prompt, model=mode.model)
                # Yer tutucular gerçek değerlere geri çevriliyor: değer buluta
                # gitmedi ama kullanıcının metninde eksiksiz duruyor.
                final_text = pii.unmask(sanitize_output(completion.text)) or injected.text
                llm_provider = completion.provider
                llm_model = completion.model
                llm_ms = completion.usage.latency_ms
                llm_cost = completion.usage.cost_usd or 0.0
                self._db.add_spend(
                    provider=completion.provider,
                    model=completion.model,
                    kind="llm",
                    cost_usd=completion.usage.cost_usd,
                    latency_ms=completion.usage.latency_ms,
                    meta={
                        "inputTokens": completion.usage.input_tokens,
                        "outputTokens": completion.usage.output_tokens,
                    },
                )
            except ProviderError as exc:
                # LLM düşerse dikteyi kaybetmiyoruz: yerel olarak temizlenmiş
                # metin hâlâ kullanılabilir.
                log.warning("LLM katmanı atlandı: %s", exc)
                await self._emit(
                    {"type": "dictation:warning", "message": f"LLM atlandı: {exc}"}
                )

        total_ms = int((time.perf_counter() - started) * 1000)
        cost = (transcript.usage.cost_usd or 0.0) + llm_cost

        result = DictationResult(
            raw_text=transcript.text,
            final_text=final_text,
            fillers_removed=local.removed_count,
            language=transcript.language,
            stt_provider=transcript.provider,
            stt_model=transcript.model,
            stt_ms=transcript.usage.latency_ms,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_ms=llm_ms,
            total_ms=total_ms,
            cost_usd=cost,
            audio_seconds=clip_seconds,
            target=session.target,
            # Biçim isteği HAM metinden okunur: LLM temizlerken "json olarak"
            # ifadesini çıkarmış olabilir ama kullanıcı onu söylemişti.
            paste_format=detect_format(transcript.text),
            snippet=snippet.name if snippet else None,
            pii_masked=pii.masked_count,
            mode=mode.id.value,
            profile=session.profile.profile.value,
            app_display_name=session.profile.display_name or None,
            selection_chars=len(selection),
            variables=injected.used,
        )

        result.record_id = self._db.add_dictation(
            DictationRecord(
                raw_text=result.raw_text,
                final_text=result.final_text,
                mode=mode.id.value,
                app_name=session.profile.display_name
                or (session.target.app_name if session.target else None),
                window_title=session.target.title if session.target else None,
                language=result.language,
                stt_provider=result.stt_provider,
                stt_model=result.stt_model,
                llm_provider=result.llm_provider,
                llm_model=result.llm_model,
                audio_seconds=result.audio_seconds,
                fillers_removed=result.fillers_removed,
                stt_ms=result.stt_ms,
                llm_ms=result.llm_ms,
                total_ms=result.total_ms,
                cost_usd=result.cost_usd,
            )
        )

        if snippet is not None and self._snippets is not None:
            # Sayaç diske yazıyor; olay döngüsünü bekletmesin.
            await asyncio.to_thread(self._snippets.mark_used, snippet.name)

        return result

    async def paste(self, text: str | None = None) -> None:
        """Pre-flight'taki metni hedef pencereye yapıştırır."""
        result = self._result
        if self.state is not DictationState.PREFLIGHT or result is None:
            return

        # Kullanıcı önizlemede düzenlemiş olabilir.
        content = text if text is not None else result.final_text

        # Biçim dönüşümü yapıştırma anında uygulanır, üretim anında değil:
        # kullanıcı pre-flight'ta metni düzenlerse dönüşüm ona da uygulanmalı.
        if result.paste_format is not None:
            content = apply_format(content, result.paste_format)

        try:
            # Yapıştırma bloklayıcı Win32 çağrıları içeriyor; olay döngüsünü
            # kilitlememek için iş parçacığına alıyoruz.
            outcome = await asyncio.to_thread(
                paste_text,
                content,
                window_handle=result.target.handle if result.target else None,
            )
        except PasteError as exc:
            # Buraya yalnız metin hiçbir yere konulamadıysa düşülür.
            log.error("Yapıştırma başarısız: %s", exc)
            await self._set_state(DictationState.ERROR, message=str(exc))
            return

        if result.record_id:
            self._db.mark_pasted(result.record_id)

        self._result = None

        # Panoya düşmek hata DEĞİL: kullanıcı konuşmasını kaybetmedi. Ama
        # Ctrl+V'ye basması gerektiğini bilmeli, yoksa metin kaybolmuş sanır.
        if outcome.needs_manual_paste:
            log.info("Metin panoda bırakıldı: %d karakter", len(content))
            await self._set_state(
                DictationState.CLIPBOARD, message=outcome.reason, chars=len(content)
            )
            return

        await self._set_state(DictationState.IDLE, pasted=True)
        log.info("Yapıştırıldı: %d karakter", len(content))

    # ── Kuyruk (Faz 7.2) ──────────────────────────────────────────────────

    async def _enqueue(self, clip: AudioClip, mode: Mode, error: str) -> bool:
        """Başarısız kaydı diske alır."""
        if self._queue is None:
            return False
        try:
            data, _, _ = await asyncio.to_thread(clip.to_upload_bytes)
        except Exception:  # noqa: BLE001 - kodlama hatası kuyruğu çökertmesin
            log.warning("Kayıt kodlanamadı, kuyruğa alınamıyor", exc_info=True)
            return False

        suffix = ".flac" if data[:4] == b"fLaC" else ".wav"
        item = await asyncio.to_thread(
            self._queue.add,
            audio=data,
            suffix=suffix,
            mode=mode.id.value,
            duration_seconds=clip.duration_seconds,
            error=error,
        )
        if item is not None:
            await self._emit({"type": "queue:changed", **self._queue.to_payload()})
        return item is not None

    async def flush_queue(self) -> dict[str, int]:
        """Kuyruktaki kayıtları yeniden göndermeyi dener.

        **Sonuç yapıştırılmıyor, geçmişe yazılıyor.** Kullanıcı o kayıttan
        sonra başka bir işe geçmiş olabilir; şu an odaktaki pencereye metin
        göndermek yanlış yere yazmak demektir ve geri alınamaz.

        Bir kayıt yine geçici bir hatayla düşerse kuyrukta kalıyor; kalıcı
        hatayla düşerse **çıkarılıyor** — sonsuza kadar denemenin anlamı yok
        ve diskte duran sesin gizlilik maliyeti sürüyor.
        """
        if self._queue is None:
            return {"sent": 0, "failed": 0, "dropped": 0}

        items = await asyncio.to_thread(self._queue.items)
        sent = failed = dropped = 0

        for item in items:
            try:
                data = await asyncio.to_thread(item.audio_path.read_bytes)
                clip = await asyncio.to_thread(AudioClip.from_encoded_bytes, data)
            except Exception:  # noqa: BLE001
                log.warning("Kuyruktaki kayıt okunamadı: %s", item.item_id, exc_info=True)
                await asyncio.to_thread(self._queue.remove, item)
                dropped += 1
                continue

            await asyncio.to_thread(self._queue.mark_attempt, item)

            try:
                transcript = await self._stt.transcribe(
                    clip,
                    language=None,
                    vocabulary=self._vocabulary.stt_terms() if self._vocabulary else None,
                )
            except ProviderError as exc:
                if exc.retryable:
                    log.info("Kuyruk kaydı hâlâ gönderilemiyor: %s", exc)
                    failed += 1
                    # Ağ hâlâ kapalıysa kalanları denemek boşuna.
                    break
                log.warning("Kuyruk kaydı kalıcı hatayla düştü: %s", exc)
                await asyncio.to_thread(self._queue.remove, item)
                dropped += 1
                continue

            self._db.add_dictation(
                DictationRecord(
                    raw_text=transcript.text,
                    final_text=transcript.text,
                    mode=item.mode,
                    app_name=None,
                    window_title=None,
                    language=transcript.language,
                    stt_provider=transcript.provider,
                    stt_model=transcript.model,
                    llm_provider=None,
                    llm_model=None,
                    audio_seconds=item.duration_seconds,
                    fillers_removed=0,
                    stt_ms=transcript.usage.latency_ms,
                    llm_ms=0,
                    total_ms=transcript.usage.latency_ms,
                    cost_usd=transcript.usage.cost_usd or 0.0,
                )
            )
            # Gönderildi: ses diskte kalmamalı.
            await asyncio.to_thread(self._queue.remove, item)
            sent += 1

        if sent or dropped or failed:
            await self._emit(
                {
                    "type": "queue:changed",
                    "sent": sent,
                    "failed": failed,
                    "dropped": dropped,
                    **self._queue.to_payload(),
                }
            )
        return {"sent": sent, "failed": failed, "dropped": dropped}

    async def _flush_queue_quietly(self) -> None:
        """Arka planda kuyruğu boşaltır; hatası dikteyi etkilemez."""
        try:
            await self.flush_queue()
        except Exception:  # noqa: BLE001 - arka plan görevi sessizce ölmemeli
            log.warning("Kuyruk boşaltma başarısız", exc_info=True)

    async def cancel(self) -> None:
        """Akışı iptal eder — Esc."""
        async with self._lock:
            if self._session and self._session.level_task:
                self._session.level_task.cancel()
            self._mic.cancel_recording()
            self._session = None
            self._result = None
            await self._set_state(DictationState.IDLE, cancelled=True)

    async def toggle(
        self, mode: ModeId | str = ModeId.QUICK, *, region: dict[str, int] | None = None
    ) -> None:
        """Kısayolun davranışı: boştaysa başlat, dinliyorsa bitir."""
        # SILENT, CLIPBOARD ve ERROR birer bilgilendirme durumu; kısayola
        # tekrar basmak yeni bir dikte başlatmalı, kullanıcıyı önce kapatmaya
        # zorlamamalı.
        if self.state in {
            DictationState.IDLE,
            DictationState.SILENT,
            DictationState.CLIPBOARD,
            DictationState.ERROR,
        }:
            await self.start(mode, region=region)
        elif self.state is DictationState.LISTENING:
            await self.stop()
        # İşleme veya pre-flight sırasında kısayol yok sayılır; kullanıcı
        # Enter veya Esc ile karar verir.
