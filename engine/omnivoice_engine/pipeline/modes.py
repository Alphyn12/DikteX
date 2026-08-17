"""Dikte modları (Properties II, IV.5).

Bir **mod**, konuşmanın nasıl işleneceğini belirleyen paket: sistem istemi,
model, sağlayıcı, kısayol ve davranış bayrakları. Kullanıcı chorded kısayolla
(Ctrl+Alt+Space → K) mod seçer.

Modlar burada tek yerde tanımlanır; arayüzdeki tablo, kısayol kaydı ve boru
hattı hepsi bu listeden okur. Yeni bir mod eklemek tek bir kayıt eklemektir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModeId(str, Enum):
    QUICK = "quick"
    CODE = "code"
    TRANSLATE_EN = "translate_en"
    MEGA_PROMPT = "mega_prompt"
    IMAGE_PROMPT = "image_prompt"
    SQL = "sql"
    COMMIT = "commit"
    SCREEN = "screen"
    SEARCH = "search"


@dataclass(frozen=True, slots=True)
class Mode:
    """Bir dikte modunun tanımı."""

    id: ModeId
    #: Chorded kısayolun ikinci tuşu. `None` ise yalnız temel kısayolla açılır.
    chord_key: str | None
    #: Arayüzdeki renk kimliği (bkz. DESIGN-TOKENS.md § 2).
    module: str
    #: Modelin görevini anlatan yönerge. Ortak kurallara **eklenir**.
    instruction: str
    #: Bu mod için tercih edilen model. `None` ise varsayılan kullanılır.
    model: str | None = None
    #: Çıktı yapıştırılmadan önce onay penceresi zorunlu mu?
    require_preflight: bool = False
    #: Seçili metin otomatik okunsun mu?
    uses_selection: bool = False
    #: Aktif dizindeki `git diff` okunup isteme eklensin mi (Properties V.5)?
    uses_git_diff: bool = False
    #: Konuşmadan önce ekrandan bölge seçilsin mi (Properties V.2)?
    uses_screen_region: bool = False
    #: Uygulama profiline göre biçim yönergesi eklensin mi?
    #:
    #: Kapalı olduğu modlar çıktının biçimini kendisi belirler; üstüne bir de
    #: "kullanıcı Slack'te, kısa yaz" demek çelişkili yönerge üretirdi.
    use_app_profile: bool = True
    #: Daha uzun çıktı gereken modlar için üst sınır.
    max_tokens: int = 2000
    #: Yaratıcılık. Temizlik işleri deterministik olmalı.
    temperature: float = 0.2
    aliases: tuple[str, ...] = field(default_factory=tuple)


#: Ortak yasaklar tüm modlara uygulanır (Properties II.9 — Negative Prompting).
FORBIDDEN_RULES = """\
KESİN YASAKLAR:
- Metne yeni bilgi, cümle, örnek veya açıklama EKLEME.
- Soru sorma, öneride bulunma, yorum yapma.
- "İşte", "Tabii", "Elbette", "Anladım" gibi giriş cümlesi yazma.
- Metni tırnak içine alma, kod bloğuna sarma, başlık ekleme.
- "Umarım yardımcı olmuştur" gibi kapanış cümlesi yazma.
- Kullanıcının üslubunu resmileştirme veya yapay zeka diline çevirme.

