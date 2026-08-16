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


class AudioDeviceError(RuntimeError):
    """Ses aygıtı açılamadı veya değiştirilemedi."""


def _friendly_open_error(device_name: str, errors: list[str]) -> str:
    """Ham PortAudio hatasını kullanıcının anlayacağı bir cümleye çevirir.

    `AUDCLNT_E_UNSUPPORTED_FORMAT | Invalid sample rate | Invalid device`
    dizisi kullanıcıya hiçbir şey anlatmaz. Ölçtük: bu mikrofonların en sık
    açılamama sebebi, aygıtın başka bir uygulama (örn. NVIDIA Broadcast, Zoom,
    Teams) tarafından tutuluyor olması — sebebi söylemek çözümü de söylemek
    demek.
    """
    joined = " ".join(errors).lower()

    if "unsupported_format" in joined or "device unavailable" in joined:
        reason = (
            f"“{device_name}” başka bir uygulama tarafından kullanılıyor olabilir "
            "(NVIDIA Broadcast, Zoom, Teams gibi). O uygulamayı kapatıp tekrar deneyin."
        )
    elif "invalid device" in joined:
        reason = f"“{device_name}” artık bağlı değil. Listeyi yenileyin."
    elif "invalid sample rate" in joined:
        reason = f"“{device_name}” desteklenen bir ses biçimi sunmuyor."
    else:
        reason = f"“{device_name}” açılamadı."

    # Teknik ayrıntı kayboluyor değil, günlüğe yazılıyor; arayüz sade kalıyor.
    log.warning("Aygıt açma hatası (%s): %s", device_name, " | ".join(errors))
    return reason


def _lowpass_kernel(cutoff_ratio: float, taps: int = 129) -> np.ndarray:
    """Pencerelenmiş sinc alçak geçiren süzgeç.

    Örnekleme hızını düşürmeden önce, hedef Nyquist frekansının üstündeki
    içeriği süzmek gerekir; yoksa o içerik katlanarak (aliasing) konuşmanın
    üstüne cızırtı olarak biner.
    """
    n = np.arange(taps) - (taps - 1) / 2
    # sinc zaten normalize (sin(pi x)/(pi x)) olduğu için oran doğrudan geçer.
    kernel = np.sinc(2 * cutoff_ratio * n) * np.hamming(taps)
    return (kernel / np.sum(kernel)).astype(np.float32)


def resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    """Sesi hedef örnekleme hızına indirir/çıkarır.

    Neden gerekli: WASAPI paylaşımlı kipte aygıt yalnız kendi doğal hızında
    açılır. Realtek mikrofonunu 16 kHz istemek `Invalid sample rate` hatası
    veriyordu; aygıtı 44.1 kHz'de açıp burada 16 kHz'e indiriyoruz.
    """
    if source_rate == target_rate or len(samples) == 0:
        return samples

    signal = samples.astype(np.float32)

    # Aşağı örnekleme: önce süz, sonra seyrelt.
    if target_rate < source_rate:
        kernel = _lowpass_kernel(0.5 * target_rate / source_rate)
        signal = np.convolve(signal, kernel, mode="same")

    duration = len(signal) / source_rate
    target_length = int(round(duration * target_rate))
    if target_length <= 0:
        return np.zeros(0, dtype=DTYPE)

    source_positions = np.arange(len(signal), dtype=np.float32)
    target_positions = np.linspace(0, len(signal) - 1, target_length, dtype=np.float32)
    resampled = np.interp(target_positions, source_positions, signal)

    return np.clip(resampled, -32768, 32767).astype(DTYPE)


