"""Kalıcı kullanıcı ayarları (Faz 3.15 / 7.B).

Bugüne kadar ayarların hepsi bellekteydi: motor yeniden başladığında mikrofon
seçimi sistem varsayılanına dönüyordu, model değiştirmek için `config.py`
elle düzenleniyordu. Bu modül ikisini de kapatıyor.

## `config.py` ile farkı

`Settings` (pydantic) **ortam değişkenlerinden** okunan, dağıtımın belirlediği
varsayılanlar. Buradaki ise **kullanıcının seçtikleri** ve onun profilinde
duruyor. Öncelik sırası:

    kullanıcı ayarı  >  ortam değişkeni  >  koddaki varsayılan

Bu sıralama bilinçli: kullanıcı arayüzden bir model seçtiyse, `.env` dosyasında
kalmış eski bir değer onu ezmemeli — ezerse kullanıcı ayarın çalışmadığını
düşünür ve sebebini bulamaz.

## Neden JSON

Sözlük ve snippet kütüphanesiyle aynı desen: kullanıcı dosyayı açıp
okuyabiliyor, sürüm kontrolüne koyabiliyor, bozulursa silip baştan
başlayabiliyor. Bozuk dosya uygulamayı açılmaz hâle getirmiyor —
varsayılanlara dönülüyor.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omnivoice_engine.storage.db import default_db_path

log = logging.getLogger(__name__)

#: Dosya biçimi sürümü. Alan eklemek sürümü artırmayı gerektirmiyor;
#: bilinmeyen alanlar yok sayılıyor, eksik alanlar varsayılana düşüyor.
SCHEMA_VERSION = 1


@dataclass
class UserSettings:
    """Kullanıcının kaydettiği tercihler.

    Hepsi `None` olabilir ve `None` "seçim yapılmadı, varsayılanı kullan"
    demek. Boş dizeyle karıştırmamak önemli: boş dize "bilerek hiçbiri"
    anlamına gelebilirdi ve model alanında bu geçersiz bir durum.
    """

    #: Seçili mikrofonun **adı**, indeksi değil.
    #:
    #: İndeks kaydetmek işe yaramıyor: PortAudio indeksleri aygıt takılıp
    #: çıkarıldıkça kayıyor. Kaydedilen 3 numaralı aygıt bir sonraki açılışta
    #: bambaşka bir mikrofon olabilir — ve kullanıcı bunu ancak kaydın boş
    #: çıkmasıyla anlar.
    microphone_name: str | None = None

    #: Metin işleme sağlayıcısı: `openrouter` ya da `gemini`.
    #:
    #: İkisi de aynı modeli sunabiliyor ama **gizlilik sınıfları farklı**:
    #: OpenRouter ücretli uç nokta (eğitime kapalı), Gemini'nin AI Studio
    #: ücretsiz katmanı gönderilen veriyi eğitimde kullanıyor. Seçim
    #: kullanıcının, ama bilerek yapması gerekiyor.
    llm_provider: str | None = None

    #: Rol başına model seçimi. `None` ise dağıtımın varsayılanı kullanılır.
    stt_model: str | None = None
    llm_model: str | None = None
    #: Görsel işler (ekran gözü) için model; `None` ise LLM modeli kullanılır.
    vision_model: str | None = None

    #: Sessizlikte otomatik durdurma eşiği, saniye. 0 = kapalı.
    auto_stop_seconds: float | None = None

    #: Hassas veri maskeleme açık mı.
    mask_pii: bool | None = None

    #: Arayüz dili.
    locale: str | None = None

    #: Öğrenen kişisel stil açık mı (Faz 3.13).
    #:
    #: Varsayılan KAPALI: özellik geçmiş dikte içeriğini yeni isteklere
    #: taşıyor ve bu, kullanıcının beklemediği bir veri akışı.
    style_learning: bool | None = None

    #: Pre-flight önizlemesi açık mı. Kapalıyken çıktı doğrudan yapıştırılır
    #: (modun `require_preflight` bayrağı bunu ezer).
    preflight: bool | None = None

    #: Türkçe sayıları rakama çevirme (Faz 7.9).
    normalize_numbers: bool | None = None

    #: Basılı tut (push-to-talk) kipi açık mı (Faz 7.7).
    #:
    #: Varsayılan KAPALI ve bu bilinçli: kip düşük seviyeli bir klavye kancası
    #: kuruyor ve o kanca sistemdeki her tuşu görüyor. Böyle bir şeyin
    #: varsayılan olarak açık gelmesi savunulamaz — kullanıcı bilerek
    #: açmalı.
    push_to_talk: bool | None = None

    #: Uygulama başına varsayılan mod (Faz 7.5): süreç adı → mod kimliği.
    #:
    #: Anahtar küçük harfe indirilmiş, `.exe` eki atılmış süreç adı —
    #: `context.apps.profile_for` ile aynı biçim. Aynı normalleştirmeyi
    #: kullanmak şart: iki yer ayrışırsa eşleşme sessizce çalışmaz.
    app_modes: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "microphoneName": self.microphone_name,
            "llmProvider": self.llm_provider,
            "sttModel": self.stt_model,
            "llmModel": self.llm_model,
            "visionModel": self.vision_model,
            "autoStopSeconds": self.auto_stop_seconds,
            "maskPii": self.mask_pii,
            "locale": self.locale,
            "styleLearning": self.style_learning,
            "preflight": self.preflight,
            "normalizeNumbers": self.normalize_numbers,
            "pushToTalk": self.push_to_talk,
            "appModes": dict(self.app_modes),
        }


#: JSON anahtarı → alan adı. Açıkça yazılıyor ki dosya biçimi, iç alan
#: adlarını yeniden adlandırdığımızda sessizce bozulmasın.
_FIELD_MAP = {
    "microphoneName": "microphone_name",
    "llmProvider": "llm_provider",
    "sttModel": "stt_model",
    "llmModel": "llm_model",
    "visionModel": "vision_model",
    "autoStopSeconds": "auto_stop_seconds",
    "maskPii": "mask_pii",
    "locale": "locale",
    "styleLearning": "style_learning",
    "preflight": "preflight",
    "normalizeNumbers": "normalize_numbers",
    "pushToTalk": "push_to_talk",
    "appModes": "app_modes",
}


@dataclass
class SettingsStore:
    """Ayarların diskteki hâli."""

    path: Path
    settings: UserSettings = field(default_factory=UserSettings)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> SettingsStore:
        resolved = path or default_settings_path()
        store = cls(path=resolved)

        if not resolved.exists():
            return store

        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Bozuk ayar dosyası uygulamayı açılmaz hâle getirmemeli.
            log.warning("Ayar dosyası okunamadı, varsayılanlara dönülüyor: %s", resolved)
            return store

        if not isinstance(raw, dict):
            return store

        for json_key, field_name in _FIELD_MAP.items():
            if json_key not in raw:
                continue
            value = raw[json_key]
            if value is None:
                continue
            try:
                setattr(store.settings, field_name, _coerce(field_name, value))
            except (TypeError, ValueError):
                # Tek bir bozuk alan diğerlerini götürmesin.
                log.warning("Ayar alanı yok sayıldı: %s = %r", json_key, value)

        return store

    def save(self) -> bool:
        """Ayarları diske yazar. Başarısızlık uygulamayı durdurmuyor."""
        payload = {"version": SCHEMA_VERSION, **self.settings.to_payload()}
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix(".json.tmp")
                temp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                # Atomik değiştirme: yazma yarıda kesilirse eski dosya sağlam kalır.
                temp.replace(self.path)
            return True
        except OSError:
            log.warning("Ayarlar kaydedilemedi: %s", self.path, exc_info=True)
            return False

    def update(self, **changes: Any) -> UserSettings:
        """Verilen alanları değiştirir ve kaydeder.

        Bilinmeyen alan **sessizce yok sayılmıyor**, hata veriyor: yanlış
        yazılmış bir alan adı, çalışmayan bir ayar olarak ortaya çıkardı ve
        sebebi görünmezdi.
        """
        for name, value in changes.items():
            if not hasattr(self.settings, name):
                raise KeyError(f"bilinmeyen ayar: {name}")
            setattr(self.settings, name, _coerce(name, value) if value is not None else None)
        self.save()
        return self.settings

    def to_payload(self) -> dict[str, Any]:
        return {"path": str(self.path), **self.settings.to_payload()}


def _coerce(field_name: str, value: Any) -> Any:
    """Dosyadan gelen değeri beklenen tipe çevirir."""
    if field_name == "app_modes":
        if not isinstance(value, dict):
            raise TypeError("app_modes bir eşleme olmalı")
        # Anahtarlar `profile_for` ile aynı biçime indiriliyor; aksi hâlde
        # "Code.exe" yazan bir kayıt hiç eşleşmez ve kullanıcı sebebini
        # bulamaz.
        return {
            str(k).lower().removesuffix(".exe").strip(): str(v)
            for k, v in value.items()
            if str(k).strip() and str(v).strip()
        }
    if field_name == "auto_stop_seconds":
        return max(0.0, min(float(value), 10.0))
    if field_name in {
        "mask_pii",
        "push_to_talk",
        "normalize_numbers",
        "style_learning",
        "preflight",
    }:
        return bool(value)
    if field_name == "llm_provider":
        text = str(value).strip().lower()
        return text if text in {"openrouter", "gemini"} else None
    if field_name == "locale":
        text = str(value)
        return text if text in {"tr", "en"} else None
    text = str(value).strip()
    return text or None


def default_settings_path() -> Path:
    return default_db_path().parent / "settings.json"
