"""Sistem sesi kaydı — iki yönlü toplantı yakalama (Properties III.1).

Toplantıda iki ses kaynağı vardır: kendi mikrofonun ve hoparlörden gelen
diğer katılımcılar. İkisini birlikte yakalamak için Windows'un **WASAPI
loopback** yeteneği kullanılır: bir çıkış aygıtı giriş gibi açılır ve
hoparlöre giden ses okunur.

`sounddevice` bu bayrağı dışarı açmıyor, bu yüzden `soundcard` kütüphanesi
kullanılıyor. O da kendi WASAPI bağlarını taşıdığı için PortAudio ile
çakışmıyor — iki kütüphane yan yana sorunsuz çalışıyor.

## İki akışı neden ayrı tutuyoruz

Konuşmacı ayrımı (diarization) kapsam dışı bırakıldı; ayrı bir sağlayıcı
hesabı gerektiriyordu. Ama mikrofon ile loopback zaten **fiziksel olarak
ayrı** iki kaynak: biri sen, diğeri karşı taraf. İkisini ayrı çevirip
etiketlemek, hiçbir ek servis olmadan "ben / diğerleri" ayrımı veriyor.
Tam diarization değil ama toplantı özeti için çoğu zaman yeterli.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

from omnivoice_engine.audio.capture import (
    SAMPLE_RATE,
    AudioClip,
    resample,
)

log = logging.getLogger(__name__)

#: Loopback aygıtları genelde 48 kHz stereo çalışır; 16 kHz'e biz indiriyoruz.
_CAPTURE_RATE = 48_000
_BLOCK_FRAMES = 4800  # 100 ms


@dataclass
class MeetingRecording:
    """Bir toplantı kaydının iki kanalı."""

    #: Kullanıcının mikrofonu — "ben".
    microphone: AudioClip | None
    #: Hoparlöre giden ses — "diğerleri".
    system: AudioClip | None
    duration_seconds: float

    @property
    def has_audio(self) -> bool:
        return bool(
            (self.microphone and not self.microphone.is_silent())
            or (self.system and not self.system.is_silent())
        )

    def mixed(self) -> AudioClip:
        """İki kanalı tek bir kayda karıştırır.

        Etiketli döküm istenmediğinde (veya bir kanal boş olduğunda) kullanılır.
        Karıştırırken genlik yarıya indirilir; toplamak kırpma (clipping)
        üretirdi.
        """
        clips = [c for c in (self.microphone, self.system) if c and len(c.samples)]
        if not clips:
            return AudioClip(samples=np.zeros(0, dtype=np.int16), sample_rate=SAMPLE_RATE)
        if len(clips) == 1:
            return clips[0]

        length = max(len(c.samples) for c in clips)
        accumulator = np.zeros(length, dtype=np.float32)
        for clip in clips:
            accumulator[: len(clip.samples)] += clip.samples.astype(np.float32)
        accumulator /= len(clips)
        return AudioClip(
            samples=np.clip(accumulator, -32768, 32767).astype(np.int16),
            sample_rate=SAMPLE_RATE,
        )


class _LoopbackStream:
    """Tek bir loopback aygıtından okuyan iş parçacığı.

    `soundcard`'ın kaydedicisi bloklayıcı çalışır, bu yüzden kendi iş
    parçacığında döner. Durdurma bayrağı ile sonlanır.
    """

    def __init__(self, device_name: str | None = None) -> None:
        self._device_name = device_name
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: str | None = None
        self._level = 0.0

    def start(self) -> None:
        self._stop.clear()
        self._chunks = []
        self._error = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="loopback")
        self._thread.start()

    def _run(self) -> None:
        com_ready = False
        try:
            # `soundcard` Windows Media Foundation üzerinden COM kullanıyor ve
            # COM **her iş parçacığında ayrı ayrı** başlatılmalı. Bunu atlamak
            # `0x800401f0 CO_E_NOTINITIALIZED` veriyor — ana iş parçacığında
            # çalışan kod sorunsuz, arka planda çalışan aynı kod düşüyor.
            import pythoncom

            pythoncom.CoInitialize()
            com_ready = True
        except Exception:  # noqa: BLE001 - COM zaten başlatılmış olabilir
            log.debug("CoInitialize atlandı", exc_info=True)

        try:
            import soundcard as sc

            if self._device_name:
                device = sc.get_microphone(self._device_name, include_loopback=True)
            else:
                # Varsayılan hoparlörün loopback'i — kullanıcı sesi nereden
                # duyuyorsa oradan kaydediyoruz.
                device = sc.get_microphone(
                    str(sc.default_speaker().name), include_loopback=True
                )

            with device.recorder(samplerate=_CAPTURE_RATE, blocksize=_BLOCK_FRAMES) as rec:
                while not self._stop.is_set():
                    data = rec.record(numframes=_BLOCK_FRAMES)
                    # soundcard float32 [-1, 1] döndürür ve çok kanallı olabilir.
                    mono = data.mean(axis=1) if data.ndim > 1 else data
                    with self._lock:
                        self._chunks.append(mono.astype(np.float32))
                        self._level = float(np.sqrt(np.mean(mono**2)))
        except Exception as exc:  # noqa: BLE001 - kayıt iş parçacığı sessizce ölmemeli
            self._error = str(exc)
            log.warning("Sistem sesi kaydı başarısız: %s", exc, exc_info=True)
        finally:
            if com_ready:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:  # noqa: BLE001
                    pass

    def stop(self) -> AudioClip:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        with self._lock:
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return AudioClip(samples=np.zeros(0, dtype=np.int16), sample_rate=SAMPLE_RATE)

        # float32 [-1,1] → int16, sonra 48 kHz → 16 kHz
        merged = np.concatenate(chunks)
        as_int16 = np.clip(merged * 32767.0, -32768, 32767).astype(np.int16)
        return AudioClip(
            samples=resample(as_int16, _CAPTURE_RATE, SAMPLE_RATE),
            sample_rate=SAMPLE_RATE,
        )

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def level(self) -> float:
        return self._level


class MeetingRecorder:
    """Mikrofon ve sistem sesini eşzamanlı kaydeder.

    Mikrofon tarafını mevcut `MicrophoneCapture` yürütür; burada yalnız
    loopback yönetiliyor ve iki kayıt tek sonuçta buluşturuluyor.
    """

    def __init__(self) -> None:
        self._loopback: _LoopbackStream | None = None
        self._started_at = 0.0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self._started_at if self._recording else 0.0

    @property
    def system_level(self) -> float:
        return self._loopback.level if self._loopback else 0.0

    def start(self, device_name: str | None = None) -> None:
        if self._recording:
            return
        self._loopback = _LoopbackStream(device_name)
        self._loopback.start()
        self._started_at = time.perf_counter()
        self._recording = True
        log.info("Toplantı kaydı başladı (sistem sesi: %s)", device_name or "varsayılan")

    def stop(self, microphone_clip: AudioClip | None = None) -> MeetingRecording:
        if not self._recording:
            return MeetingRecording(microphone=None, system=None, duration_seconds=0.0)

        duration = self.elapsed_seconds
        self._recording = False

        system_clip: AudioClip | None = None
        if self._loopback:
            system_clip = self._loopback.stop()
            if self._loopback.error:
                # Sistem sesi alınamadıysa kaydı büsbütün kaybetmiyoruz;
                # mikrofon tarafı hâlâ değerli.
                log.warning("Sistem sesi kanalı boş: %s", self._loopback.error)
                system_clip = None
            self._loopback = None

        log.info(
            "Toplantı kaydı bitti (%.1f dk · mikrofon %s · sistem %s)",
            duration / 60,
            "var" if microphone_clip and len(microphone_clip.samples) else "yok",
            "var" if system_clip and len(system_clip.samples) else "yok",
        )
        return MeetingRecording(
            microphone=microphone_clip, system=system_clip, duration_seconds=duration
        )


def list_loopback_devices() -> list[dict[str, object]]:
    """Kaydedilebilir çıkış aygıtları (hoparlör / kulaklık)."""
    try:
        import soundcard as sc

        default_name = str(sc.default_speaker().name)
        devices: list[dict[str, object]] = []
        for speaker in sc.all_speakers():
            name = str(speaker.name)
            devices.append({"name": name, "isSystemDefault": name == default_name})
        return devices
    except Exception:  # noqa: BLE001
        log.warning("Loopback aygıtları listelenemedi", exc_info=True)
        return []


def loopback_available() -> bool:
    """Sistem sesi kaydı bu makinede mümkün mü?"""
    try:
        import soundcard as sc

        return bool(sc.all_speakers())
    except Exception:  # noqa: BLE001
        return False


