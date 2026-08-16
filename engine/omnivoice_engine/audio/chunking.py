"""Uzun kayıtları sağlayıcı sınırlarına sığacak parçalara böler (Faz 4.2).

Sağlayıcıların iki sınırı var: dosya boyutu (25 MB) ve istek süresi (60 sn).
16 kHz mono FLAC dakikada ~0,94 MB; yani 25 MB sınırı ~27 dakikaya denk
geliyor. Bir saatlik toplantı bunu aşar.

**Nerede bölüneceği önemlidir.** Sabit aralıklarla kesmek kelimeyi ortadan
böler ve iki parçada da bozuk kelime üretir. Bunun yerine hedef sürenin
çevresinde en sessiz nokta aranır — konuşmacının nefes aldığı yer.

Parçalar arasında küçük bir **bindirme** bırakılır: sınırdaki bir hece iki
parçaya da girsin, hiçbirinde kaybolmasın.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from omnivoice_engine.audio.capture import AudioClip

log = logging.getLogger(__name__)

#: Hedef parça süresi. Sağlayıcı sınırının altında güvenli bir pay bırakır.
DEFAULT_CHUNK_SECONDS = 600.0  # 10 dakika

#: Bölme noktası bu pencere içinde aranır (hedefin öncesi ve sonrası).
_SEARCH_WINDOW_SECONDS = 20.0

#: Parçalar arasındaki bindirme. Sınırdaki hece kaybolmasın diye.
_OVERLAP_SECONDS = 0.4

#: Sessizlik araması bu çözünürlükte yapılır.
_FRAME_MS = 20


@dataclass(frozen=True, slots=True)
class Chunk:
    """Bir ses parçası ve kaynaktaki yeri."""

    clip: AudioClip
    index: int
    total: int
    #: Parçanın orijinal kayıttaki başlangıç saniyesi.
    start_seconds: float

    @property
    def is_only(self) -> bool:
        return self.total == 1


def _frame_energies(samples: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
    """Kare başına RMS ve kare boyutu."""
    frame_size = max(1, int(sample_rate * _FRAME_MS / 1000))
    usable = len(samples) - (len(samples) % frame_size)
    if usable <= 0:
        return np.zeros(0, dtype=np.float32), frame_size
    frames = samples[:usable].astype(np.float32).reshape(-1, frame_size)
    return np.sqrt(np.mean(frames**2, axis=1)), frame_size


def _quietest_point(
    samples: np.ndarray, sample_rate: int, target: int, window: int
) -> int:
    """`target` örneğinin çevresindeki en sessiz noktayı bulur.

    Konuşmada doğal duraklamalar vardır; kesmek için en az zarar veren yer
    orasıdır. Pencere içinde hiç sessizlik yoksa hedef noktanın kendisi
    kullanılır — kesmek zorundayız, hiç kesmemek seçenek değil.
    """
    # Aranacak aralık, dizinin dışına taşmasın.
    low = max(0, target - window)
    high = min(len(samples), target + window)
    if high - low < sample_rate:  # 1 saniyeden dar pencere anlamsız
        return target

    segment = samples[low:high]
    energies, frame_size = _frame_energies(segment, sample_rate)
    if len(energies) == 0:
        return target

    return low + int(np.argmin(energies)) * frame_size


def split_for_upload(
    clip: AudioClip, *, chunk_seconds: float = DEFAULT_CHUNK_SECONDS
) -> list[Chunk]:
    """Klibi yüklenebilir parçalara böler.

    Kayıt zaten kısaysa tek parça döner ve hiçbir maliyet eklenmez.
    """
    if clip.duration_seconds <= chunk_seconds:
        return [Chunk(clip=clip, index=0, total=1, start_seconds=0.0)]

    rate = clip.sample_rate
    samples = clip.samples
    chunk_samples = int(chunk_seconds * rate)
    window = int(_SEARCH_WINDOW_SECONDS * rate)
    overlap = int(_OVERLAP_SECONDS * rate)

    boundaries: list[int] = [0]
    cursor = chunk_samples
    while cursor < len(samples):
        cut = _quietest_point(samples, rate, cursor, window)
        # Kesim noktası geriye kaçmamalı; sonsuz döngü olur.
        cut = max(cut, boundaries[-1] + rate)
        if cut >= len(samples):
            break
        boundaries.append(cut)
        cursor = cut + chunk_samples

    boundaries.append(len(samples))

    chunks: list[Chunk] = []
    total = len(boundaries) - 1
    for index in range(total):
        start = boundaries[index]
        end = boundaries[index + 1]
        # Bindirme yalnız başa eklenir; sonraki parça önceki parçanın son
        # anlarını da içerir.
        padded_start = max(0, start - overlap) if index > 0 else start
        chunks.append(
            Chunk(
                clip=AudioClip(samples=samples[padded_start:end], sample_rate=rate),
                index=index,
                total=total,
                start_seconds=padded_start / rate,
            )
        )

    log.info(
        "Kayıt %d parçaya bölündü (%.1f dk toplam)",
        total,
        clip.duration_seconds / 60,
    )
    return chunks


def join_transcripts(texts: list[str]) -> str:
    """Parça metinlerini birleştirir.

    Bindirme yüzünden sınırdaki birkaç kelime iki parçada da geçebilir.
    Bitiş ve başlangıçtaki ortak kelime dizisini bulup tekrarı ayıklıyoruz —
    aksi halde özetleyen model tekrarı gerçek bir vurgu sanır.
    """
    parts = [text.strip() for text in texts if text.strip()]
    if not parts:
        return ""

    joined = parts[0]
    for part in parts[1:]:
        joined = f"{joined} {_strip_overlap(joined, part)}".strip()
    return joined


def _strip_overlap(previous: str, current: str, max_words: int = 12) -> str:
    """`current`'ın başındaki, `previous`'ın sonuyla çakışan kelimeleri atar."""
    previous_words = previous.split()
    current_words = current.split()
    if not previous_words or not current_words:
        return current

    limit = min(max_words, len(previous_words), len(current_words))
    for size in range(limit, 1, -1):
        tail = [w.lower().strip(".,!?;:") for w in previous_words[-size:]]
        head = [w.lower().strip(".,!?;:") for w in current_words[:size]]
        if tail == head:
            return " ".join(current_words[size:])
    return current
