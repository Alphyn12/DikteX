"""API Kasası — anahtarların şifreli saklanması (Properties VI.1).

Anahtarlar Windows Credential Manager'da tutulur; diskte düz metin dosyada
durmazlar. Geliştirme kolaylığı için `.env.local` hâlâ okunur, ama oradaki bir
anahtar ilk görüldüğünde kasaya taşınır.

Anahtar değerleri bu modülün dışına **yalnız** sağlayıcı istemcilerine çıkar.
Arayüze giden her şey maskelenmiş biçimdedir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError

from omnivoice_engine.config import get_settings

log = logging.getLogger(__name__)

SERVICE_NAME = "DikteX"

#: Uygulamanın eski adı. Anahtarlar bu adla kaydedilmişti ve Credential
#: Manager'da kullanıcıya görünüyor.
_LEGACY_SERVICE_NAME = "OmniVoice"

#: Kasada tutulan sağlayıcılar ve `.env.local` karşılıkları.
PROVIDERS: dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

#: Kullanıcı `.env.local` şablonundaki yer tutucuyu silmemiş olabilir.
PLACEHOLDER = "BURAYA_YAPISTIR"


@dataclass(frozen=True, slots=True)
class VaultEntry:
    """Arayüze gönderilebilir anahtar özeti. Gerçek değeri **taşımaz**."""

    provider: str
    configured: bool
    masked: str | None


def _mask(key: str) -> str:
    """Anahtarı tanınabilir ama kullanılamaz hâle getirir: `sk-or-•••• 0906`."""
    key = key.strip()
    if len(key) <= 8:
        return "••••"
    # Önek sağlayıcıyı tanıtır, son dört karakter hangi anahtar olduğunu ayırt eder.
    prefix_len = 6 if key.startswith(("sk-or-", "gsk_", "AQ.")) else 4
    return f"{key[:prefix_len]}•••• {key[-4:]}"


def _is_real(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip() != PLACEHOLDER)


def get_key(provider: str) -> str | None:
    """Sağlayıcının anahtarını döndürür.

    Önce kasaya, sonra `.env.local`'a bakar. `.env.local`'da bulunup kasada
    olmayan bir anahtar sessizce kasaya taşınır — kullanıcı bir kez yapıştırır,
    bir daha düz metinde tutmak zorunda kalmaz.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider}")

    try:
        stored = keyring.get_password(SERVICE_NAME, provider)
    except KeyringError:
        # Kasa erişilemezse çalışmayı durdurmuyoruz; ortam değişkenine düşülür.
        log.warning("Credential Manager okunamadı, .env.local'a düşülüyor", exc_info=True)
        stored = None

    if _is_real(stored):
        return stored

    taşınan = _migrate_legacy(provider)
    if taşınan is not None:
        return taşınan

    env_value = getattr(get_settings(), f"{provider}_api_key", None)
    if not _is_real(env_value):
        return None

    assert env_value is not None
    if set_key(provider, env_value):
        log.info("%s anahtarı .env.local'dan kasaya taşındı", provider)
    return env_value


def _migrate_legacy(provider: str) -> str | None:
    """Eski servis adıyla kaydedilmiş anahtarı yeni ada taşır.

    Uygulama OmniVoice adıyla kullanıldı ve anahtarlar Credential
    Manager'a o adla yazıldı. Ad değiştiği için yeni sürüm onları
    bulamıyordu — kullanıcı üç anahtarı da yeniden yapıştırmak zorunda
    kalırdı.

    Sıra önemli: önce yeni ada YAZILIYOR, yazdığımız geri okunarak
    doğrulanıyor, ancak ondan sonra eskisi siliniyor. Ters sırada bir hata
    anahtarı tamamen kaybettirirdi.
    """
    try:
        eski = keyring.get_password(_LEGACY_SERVICE_NAME, provider)
    except KeyringError:
        return None
    if not _is_real(eski):
        return None

    assert eski is not None
    try:
        keyring.set_password(SERVICE_NAME, provider, eski)
        if keyring.get_password(SERVICE_NAME, provider) != eski:
            log.warning("%s anahtarı taşındı ama doğrulanamadı; eskisi duruyor", provider)
            return eski
        keyring.delete_password(_LEGACY_SERVICE_NAME, provider)
    except KeyringError:
        # Taşıyamadıysak anahtarı yine de döndürüyoruz: kullanıcının
        # dikte edebilmesi, kasanın düzenli olmasından önemli.
        log.warning("%s anahtarı yeni ada taşınamadı", provider, exc_info=True)
        return eski

    log.info("%s anahtarı kasada DikteX adına taşındı", provider)
    return eski


def set_key(provider: str, key: str) -> bool:
    """Anahtarı kasaya yazar. Başarılıysa `True` döner."""
    if provider not in PROVIDERS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider}")
    try:
        keyring.set_password(SERVICE_NAME, provider, key.strip())
        return True
    except KeyringError:
        log.error("Anahtar kasaya yazılamadı: %s", provider, exc_info=True)
        return False


def delete_key(provider: str) -> bool:
    """Anahtarı kasadan siler."""
    if provider not in PROVIDERS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider}")
    try:
        keyring.delete_password(SERVICE_NAME, provider)
        return True
    except KeyringError:
        return False


def list_entries() -> list[VaultEntry]:
    """Kasanın arayüze gönderilebilir özeti. Anahtar değeri içermez."""
    entries: list[VaultEntry] = []
    for provider in PROVIDERS:
        key = get_key(provider)
        entries.append(
            VaultEntry(
                provider=provider,
                configured=key is not None,
                masked=_mask(key) if key else None,
            )
        )
    return entries