@dataclass(frozen=True, slots=True)
class AudioClip:
    """Kaydedilmiş ses. Sağlayıcılara bu biçimde verilir."""

    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    @property
    def peak(self) -> float:
        """En yüksek genlik, 0.0–1.0."""
        if len(self.samples) == 0:
            return 0.0
        return float(np.max(np.abs(self.samples.astype(np.float32))) / 32768.0)

    @property
    def rms(self) -> float:
        """Ortalama enerji, 0.0–1.0."""
        if len(self.samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(self.samples.astype(np.float32) ** 2)) / 32768.0)

    def voiced_seconds(
        self, *, frame_ms: int = 20, frame_threshold: float = 0.012
    ) -> float:
        """Kayıtta ses barındıran toplam süre.

        Ses 20 ms'lik karelere bölünür ve eşiği aşan karelerin süresi
        toplanır. Ortalama enerjiye bakmak yerine bunu ölçmemizin sebebi:
        3 saniyelik sessizlik içindeki tek bir kapı çarpması ortalamayı
        konuşma düzeyine çıkarır, ama yalnız birkaç kareyi doldurur.
        """
        if len(self.samples) == 0:
            return 0.0

        frame_size = int(self.sample_rate * frame_ms / 1000)
        if frame_size <= 0:
            return 0.0

        usable = len(self.samples) - (len(self.samples) % frame_size)
        if usable == 0:
            return 0.0

        frames = self.samples[:usable].astype(np.float32).reshape(-1, frame_size)
        frame_rms = np.sqrt(np.mean(frames**2, axis=1)) / 32768.0
        voiced_frames = int(np.count_nonzero(frame_rms > frame_threshold))
        return voiced_frames * frame_ms / 1000.0

    def is_silent(self, *, min_voiced_seconds: float = 0.25) -> bool:
        """Kayıtta gerçekten konuşma var mı?

        Whisper sessizliğe metin **uydurur**: boş bir kayda "Thank you." veya
        "Altyazı M.K." gibi eğitim verisinden kalma cümleler döndürür. Ölçtük;
        kısayola basıp hiç konuşmadan bırakınca ekrana "Teşekkürler." yapışıyordu.

        Bu yüzden sessiz kayıtlar sağlayıcıya hiç gönderilmez — hem uydurma
        metin engellenir hem de boşuna istek atılmaz.

        Ölçüt süre tabanlı: en kısa anlamlı söz bile çeyrek saniye sürer.
        Bu eşik, tek tıkırtıyı eleyip kısa bir "tamam"ı geçirecek şekilde
        seçildi.
        """
        return self.voiced_seconds() < min_voiced_seconds

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
        #: Akışın gerçek hızı. Aygıt 16 kHz'i desteklemiyorsa doğal hızında
        #: açılır ve klip üretilirken 16 kHz'e indirilir.
        self._stream_rate = SAMPLE_RATE
        #: Akışın gerçek kanal sayısı; çok kanallıysa mono'ya indiriliyor.
        self._stream_channels = CHANNELS
        self._lock = threading.Lock()
        self._recording = False
        self._chunks: list[np.ndarray] = []
        #: Son bloğun RMS'i, 0.0–1.0. Arayüzdeki dalga formu bunu kullanır.
        self._level = 0.0

    # ── Akış yaşam döngüsü ────────────────────────────────────────────────

    def start_stream(self) -> None:
        """Mikrofon akışını açar. Zaten açıksa bir şey yapmaz.

        Aygıt açılamazsa `AudioDeviceError` yükseltir — çağıran taraf ya geri
        alır ya da kullanıcıya bildirir. Sessizce yutmak, kullanıcıyı mikrofonu
        çalışıyor sanarak konuşurken bırakırdı.
        """
        if self._stream is not None:
            return

        # Önce hedef hızı deneriz — yeniden örnekleme gerektirmediği için en
        # temizi. WASAPI paylaşımlı kipte aygıt yalnız kendi doğal hızında
        # açılabildiği için burada `Invalid sample rate` alınabilir; o durumda
        # aygıtın kendi hızına düşüp sesi biz indiriyoruz.
        errors: list[str] = []
        for rate, channels in self._candidate_configs():
            try:
                stream = sd.InputStream(
                    samplerate=rate,
                    channels=channels,
                    dtype="int16",
                    blocksize=int(BLOCK_SIZE * rate / SAMPLE_RATE),
                    device=self._device,
                    callback=self._on_block,
                )
                stream.start()
            except Exception as exc:  # noqa: BLE001 - PortAudio çeşitli hata üretir
                errors.append(f"{rate} Hz/{channels}ch: {exc}")
                continue

            self._stream = stream
            self._stream_rate = rate
            self._stream_channels = channels
            self._resize_ring(rate)
            log.info(
                "Mikrofon akışı açıldı: %s (%d Hz, %d kanal%s, pre-roll %.1f sn)",
                self._describe_device(),
                rate,
                channels,
                "" if rate == SAMPLE_RATE else f" → {SAMPLE_RATE} Hz'e indiriliyor",
                self.pre_roll_seconds,
            )
            return

        raise AudioDeviceError(_friendly_open_error(self._describe_device(), errors))

    def _candidate_configs(self) -> list[tuple[int, int]]:
        """Denenecek (hız, kanal) birleşimleri.

        WASAPI paylaşımlı kipte aygıt yalnız kendi **karışım biçiminde**
        açılabilir: hem örnekleme hızı hem kanal sayısı birebir uymalı.
        Ölçtük — Realtek mikrofonu 16 kHz mono isteğine `Invalid sample rate`,
        44.1 kHz mono isteğine `AUDCLNT_E_UNSUPPORTED_FORMAT` veriyor; doğru
        birleşim kendi doğal hızı ve kanal sayısı.

        Sıra: önce hiç dönüşüm gerektirmeyen hedef biçim, sonra aygıtın kendi
        biçimi, sonra yaygın yedekler.
        """
        configs: list[tuple[int, int]] = [(SAMPLE_RATE, CHANNELS)]

        native_rate: int | None = None
        native_channels = CHANNELS
        try:
            info = sd.query_devices(self._device if self._device is not None else None, "input")
            native_rate = int(info["default_samplerate"])
            native_channels = max(1, int(info["max_input_channels"]))
        except Exception:  # noqa: BLE001
            pass

        if native_rate:
            configs.append((native_rate, native_channels))
            if native_channels != CHANNELS:
                configs.append((native_rate, CHANNELS))

        for rate in (48_000, 44_100):
            for channels in (CHANNELS, 2):
                if (rate, channels) not in configs:
                    configs.append((rate, channels))

        return configs

    def _resize_ring(self, rate: int) -> None:
        """Ön belleği akışın hızına göre yeniden boyutlandırır."""
        capacity = max(int(rate * (self.pre_roll_seconds + 0.5)), int(BLOCK_SIZE * rate / SAMPLE_RATE))
        with self._lock:
            self._ring = _RingBuffer(capacity)

    def _describe_device(self) -> str:
        if self._device is None:
            return "sistem varsayılanı"
        try:
            return str(sd.query_devices(self._device)["name"])
        except Exception:  # noqa: BLE001
            return f"aygıt {self._device}"

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

        Yeni aygıt açılamazsa **eskisine geri dönülür** ve hata yükseltilir.
        Ölçtük: geçersiz bir indeks vermek PortAudio'da `Error querying device`
        üretiyor; bu yakalanmazsa motor süreci komple düşüyordu ve kullanıcı
        mikrofonsuz kalıyordu.
        """
        if device == self._device:
            return
        if self._recording:
            raise AudioDeviceError("Kayıt sürerken mikrofon değiştirilemez")

        previous = self._device
        was_streaming = self.is_streaming

        if was_streaming:
            self.stop_stream()

        self._device = device
        try:
            if was_streaming:
                self.start_stream()
        except AudioDeviceError:
            # Geri al: kullanıcı yanlış aygıtı seçtiği için mikrofonsuz
            # kalmamalı.
            self._device = previous
            if was_streaming:
                try:
                    self.start_stream()
                except AudioDeviceError:
                    log.error("Önceki mikrofon da açılamadı", exc_info=True)
            raise

        log.info("Mikrofon değiştirildi: %s", self._describe_device())

    def resolve_device_by_name(self, name: str) -> int | None:
        """Aygıt adından güncel indeksi bulur.

        PortAudio indeksleri **kararlı değildir**: aynı mikrofon bir oturumda
        20, diğerinde 15 olabilir. Bu yüzden seçim adla saklanır ve her
        açılışta yeniden çözümlenir.
        """
        for device in list_input_devices():
            if device["name"] == name:
                return int(device["index"])  # type: ignore[arg-type]
        return None

    # ── Ses geri çağrımı ──────────────────────────────────────────────────

    def _on_block(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        """PortAudio iş parçacığında çalışır — burada ağır iş yapılmaz."""
        if status:
            log.debug("Ses akışı durumu: %s", status)

        # Aygıt çok kanallı açılmış olabilir (WASAPI karışım biçimi stereo
        # isteyebiliyor). Kanalların ortalamasını alarak mono'ya indiriyoruz;
        # tek kanal seçmek, konuşmanın diğer kanalda olduğu aygıtlarda sesi
        # kaybettirirdi.
        block = (
            indata[:, 0].copy()
            if indata.shape[1] == 1
            else indata.mean(axis=1).astype(DTYPE)
        )

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
            rate = self._stream_rate
            pre_roll = self._ring.read_last(int(rate * self.pre_roll_seconds))
            self._chunks = [pre_roll] if len(pre_roll) else []
            self._recording = True
            return len(pre_roll) / rate

    def stop_recording(self) -> AudioClip:
        """Kaydı durdurur ve biriken sesi 16 kHz olarak döndürür."""
        with self._lock:
            self._recording = False
            chunks = self._chunks
            self._chunks = []
            rate = self._stream_rate

        samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=DTYPE)
        # Yeniden örnekleme kayıt bitince bir kez yapılır: ses geri çağrımında
        # yapmak gerçek zamanlı iş parçacığını gereksiz yere yorardı.
        if rate != SAMPLE_RATE:
            samples = resample(samples, rate, SAMPLE_RATE)
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
            return sum(len(c) for c in self._chunks) / self._stream_rate

    @property
    def stream_rate(self) -> int:
        """Akışın gerçek örnekleme hızı. 16 kHz değilse çıktı indiriliyor."""
        return self._stream_rate


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
