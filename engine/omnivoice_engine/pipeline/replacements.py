"""Otomatik değiştirme sözlüğü (Faz 7.8).

Sözlük (`storage/vocabulary.py`) konuşma tanımaya **ipucu** veriyor: "bu
terimler geçebilir, yazımlarını koru". İpucu her zaman tutmuyor — Whisper bazı
özel adları ısrarla aynı biçimde yanlış yazıyor ("omni voice", "es kü el").

Bu modül o kalan kısmı kapatıyor: kesin bul-değiştir. Bir kez tanımlanır, her
diktede uygulanır.

## Neden LLM'e bırakılmıyor

Bırakılabilirdi ama üç sebeple bırakılmadı: (1) yerel ve anlık, (2) bedava,
(3) **belirlenimci** — model bazen düzeltir bazen düzeltmez, kural her zaman
düzeltir. Kullanıcının kendi adının bazen doğru yazılması, hiç yazılmamasından
daha can sıkıcı.

## Sınırlar

Kural yazan kullanıcı metnini bozabilir. Bu yüzden:

* Varsayılan **kelime sınırı** aranıyor — "kod" kuralı "kodlama"yı bozmasın.
* Ama Türkçe eklemeli olduğu için kelime sınırı ekleri de kesiyor: "OmniVoice"
  kuralı "OmniVoice'u" içinde çalışsın diye **son ek serbest** bırakılıyor.
* Arayüzde deneme alanı var; kullanıcı kuralı canlı diktede sınamak zorunda
  değil.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)


def fold(text: str) -> str:
    """Türkçe duyarlı küçük harfe indirme.

    `snippets.fold` ile aynı iş — Python'da `"İ".lower()` `"i"` değil,
    `"i" + birleşen nokta` üretiyor.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    for source, target in (("ı", "i"), ("ğ", "g"), ("ş", "s")):
        stripped = stripped.replace(source, target)
    return stripped


@dataclass(frozen=True, slots=True)
class Replacement:
    """Tek bir değiştirme kuralı."""

    #: Aranan metin. Büyük/küçük harf duyarsız eşleşir.
    find: str
    #: Yerine yazılacak metin. **Olduğu gibi** yazılır — özel adların doğru
    #: yazımı bu özelliğin ana kullanımı.
    replace: str
    #: Kelime sınırı aransın mı. Kapatmak "es kü el" gibi çok kelimeli
    #: kalıplarda ya da kelime içi düzeltmelerde gerekiyor.
    whole_word: bool = True
    used: int = 0

    def to_payload(self) -> dict[str, object]:
        return {
            "find": self.find,
            "replace": self.replace,
            "wholeWord": self.whole_word,
            "used": self.used,
        }


#: Türkçe ekler kelimenin sonuna geliyor, bu yüzden **sol** sınır katı, sağ
#: sınır serbest. "OmniVoice" kuralı "OmniVoice'u" içinde çalışmalı ama
#: "MyOmniVoice" içinde çalışmamalı.
_LEFT_BOUNDARY = r"(?<![\w])"
_RIGHT_BOUNDARY = r"(?![\w])"
#: Ek ayırıcıları: kesme işareti ve doğrudan bitişik ek.
_SUFFIX = r"(?:['’]?\w*)?"


def _compile(rule: Replacement) -> re.Pattern[str]:
    escaped = re.escape(rule.find)
    if not rule.whole_word:
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(_LEFT_BOUNDARY + escaped + _SUFFIX + _RIGHT_BOUNDARY, re.IGNORECASE)


@dataclass
class ReplacementResult:
    """Uygulama sonucu."""

    text: str
    #: Uygulanan kuralların `find` alanları — arayüzde gösteriliyor.
    applied: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.applied)


def apply_replacements(text: str, rules: list[Replacement]) -> ReplacementResult:
    """Kuralları uygular.

    Kurallar **uzundan kısaya** sıralanıyor. Sıralamasak kısa bir kural uzun
    bir kuralın parçasını yiyebilirdi: "kod" ve "kod inceleme" birlikte
    tanımlıysa, önce "kod" uygulanırsa ikincisi bir daha eşleşmez.
    """
    if not text or not rules:
        return ReplacementResult(text=text)

    applied: list[str] = []
    result = text

    for rule in sorted(rules, key=lambda r: len(r.find), reverse=True):
        if not rule.find:
            continue
        pattern = _compile(rule)

        def substitute(match: re.Match[str]) -> str:
            # Eşleşen metnin kural uzunluğundan fazlası **ek** demektir ve
            # korunmalı: "OmniVoice'u" → "OmniVoice'u", "OmniVoice" değil.
            suffix = match.group(0)[len(rule.find) :]
            return rule.replace + suffix

        new_result, count = pattern.subn(substitute, result)
        if count:
            applied.append(rule.find)
            result = new_result

    return ReplacementResult(text=result, applied=tuple(applied))


@dataclass
class ReplacementLibrary:
    """Kuralların diskteki hâli."""

    path: Path
    rules: list[Replacement] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> ReplacementLibrary:
        resolved = path or default_replacements_path()
        library = cls(path=resolved)

        if not resolved.exists():
            return library

        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("Değiştirme kuralları okunamadı: %s", resolved)
            return library

        entries = raw.get("rules", []) if isinstance(raw, dict) else raw
        for entry in entries:
            if not isinstance(entry, dict) or not str(entry.get("find", "")).strip():
                continue
            library.rules.append(
                Replacement(
                    find=str(entry["find"]),
                    replace=str(entry.get("replace", "")),
                    whole_word=bool(entry.get("wholeWord", True)),
                    used=int(entry.get("used", 0)),
                )
            )
        return library

    def save(self) -> bool:
        payload = {"version": 1, "rules": [r.to_payload() for r in self.rules]}
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix(".json.tmp")
                temp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                temp.replace(self.path)
            return True
        except OSError:
            log.warning("Değiştirme kuralları kaydedilemedi", exc_info=True)
            return False

    def add(self, find: str, replace: str, *, whole_word: bool = True) -> bool:
        cleaned = find.strip()
        if not cleaned:
            return False
        # Kendini değiştiren kural gürültü: her diktede "uygulandı" der ama
        # hiçbir şey değiştirmez. Karşılaştırma **birebir** — harf katlamasıyla
        # bakmak `sql → SQL` gibi büyük harf düzeltmelerini reddederdi ve o,
        # bu özelliğin en yaygın kullanımı.
        if cleaned == replace.strip():
            return False
        if any(fold(r.find) == fold(cleaned) for r in self.rules):
            return False
        self.rules.append(
            Replacement(find=cleaned, replace=replace.strip(), whole_word=whole_word)
        )
        self.save()
        return True

    def remove(self, find: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if fold(r.find) != fold(find.strip())]
        if len(self.rules) == before:
            return False
        self.save()
        return True

    def mark_used(self, names: tuple[str, ...]) -> None:
        if not names:
            return
        wanted = {fold(name) for name in names}
        for index, rule in enumerate(self.rules):
            if fold(rule.find) in wanted:
                self.rules[index] = Replacement(
                    find=rule.find,
                    replace=rule.replace,
                    whole_word=rule.whole_word,
                    used=rule.used + 1,
                )
        self.save()

    def apply(self, text: str) -> ReplacementResult:
        return apply_replacements(text, self.rules)

    def to_payload(self) -> dict[str, object]:
        return {"path": str(self.path), "rules": [r.to_payload() for r in self.rules]}


def default_replacements_path() -> Path:
    return default_db_path().parent / "replacements.json"
