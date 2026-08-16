"""Aktif uygulama farkındalığı (Properties II.1).

Kullanıcı hangi uygulamada konuşuyorsa çıktı o ortama uygun olmalı: VS Code'da
kod, Slack'te mesaj, terminalde komut. Bunu yapmanın yolu uygulamayı tanımak
ve ona bir **profil** atamak.

Profil eşleşmesi süreç adına bakar, pencere başlığına değil. Başlık kullanıcının
açtığı dosyaya göre sürekli değişir ve güvenilmez; süreç adı sabittir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class OutputProfile(Enum):
    """Çıktının hangi biçimde üretileceği."""

    CODE = "code"
    """Kod düzenleyici. Çıktı kod veya kod yorumu; markdown sarmalı yok."""

    CHAT = "chat"
    """Anlık mesajlaşma. Kısa, doğal, gereksiz resmiyet yok."""

    DOCUMENT = "document"
    """Uzun metin. Paragraf yapısı ve noktalama önemli."""

    TERMINAL = "terminal"
    """Kabuk. Çıktı çalıştırılabilir komut olabilir; açıklama eklenmez."""

    SPREADSHEET = "spreadsheet"
    """Hesap tablosu. Formül veya hücre değeri."""

    EMAIL = "email"
    """E-posta. Profesyonel ama insani ton."""

    BROWSER = "browser"
    """Tarayıcı. Ne yazıldığı belirsiz; genel amaçlı temizlik."""

    PLAIN = "plain"
    """Tanınmayan uygulama. Yalnız temizlik, biçim varsayımı yok."""


@dataclass(frozen=True, slots=True)
class AppProfile:
    """Bir uygulamanın kimliği ve çıktı biçimi."""

    profile: OutputProfile
    #: Arayüzde gösterilecek düzgün ad ("Code" değil "VS Code").
    display_name: str


#: Süreç adı (küçük harf, `.exe` olmadan) → profil.
#:
#: Liste bilerek kısa tutuldu: tanımadığımız uygulamada `PLAIN` profiline
#: düşmek, yanlış bir profil uygulamaktan iyidir.
_APP_PROFILES: dict[str, AppProfile] = {
    # ── Kod ──────────────────────────────────────────────────────────────
    "code": AppProfile(OutputProfile.CODE, "VS Code"),
    "code - insiders": AppProfile(OutputProfile.CODE, "VS Code Insiders"),
    "cursor": AppProfile(OutputProfile.CODE, "Cursor"),
    "windsurf": AppProfile(OutputProfile.CODE, "Windsurf"),
    "antigravity ide": AppProfile(OutputProfile.CODE, "Antigravity IDE"),
    "devenv": AppProfile(OutputProfile.CODE, "Visual Studio"),
    "idea64": AppProfile(OutputProfile.CODE, "IntelliJ IDEA"),
    "pycharm64": AppProfile(OutputProfile.CODE, "PyCharm"),
    "webstorm64": AppProfile(OutputProfile.CODE, "WebStorm"),
    "rider64": AppProfile(OutputProfile.CODE, "Rider"),
    "sublime_text": AppProfile(OutputProfile.CODE, "Sublime Text"),
    "notepad++": AppProfile(OutputProfile.CODE, "Notepad++"),
    "zed": AppProfile(OutputProfile.CODE, "Zed"),
    # ── Sohbet ───────────────────────────────────────────────────────────
    "slack": AppProfile(OutputProfile.CHAT, "Slack"),
    "discord": AppProfile(OutputProfile.CHAT, "Discord"),
    "teams": AppProfile(OutputProfile.CHAT, "Microsoft Teams"),
    "ms-teams": AppProfile(OutputProfile.CHAT, "Microsoft Teams"),
    "whatsapp": AppProfile(OutputProfile.CHAT, "WhatsApp"),
    "telegram": AppProfile(OutputProfile.CHAT, "Telegram"),
    "signal": AppProfile(OutputProfile.CHAT, "Signal"),
    # ── Belge ────────────────────────────────────────────────────────────
    "winword": AppProfile(OutputProfile.DOCUMENT, "Word"),
    "notion": AppProfile(OutputProfile.DOCUMENT, "Notion"),
    "obsidian": AppProfile(OutputProfile.DOCUMENT, "Obsidian"),
    "onenote": AppProfile(OutputProfile.DOCUMENT, "OneNote"),
    "notepad": AppProfile(OutputProfile.DOCUMENT, "Not Defteri"),
    "wordpad": AppProfile(OutputProfile.DOCUMENT, "WordPad"),
    # ── Terminal ─────────────────────────────────────────────────────────
    "windowsterminal": AppProfile(OutputProfile.TERMINAL, "Windows Terminal"),
    "cmd": AppProfile(OutputProfile.TERMINAL, "Komut İstemi"),
    "powershell": AppProfile(OutputProfile.TERMINAL, "PowerShell"),
    "pwsh": AppProfile(OutputProfile.TERMINAL, "PowerShell"),
    "wt": AppProfile(OutputProfile.TERMINAL, "Windows Terminal"),
    "alacritty": AppProfile(OutputProfile.TERMINAL, "Alacritty"),
    # ── Hesap tablosu ────────────────────────────────────────────────────
    "excel": AppProfile(OutputProfile.SPREADSHEET, "Excel"),
    # ── E-posta ──────────────────────────────────────────────────────────
    "outlook": AppProfile(OutputProfile.EMAIL, "Outlook"),
    "thunderbird": AppProfile(OutputProfile.EMAIL, "Thunderbird"),
    # ── Tarayıcı ─────────────────────────────────────────────────────────
    "chrome": AppProfile(OutputProfile.BROWSER, "Chrome"),
    "msedge": AppProfile(OutputProfile.BROWSER, "Edge"),
    "firefox": AppProfile(OutputProfile.BROWSER, "Firefox"),
    "brave": AppProfile(OutputProfile.BROWSER, "Brave"),
    "opera": AppProfile(OutputProfile.BROWSER, "Opera"),
    "arc": AppProfile(OutputProfile.BROWSER, "Arc"),
}

_FALLBACK = AppProfile(OutputProfile.PLAIN, "")


def profile_for(process_name: str) -> AppProfile:
    """Süreç adından profil bulur. Tanınmıyorsa `PLAIN` döner."""
    key = process_name.lower().removesuffix(".exe").strip()
    if not key:
        return _FALLBACK

    if key in _APP_PROFILES:
        return _APP_PROFILES[key]

    # Sürüm ekli adlar: "pycharm64", "idea64" gibi kalıpları zaten tablodan
    # yakalıyoruz; kalan durumlarda rakam ekini atıp bir daha bakıyoruz.
    stripped = re.sub(r"\d+$", "", key)
    if stripped != key and stripped in _APP_PROFILES:
        return _APP_PROFILES[stripped]

    return AppProfile(OutputProfile.PLAIN, process_name.removesuffix(".exe"))


#: Profil başına çıktı yönergesi. İsteme eklenir.
#:
#: Yönergeler bilinçli olarak **kısıtlayıcı**: her biri ne YAPILMAYACAĞINI da
#: söylüyor. Dikte aracında en sık şikâyet, aracın istenmeyen biçim eklemesidir
#: (kod bloğu, başlık, madde işareti).
PROFILE_INSTRUCTIONS: dict[OutputProfile, str] = {
    OutputProfile.CODE: (
        "Kullanıcı bir kod düzenleyicisinde. Çıktı doğrudan editöre yapıştırılacak.\n"
        "- Kod isteniyorsa yalnız kodu ver; ``` ile SARMA, açıklama ekleme.\n"
        "- Değişken, fonksiyon ve kütüphane adlarını olduğu gibi koru.\n"
        "- Yorum satırı isteniyorsa dosyanın diline uygun yorum sözdizimini kullan."
    ),
    OutputProfile.CHAT: (
        "Kullanıcı bir mesajlaşma uygulamasında. Çıktı bir sohbet mesajı olacak.\n"
        "- Kısa ve doğal tut; resmi mektup diline çevirme.\n"
        "- Selamlama ve imza EKLEME — kullanıcı söylemediyse yoktur.\n"
        "- Madde işareti kullanma, düz cümle yaz."
    ),
    OutputProfile.DOCUMENT: (
        "Kullanıcı bir belge düzenleyicisinde.\n"
        "- Paragraf yapısını ve noktalamayı düzgün kur.\n"
        "- Başlık veya madde işareti EKLEME; kullanıcı istemedi."
    ),
    OutputProfile.TERMINAL: (
        "Kullanıcı bir terminalde. Çıktı doğrudan çalıştırılabilir.\n"
        "- Komut isteniyorsa yalnız komutu ver; $ veya > öneki koyma.\n"
        "- Açıklama, uyarı veya alternatif önerme.\n"
        "- ``` ile SARMA."
    ),
    OutputProfile.SPREADSHEET: (
        "Kullanıcı bir hesap tablosunda.\n"
        "- Formül isteniyorsa = ile başlayan formülü ver, açıklama ekleme.\n"
        "- Hücre değeri isteniyorsa yalnız değeri ver."
    ),
    OutputProfile.EMAIL: (
        "Kullanıcı bir e-posta istemcisinde.\n"
        "- Profesyonel ama insani bir ton kullan; kalıp cümlelerden kaçın.\n"
        "- Kullanıcı söylemediyse selamlama ve imza EKLEME."
    ),
    OutputProfile.BROWSER: (
        "Kullanıcı bir tarayıcıda; ne yazdığı belirsiz.\n"
        "- Yalnız temizlik yap, biçim varsayımında bulunma."
    ),
    OutputProfile.PLAIN: (
        "Uygulama tanınmadı. Yalnız temizlik yap, hiçbir biçim varsayımında bulunma."
    ),
}