YALNIZCA istenen çıktıyı döndür, başka hiçbir şey yazma."""


MODES: dict[ModeId, Mode] = {
    ModeId.QUICK: Mode(
        id=ModeId.QUICK,
        chord_key=None,
        module="audio",
        instruction=(
            "Sana konuşmadan metne çevrilmiş ham bir metin verilir. "
            "Görevin onu okunabilir hâle getirmek.\n"
            "- Bağlama göre anlamsız kalan dolgu kelimeleri çıkar "
            '("yani", "işte", "şey", "hani", "falan") — ama cümlenin öznesi '
            "veya anlamlı bir parçasıysa BIRAK.\n"
            "- Kekeleme ve yarım kalmış kelime tekrarlarını temizle.\n"
            "- Noktalama ve büyük/küçük harfleri düzelt.\n"
            "- Kendini düzeltmeleri uygula: "
            '"salı, yok pardon çarşamba" → "çarşamba".\n'
            "- Açık yazım ve dilbilgisi hatalarını düzelt.\n"
            "- Uzunluğu koru; özetleme."
        ),
    ),
    ModeId.CODE: Mode(
        id=ModeId.CODE,
        chord_key="K",
        module="prompt",
        instruction=(
            "Kullanıcı bir kod düzenleyicisinde konuşuyor ve koddan bahsediyor.\n"
            "- Kod isteniyorsa yalnız kodu üret.\n"
            "- Seçili bir kod bloğu verildiyse istenen değişikliği ona uygula "
            "ve TÜM bloğu değiştirilmiş hâliyle döndür.\n"
            "- Var olan girinti, adlandırma ve yorum biçimini koru.\n"
            "- Docstring ve yorumları silme.\n"
            "- Kodu ``` ile SARMA."
        ),
        uses_selection=True,
        require_preflight=True,
        max_tokens=4000,
    ),
    ModeId.TRANSLATE_EN: Mode(
        id=ModeId.TRANSLATE_EN,
        chord_key="E",
        module="system",
        instruction=(
            "Kullanıcı Türkçe konuştu, çıktı İNGİLİZCE olacak.\n"
            "- Anlamı ve tonu koru; birebir kelime çevirisi yapma.\n"
            "- Teknik terimleri İngilizce'deki yerleşik karşılıklarıyla ver.\n"
            "- Dolgu kelimeleri çeviriye taşıma."
        ),
        # Uygulama profili kapalı: bu modun çıktısı zaten "İngilizce metin",
        # üstüne bir de biçim yönergesi eklemek çelişki yaratır.
        use_app_profile=False,
    ),
    ModeId.MEGA_PROMPT: Mode(
        id=ModeId.MEGA_PROMPT,
        chord_key="M",
        module="prompt",
        instruction=(
            "Kullanıcı dağınık bir fikri sesli anlattı. Bunu başka bir yapay "
            "zekaya verilecek, iyi yapılandırılmış bir İSTEME dönüştür.\n"
            "İstem şu bölümleri içermeli (yalnız kullanıcının söylediklerinden "
            "türet, UYDURMA):\n"
            "- Rol: modelin hangi uzmanlıkla davranacağı\n"
            "- Görev: ne yapılacağı, aşamalara bölünmüş\n"
            "- Bağlam: kullanıcının verdiği arka plan\n"
            "- Kısıtlar: uyulacak sınırlar\n"
            "- Çıktı biçimi: sonucun nasıl görüneceği\n"
            "Kullanıcının vermediği bir bölümü boş bırakma, o başlığı hiç yazma."
        ),
        use_app_profile=False,
        require_preflight=True,
        max_tokens=4000,
        temperature=0.4,
    ),
    ModeId.IMAGE_PROMPT: Mode(
        id=ModeId.IMAGE_PROMPT,
        chord_key="G",
        module="meeting",
        instruction=(
            "Kullanıcının anlattığı görseli bir GÖRSEL ÜRETİM İSTEMİNE çevir.\n"
            "- İngilizce yaz; görsel üretim modelleri İngilizce'de daha iyi.\n"
            "- Özne, ortam, ışık, kompozisyon, stil ve teknik ayrıntıları "
            "virgülle ayrılmış öbekler hâlinde ver.\n"
            "- Kullanıcının söylemediği bir stil UYDURMA.\n"
            "- Tek satır olarak döndür."
        ),
        use_app_profile=False,
        require_preflight=True,
        temperature=0.5,
    ),
    ModeId.SQL: Mode(
        id=ModeId.SQL,
        chord_key="S",
        module="automation",
        instruction=(
            "Kullanıcının anlattığı sorguyu SQL'e çevir.\n"
            "- Yalnız SQL döndür; açıklama ve ``` ekleme.\n"
            "- Tablo ve sütun adlarını kullanıcının söylediği gibi kullan, "
            "tahmin ederek DEĞİŞTİRME.\n"
            "- Kullanıcı lehçe belirtmediyse standart SQL kullan."
        ),
        use_app_profile=False,
        require_preflight=True,
    ),
    ModeId.SEARCH: Mode(
        id=ModeId.SEARCH,
        chord_key="A",
        module="system",
        # Bu mod LLM'e HİÇ gitmiyor; yönerge yalnız arayüz tutarlılığı için
        # duruyor. Sesli bir arama sorgusunu modele göndermek hem para hem
        # gecikme harcar, hem de sorguyu "düzelterek" bozabilir.
        instruction="Bu mod yerel çalışır; metin doğrudan arama kutusuna gider.",
        require_preflight=False,
        use_app_profile=False,
        aliases=("ara", "arama", "gecmis", "geçmiş"),
    ),
    ModeId.COMMIT: Mode(
        id=ModeId.COMMIT,
        chord_key="C",
        module="automation",
        instruction=(
            "Bir conventional commit mesajı yaz.\n"
            "- Sana `git diff` verildiyse mesajı ÖNCELİKLE ona dayandır; "
            "kullanıcının sesli notu niyeti açıklar, diff ise gerçekte ne "
            "değiştiğini gösterir.\n"
            "- Biçim: <tip>(<kapsam>): <özet>\n"
            "- Tip: feat, fix, docs, style, refactor, test, chore\n"
            "- Özet 72 karakteri geçmesin, küçük harfle başlasın, nokta ile "
            "bitmesin.\n"
            "- Değişiklik birden fazla konuyu kapsıyorsa boş satırdan sonra "
            "madde işaretli gövde ekle.\n"
            "- Kapsamı diff'teki dosya yollarından çıkar; belirsizse parantezi "
            "hiç yazma.\n"
            "- Diff'te GÖRMEDİĞİN bir değişikliği mesaja yazma."
        ),
        use_app_profile=False,
        require_preflight=True,
        uses_git_diff=True,
        max_tokens=1000,
    ),
    ModeId.SCREEN: Mode(
        id=ModeId.SCREEN,
        chord_key="R",
        module="system",
        # Bu modun asıl yönergesi `vision_prompts.py` içinde; burada yalnız
        # mod kaydı için bir özet duruyor.
        instruction=(
            "Kullanıcı ekrandan bir bölge seçti ve onun hakkında soru soruyor. "
            "Gördüğüne dayan, okuyamadığını uydurma."
        ),
        use_app_profile=False,
        uses_screen_region=True,
        require_preflight=True,
        max_tokens=1500,
        temperature=0.3,
    ),
}


#: Takma ad → mod. Modül yüklenirken bir kez kuruluyor.
#:
#: `Mode.aliases` alanı vardı ama **hiçbir yerden okunmuyordu** — yani her
#: modda tanımlı, hiç çalışmayan bir alan. Buraya bağlandı.
_ALIASES: dict[str, ModeId] = {
    alias.lower(): mode.id for mode in MODES.values() for alias in mode.aliases
}


def get_mode(mode_id: ModeId | str) -> Mode:
    """Kimlikten mod döndürür. Bilinmeyen kimlik hızlı dikteye düşer."""
    if isinstance(mode_id, str):
        try:
            mode_id = ModeId(mode_id)
        except ValueError:
            resolved = _ALIASES.get(mode_id.strip().lower())
            if resolved is None:
                return MODES[ModeId.QUICK]
            mode_id = resolved
    return MODES.get(mode_id, MODES[ModeId.QUICK])


def mode_for_chord(key: str) -> Mode | None:
    """Chorded kısayolun ikinci tuşundan mod bulur."""
    upper = key.upper()
    for mode in MODES.values():
        if mode.chord_key and mode.chord_key == upper:
            return mode
    return None


def chorded_modes() -> list[Mode]:
    """Kısayolu olan modlar — arayüzde ve kanca kaydında listelenir."""
    return [mode for mode in MODES.values() if mode.chord_key]
