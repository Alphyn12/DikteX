"""LLM sağlayıcı arayüzü."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from omnivoice_engine.providers import Completion, ProviderInfo


@dataclass(frozen=True, slots=True)
class Prompt:
    """LLM'e gönderilen istem."""

    system: str
    user: str
    #: Yaratıcılık burada istenmez; metni temizlemek deterministik bir iştir.
    temperature: float = 0.2
    max_tokens: int = 2000
    #: İsteme eklenecek görseller (`data:image/png;base64,...`).
    #:
    #: Varsayılan modelimiz zaten görsel kabul ediyor, bu yüzden ekran
    #: sorularında ayrı bir sağlayıcıya geçmek gerekmiyor.
    images: tuple[str, ...] = ()


@runtime_checkable
class LlmProvider(Protocol):
    """Metin üreten sağlayıcı."""

    @property
    def info(self) -> ProviderInfo: ...

    def is_available(self) -> bool: ...

    async def complete(self, prompt: Prompt, *, model: str | None = None) -> Completion: ...
