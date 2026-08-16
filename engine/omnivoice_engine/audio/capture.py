"""Mikrofon yakalama ve sıfır gecikmeli dairesel ön bellek (Properties I.3).

Sorun: kullanıcı kısayola bastığında ilk heceyi çoktan söylemiş olur. Kayda
tuşa basıldığı anda başlarsak o hece yutulur.

Çözüm: mikrofon sürekli dinlenir ve son birkaç saniye dairesel bir tamponda
tutulur. Kısayola basıldığında tamponun son 1 saniyesi kaydın **başına**
eklenir. Böylece kullanıcı tuşa basmadan önce söylediği hece de kayda girer.

Gizlilik: bu tampon yalnız bellektedir, hiçbir zaman diske yazılmaz ve kısayola
basılmadıkça hiçbir yere gönderilmez. Sürekli dinleme istenmiyorsa
`pre_roll_seconds=0` ile kapatılabilir; o zaman mikrofon yalnız kayıt sırasında
açılır.
"""

from __future__ import annotations

import logging
import threading
import wave
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

#: Whisper 16 kHz mono ile çalışır; kaynağı doğrudan bu oranda açmak hem
#: yeniden örnekleme hatasını hem de yükleme boyutunu ortadan kaldırır.
SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = np.int16
BLOCK_SIZE = 1600  # 100 ms


@dataclass(frozen=True, slots=True)
class AudioClip:
    """Kaydedilmiş ses. Sağlayıcılara bu biçimde verilir."""

    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    def to_wav_bytes(self) -> bytes:
        """16-bit PCM WAV. STT sağlayıcılarının hepsi bu biçimi kabul eder."""
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(2)  # int16
            wav.setframerate(self.sample_rate)
            wav.writeframes(self.samples.astype(np.int16).tobytes())
        return buffer.getvalue()


class _RingBuffer:
    """Sabit boyutlu dairesel tampon. Dolduğunda en eskiyi ezer."""

    def __init__(self, capacity: int) -> None:
        self._data = np.zeros(capacity, dtype=DTYPE)
        self._capacity = capacity
        self._write = 0
        self._filled = 0

    def write(self, block: np.ndarray) -> None:
        n = len(block)
        if n >= self._capacity:
            # Blok tampondan büyükse yalnız son kısmı anlamlı.
            self._data[:] = block[-self._capacity :]
            self._write = 0
            self._filled = self._capacity
            return

        end = self._write + n
        if end <= self._capacity:
            self._data[self._write : end] = block
        else:
            split = self._capacity - self._write
            self._data[self._write :] = block[:split]
            self._data[: end - self._capacity] = block[split:]

        self._write = end % self._capacity
        self._filled = min(self._filled + n, self._capacity)

    def read_last(self, count: int) -> np.ndarray:
        """En son yazılan `count` örneği kronolojik sırada döndürür."""
        count = min(count, self._filled)
        if count == 0:
            return np.zeros(0, dtype=DTYPE)

        start = (self._write - count) % self._capacity
        if start + count <= self._capacity:
            return self._data[start : start + count].copy()
        split = self._capacity - start
        return np.concatenate([self._data[start:], self._data[: count - split]])

    def clear(self) -> None:
        self._filled = 0
        self._write = 0


class MicrophoneCapture:
    """Sürekli dinleyen mikrofon akışı.

    Akış uygulama açık olduğu sürece çalışır; `start_recording()` yalnız
    örnekleri biriktirmeye başlar. Böylece kayıt komutu ile ilk örnek arasında
    aygıt açma gecikmesi olmaz.
    """

    def __init__(self, *, pre_roll_seconds: float = 1.0, device: int | None = None) -> None:
        self.pre_roll_seconds = pre_roll_seconds
        self._device = device
        # Ön belleği istenen süreden biraz büyük tutuyoruz ki blok sınırında
        # yuvarlama yüzünden eksik kalmasın.
        capacity = max(int(SAMPLE_RATE * (pre_roll_seconds + 0.5)), BLOCK_SIZE)
        self._ring = _RingBuffer(capacity)

        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._chunks: list[np.ndarray] = []
        #: Son bloğun RMS'i, 0.0–1.0. Arayüzdeki dalga formu bunu kullanır.
        self._level = 0.0

    # ── Akış yaşam döngüsü ────────────────────────────────────────────────

    def start_stream(self) -> None:
        """Mikrofon akışını açar. Zaten açıksa bir şey yapmaz."""
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            device=self._device,
            callback=self._on_block,
        )
        self._stream.start()
        log.info(
            "Mikrofon akışı açıldı (%d Hz, pre-roll %.1f sn)",
            SAMPLE_RATE,
            self.pre_roll_seconds,
        )

    def stop_stream(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            self._ring.clear()
            self._chunks.clear()
            self._recording = False
            self._level = 0.0
        log.info("Mikrofon akışı kapatıldı")

    @property
    def is_streaming(self) -> bool:
        return self._stream is not None

    @property
    def device(self) -> int | None:
        return self._device

    def set_device(self, device: int | None) -> None:
        """Mikrofonu değiştirir.

        Akış açıksa yeni aygıtla yeniden açılır. Kayıt sırasında aygıt
        değiştirmek kaydı bozacağı için o durumda yok sayılır.
        """
        if device == self._device:
            return
        if self._recording:
            log.warning("Kayıt sürerken mikrofon değiştirilemez")
            return

        was_streaming = self.is_streaming
        if was_streaming:
            self.stop_stream()
        self._device = device
        if was_streaming:
            self.start_stream()
        log.info("Mikrofon değiştirildi: %s", device if device is not None else "sistem varsayılanı")

    # ── Ses geri çağrımı ──────────────────────────────────────────────────

    def _on_block(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        """PortAudio iş parçacığında çalışır — burada ağır iş yapılmaz."""
        if status:
            log.debug("Ses akışı durumu: %s", status)

        block = indata[:, 0].copy()

        with self._lock:
            self._ring.write(block)
            if self._recording:
                self._chunks.append(block)
            # RMS'i int16 tam ölçeğine göre normalize ediyoruz.
            self._level = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)) / 32768.0)

    # ── Kayıt ─────────────────────────────────────────────────────────────

    def start_recording(self) -> float:
        """Kaydı başlatır ve ön bellekten alınan pre-roll süresini döndürür."""
        with self._lock:
            pre_roll = self._ring.read_last(int(SAMPLE_RATE * self.pre_roll_seconds))
            self._chunks = [pre_roll] if len(pre_roll) else []
            self._recording = True
            return len(pre_roll) / SAMPLE_RATE

    def stop_recording(self) -> AudioClip:
        """Kaydı durdurur ve biriken sesi döndürür."""
        with self._lock:
            self._recording = False
            chunks = self._chunks
            self._chunks = []

        samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=DTYPE)
        return AudioClip(samples=samples, sample_rate=SAMPLE_RATE)

    def cancel_recording(self) -> None:
        """Kaydı atar — Esc ile iptal."""
        with self._lock:
            self._recording = False
            self._chunks = []

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def level(self) -> float:
        """Anlık ses seviyesi, 0.0–1.0."""
        return self._level

    @property
    def recorded_seconds(self) -> float:
        with self._lock:
            return sum(len(c) for c in self._chunks) / SAMPLE_RATE


