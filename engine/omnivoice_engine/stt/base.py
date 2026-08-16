"""STT sağlayıcı arayüzü."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from omnivoice_engine.audio.capture import AudioClip
from omnivoice_engine.providers import ProviderInfo, Transcript


@runtime_checkable
class SttProvider(Protocol):
    """Konuşmayı metne çeviren sağlayıcı.

    Uygulamalar yalnız bu arayüzü karşılamak zorundadır; yarın yerel bir motor
    eklenirse (`LocalWhisperStt`) çağıran taraf değişmez.
    """

    @property
    def info(self) -> ProviderInfo: ...

    def is_available(self) -> bool:
        """Anahtarı girilmiş ve kullanılabilir durumda mı?"""
        ...

    async def transcribe(
        self,
        clip: AudioClip,
        *,
        language: str | None = None,
        vocabulary: list[str] | None = None,
    ) -> Transcript:
        """Sesi metne çevirir.

        `vocabulary` özel terim listesidir (Properties I.4); sağlayıcı
        destekliyorsa istem olarak iletilir, desteklemiyorsa yok sayılır.
        """
        ...
