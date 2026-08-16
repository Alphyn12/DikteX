"""Sağlayıcı ortak tipleri.

STT ve LLM katmanları bu tipler üzerinden konuşur; hiçbir çağıran taraf
sağlayıcı adını sabit yazmaz (bkz. docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PrivacyClass(Enum):
    """Sağlayıcının gönderilen veriye ne yaptığı.

    Yönlendirici bu sınıfı işin hassasiyetiyle eşleştirir: kullanıcı içeriği
    `TRAINS_ON_DATA` bir sağlayıcıya varsayılan olarak gönderilmez.
    """

    PRIVATE = "private"
    """Veri model eğitiminde kullanılmaz."""

    TRAINS_ON_DATA = "trains_on_data"
    """Sağlayıcı gönderilen veriyi model eğitiminde kullanır."""


@dataclass(frozen=True, slots=True)
class Usage:
    """Bir isteğin gerçek bedeli.

    Arayüzde sahte performans sayısı göstermemek için gecikme **ölçülür**,
    maliyet ise sağlayıcının bildirdiği değerden alınır; bilinmiyorsa `None`
    kalır ve arayüzde tahmin uydurulmaz.
    """

    latency_ms: int
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    audio_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    """Konuşmadan çıkarılan ham metin."""

    text: str
    language: str | None
    model: str
    provider: str
    usage: Usage


@dataclass(frozen=True, slots=True)
class Completion:
    """LLM'in ürettiği metin."""

    text: str
    model: str
    provider: str
    usage: Usage


class ProviderError(RuntimeError):
    """Sağlayıcı isteği başarısız oldu."""

    def __init__(self, provider: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    """Sağlayıcının arayüzde gösterilen kimliği."""

    name: str
    privacy: PrivacyClass
    models: list[str] = field(default_factory=list)

    @property
    def trains_on_data(self) -> bool:
        return self.privacy is PrivacyClass.TRAINS_ON_DATA