#: Aynı fiziksel mikrofon her host API altında ayrı bir aygıt olarak görünür
#: (MME, DirectSound, WASAPI, WDM-KS). Kullanıcıya dört kopya göstermenin
#: anlamı yok; en iyi olanı seçip diğerlerini eliyoruz.
_HOST_API_PREFERENCE = ("Windows WASAPI", "Windows DirectSound", "MME")

#: WDM-KS çekirdek akış katmanıdır; aygıtları sürücü yolu adıyla listeler
#: ("@System32\\drivers\\bthhfenum.sys,#2;%1") ve gerçek aygıtların hepsi zaten
#: üstteki üç API'de görünür. Kullanıcıya gösterilecek bir şey değil.
_EXCLUDED_HOST_APIS = frozenset({"Windows WDM-KS"})

#: Toplayıcı sanal aygıtlar. "Sistem varsayılanı" seçeneğini zaten ayrıca
#: sunduğumuz için bunları listelemek kafa karıştırır.
_EXCLUDED_NAMES = frozenset(
    {
        "microsoft ses eşleştiricisi - input",
        "microsoft sound mapper - input",
        "birincil ses yakalama sürücüsü",
        "primary sound capture driver",
    }
)


def _is_listable(name: str, host_api: str) -> bool:
    """Aygıt kullanıcıya gösterilmeye değer mi?"""
    if host_api in _EXCLUDED_HOST_APIS:
        return False
    lowered = name.strip().lower()
    if not lowered or lowered in _EXCLUDED_NAMES:
        return False
    # Sürücü yolu adları: "@System32\drivers\...sys,#2;%1 Hands-Free"
    if lowered.startswith("@") or ".sys," in lowered:
        return False
    # "Input ()" gibi boş adlar
    return lowered not in {"input ()", "output ()"}


def list_input_devices() -> list[dict[str, object]]:
    """Kullanılabilir mikrofonlar — aygıt başına tek satır.

    Ayarlar ekranındaki mikrofon seçicisi bunu kullanır. Aynı ada sahip
    kopyalardan yalnız en tercih edilen host API'deki tutulur.
    """
    try:
        host_apis = sd.query_hostapis()
        devices = sd.query_devices()
        default_index = sd.default.device[0]
    except Exception:  # noqa: BLE001 - ses alt sistemi yoksa liste boş dönsün
        log.warning("Ses aygıtları listelenemedi", exc_info=True)
        return []

    def rank(host_api_index: int) -> int:
        name = str(host_apis[host_api_index]["name"])
        return _HOST_API_PREFERENCE.index(name) if name in _HOST_API_PREFERENCE else 99

    # Ad → en iyi aday
    best: dict[str, dict[str, object]] = {}
    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue
        name = str(device["name"]).strip()
        host_api_name = str(host_apis[device["hostapi"]]["name"])
        if not _is_listable(name, host_api_name):
            continue

        candidate = {
            "index": index,
            "name": name,
            "hostApi": str(host_apis[device["hostapi"]]["name"]),
            "channels": int(device["max_input_channels"]),
            "sampleRate": int(device["default_samplerate"]),
            "isSystemDefault": index == default_index,
            "_rank": rank(int(device["hostapi"])),
        }

        current = best.get(name)
        if current is None:
            best[name] = candidate
            continue

        # Sistem varsayılanı olan kopyayı korumak, sıralamadan önce gelir —
        # kullanıcının Windows'ta seçtiği aygıt listede işaretli görünmeli.
        if candidate["isSystemDefault"] and not current["isSystemDefault"]:
            best[name] = candidate
        elif candidate["_rank"] < current["_rank"] and not current["isSystemDefault"]:
            best[name] = candidate

    result = sorted(
        best.values(),
        # Varsayılan en üstte, kalanlar alfabetik.
        key=lambda d: (not d["isSystemDefault"], str(d["name"]).lower()),
    )
    for item in result:
        item.pop("_rank", None)
    return result
