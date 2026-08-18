"""Anahtar denetimi — "bu düğmeler gerçekten bir şey yapıyor mu?"

## Neden var

Ayarlar ekranındaki anahtarların bir kısmı geliştirme sırasında yalnız
yerel React durumu olarak duruyordu: tıklayınca kayıyor, hiçbir şey
değiştirmiyordu. Bunlardan biri (`dynamicModel`, "%35 pil altında küçük
model") kullanıcı tarafından fark edildi. Gözle bakarak ayırt etmek
imkânsız — açık ile kapalı arasındaki fark yalnız bir animasyon.

Bu betik farkı ölçüyor. Bir anahtarın **gerçek** sayılması için iki koşul:

1. Tıklandığında görünen durumu değişmeli.
2. Pencere **yeniden yüklendiğinde** yeni değer yerinde durmalı.

Belirleyici olan ikincisi. Sahte anahtar yalnız `useState` tutuyor;
yeniden yükleme onu koda gömülü varsayılana döndürüyor. Gerçek anahtarın
değeri renderer'ın dışında — main süreçte ya da motorda — yaşıyor.

Ekran görüntüsü karşılaştırması yapmıyoruz bilinçli olarak: bir anahtarın
görsel olarak kayması zaten sahte olanın da yaptığı şey.

## Nasıl çalışır

Uygulama `--remote-debugging-port` ile açılıyor ve Chrome DevTools
Protocol üzerinden sürülüyor; anahtarlar `role="switch"` ile bulunuyor.

## İlk bulgu

Bu betiğin ilk çalıştırmasında "Sayıları rakama çevir" anahtarı yeniden
yüklemede sıfırlandı: motor değeri kaydediyordu ama hiçbir yerden
yayınlamıyordu, arayüz de her açılışta `true` varsayıyordu. Kullanıcı
kapatıp uygulamayı yeniden başlatınca anahtar açık görünüyor, boru hattı
kapalı çalışıyordu. Düzeltildi — değer artık `privacy:get` yükünde.

## Kullanım

    npm run build
    engine/.venv/Scripts/python tools/denetim/anahtar_denetimi.py

Kurulum paketini denetlemek için (asıl dağıtılan şey bu):

    npm run dist
    engine/.venv/Scripts/python tools/denetim/anahtar_denetimi.py --paketli

Paketli kip önemli: geliştirme derlemesinde çalışan bir şeyin pakette de
çalıştığı **varsayılamaz**. Eksik bir dosya ya da izin listesinde unutulan
bir IPC kanalı yalnız orada patlıyor.

Çıkış kodu: her anahtar gerçekse 0, en az biri sahteyse 1.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import websockets

KÖK = Path(__file__).resolve().parents[2]
MASAÜSTÜ = KÖK / "apps" / "desktop"
CDP_PORT = 9333

#: Uygulamanın açılıp renderer'ın hazır olması için üst sınır.
AÇILIŞ_ZAMAN_AŞIMI = 60.0
#: Tıklamadan sonra motora gidip gelmenin tamamlanması için beklenen süre.
TIKLAMA_BEKLEME = 1.2


@dataclass
class Bulgu:
    etiket: str
    başlangıç: bool | None = None
    tıklama_sonrası: bool | None = None
    yeniden_yükleme_sonrası: bool | None = None
    #: Anahtarın satırındaki açıklama metni.
    meta: str = ""
    not_: str = ""

    @property
    def görsel_değişti(self) -> bool:
        return (
            self.başlangıç is not None
            and self.tıklama_sonrası is not None
            and self.başlangıç != self.tıklama_sonrası
        )

    @property
    def kalıcı(self) -> bool:
        return (
            self.yeniden_yükleme_sonrası is not None
            and self.yeniden_yükleme_sonrası == self.tıklama_sonrası
        )

    @property
    def gerçek(self) -> bool:
        """Ölçüt **kalıcılık**, IPC değil.

        İlk sürüm `window.omnivoice.invoke` sarmalayıp çağrıları saymaya
        çalışıyordu. Ölçtük: köprü `contextBridge` ile açıldığı için nesne
        donmuş geliyor —

            Object.getOwnPropertyDescriptor(window, 'omnivoice')
              -> { configurable: false, writable: false }

        Ne atama ne `defineProperty` işliyor. Sarmalayıcı sessizce etkisiz
        kalıyor ve **her anahtar sahte görünüyordu**; ölçüm aracının kendisi
        ölçülmeden güvenilmez.

        Kalıcılık zaten daha güçlü bir ölçüt: sahte anahtar yalnız
        `useState` tutar ve yeniden yükleme onu koda gömülü varsayılana
        döndürür. Gerçek anahtarın değeri renderer'ın dışında yaşar.
        """
        if self.dev_kısıtlı:
            return True
        return self.görsel_değişti and self.kalıcı

    @property
    def dev_kısıtlı(self) -> bool:
        """Geliştirme kurulumunda bilinçli olarak etkisiz olan anahtar.

        Otomatik başlatma paketlenmemiş sürümde uygulanmıyor ve arayüz bunu
        anahtarın altında yazıyor. Bozuk saymak yanlış alarm olurdu.
        """
        return "yalnız kurulu sürümde" in self.meta or "packaged build" in self.meta

    @property
    def hüküm(self) -> str:
        if self.dev_kısıtlı:
            return "DEV'DE KAPALI (beklenen)"
        if not self.görsel_değişti:
            return "TIKLAMA İŞLEMİYOR"
        if not self.kalıcı:
            return "SAHTE (yeniden yüklemede sıfırlanıyor)"
        return "GERÇEK"


# ── CDP istemcisi ──────────────────────────────────────────────────────────


class Cdp:
    """Tek sayfaya bağlı, en küçük Chrome DevTools Protocol istemcisi."""

    def __init__(self, ws: websockets.ClientConnection) -> None:
        self._ws = ws
        self._id = 0

    async def çağır(self, yöntem: str, **parametre: object) -> dict:
        self._id += 1
        istek = self._id
        await self._ws.send(json.dumps({"id": istek, "method": yöntem, "params": parametre}))
        while True:
            ham = json.loads(await self._ws.recv())
            # Olay bildirimleri araya giriyor; yalnız kendi yanıtımızı bekliyoruz.
            if ham.get("id") == istek:
                if "error" in ham:
                    raise RuntimeError(f"{yöntem}: {ham['error']}")
                return ham.get("result", {})

    async def js(self, ifade: str) -> object:
        sonuç = await self.çağır(
            "Runtime.evaluate",
            expression=ifade,
            returnByValue=True,
            awaitPromise=True,
        )
        detay = sonuç.get("exceptionDetails")
        if detay:
            raise RuntimeError(f"JS hatası: {detay.get('text')} {detay.get('exception', {})}")
        return sonuç.get("result", {}).get("value")


# ── Uygulamayı başlatma ────────────────────────────────────────────────────


def _boş_port_mu(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


#: Paketlenmiş uygulamanın yeri.
PAKET_EXE = KÖK / "release" / "win-unpacked" / "DikteX.exe"


def electron_yolu() -> Path:
    """`node_modules` içindeki Electron ikilisi."""
    yol = MASAÜSTÜ.parent.parent / "node_modules" / "electron" / "dist" / "electron.exe"
    if yol.exists():
        return yol
    bulunan = shutil.which("electron")
    if bulunan:
        return Path(bulunan)
    raise SystemExit("Electron bulunamadı — `npm install` çalıştırıldı mı?")


def başlatma_komutu(paketli: bool) -> tuple[list[str], str | None]:
    """Denetlenecek uygulamayı başlatan komut ve çalışma dizini."""
    if paketli:
        if not PAKET_EXE.exists():
            raise SystemExit(
                "Paket bulunamadı: " + str(PAKET_EXE) + " — `npm run dist` çalıştırın."
            )
        return ([str(PAKET_EXE), f"--remote-debugging-port={CDP_PORT}"], None)
    if not (MASAÜSTÜ / "out" / "main" / "index.js").exists():
        raise SystemExit("`npm run build` çalıştırılmamış — out/ yok.")
    return (
        [str(electron_yolu()), ".", f"--remote-debugging-port={CDP_PORT}"],
        str(MASAÜSTÜ),
    )


def ayar_dosyası() -> Path:
    """Kullanıcının gerçek ayar dosyası.

    Denetim ayrı bir profil kullanmıyor: uygulamayı olduğu gibi çalıştırmak
    istiyoruz, yoksa ölçtüğümüz şey gerçek uygulama olmaz. Bedeli, denetimin
    kullanıcının **asıl ayarlarını** oynatması — ölçtük, bir çalıştırma
    `maskPii` ve `preflight` değerlerini kapalı bıraktı. Bu yüzden dosya
    baştan yedekleniyor ve sonunda geri konuyor.
    """
    kök = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(kök) / "DikteX" / "settings.json"


class AyarYedeği:
    """Ayar dosyasının denetim öncesi hâli."""

    def __init__(self) -> None:
        self._yol = ayar_dosyası()
        # Uygulama başlatılmadan ÖNCE okunuyor: motor açılışta dosyaya
        # yazabiliyor ve sonradan alınan yedek zaten kirlenmiş olurdu.
        self._içerik = self._yol.read_bytes() if self._yol.exists() else None

    def geri_koy(self) -> None:
        if self._içerik is None:
            return
        try:
            self._yol.write_bytes(self._içerik)
            print(f"Ayarlar geri kondu: {self._yol}")
        except OSError:
            # Geri koyamamak denetimi başarısız saydırmamalı, ama sessiz de
            # kalmamalı: kullanıcı ayarlarının değiştiğini bilmeli.
            print(f"UYARI: ayarlar geri konamadı — {self._yol}")


#: Kurulu/çalışan sürümün süreç adları.
ÇAKIŞAN_SÜREÇLER = {"diktex.exe", "omnivoice.exe", "diktex-engine.exe", "omnivoice-engine.exe"}


def çalışan_örnek_var_mı() -> list[str]:
    """Denetimi geçersiz kılacak süreçler.

    Uygulamada **tek örnek kilidi** var: ikinci örnek hemen kapanıyor. Ayrıca
    motor 8756 portunu tutuyor. Zaten çalışan bir DikteX varken denetim
    yapılırsa uygulama hiç açılmıyor ya da IPC çağrıları başkasının motoruna
    gidiyor — iki durumda da ölçüm yalan söyler.
    """
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        return []
    bulunan = []
    for süreç in psutil.process_iter(["name"]):
        ad = (süreç.info.get("name") or "").lower()
        if ad in ÇAKIŞAN_SÜREÇLER:
            bulunan.append(ad)
    return bulunan


async def sayfayı_bekle(port: int, süre: float, süreç: subprocess.Popen) -> str:
    """Ana pencerenin CDP adresini döndürür."""
    son = time.monotonic() + süre
    async with httpx.AsyncClient(timeout=3.0) as istemci:
        while time.monotonic() < son:
            # Erken çıkışı beklemeden yakalıyoruz: tek örnek kilidi devreye
            # girdiyse süreç saniyeler içinde ölüyor ve 60 saniye beklemek
            # yalnız tanıyı geciktirirdi.
            if süreç.poll() is not None:
                raise SystemExit(
                    f"Uygulama açılır açılmaz kapandı (çıkış {süreç.returncode}).\n"
                    "En olası sebep: başka bir DikteX örneği çalışıyor "
                    "(tek örnek kilidi). Tepsi simgesinden çıkın ve tekrar deneyin."
                )
            try:
                yanıt = await istemci.get(f"http://127.0.0.1:{port}/json/list")
                for hedef in yanıt.json():
                    # HUD, komut çubuğu ve bölge kaplaması da birer sayfa;
                    # ayarların bulunduğu ana pencereyi arıyoruz.
                    if hedef.get("type") == "page" and "main.html" in hedef.get("url", ""):
                        return str(hedef["webSocketDebuggerUrl"])
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                pass
            await asyncio.sleep(0.5)
    raise SystemExit("Ana pencere CDP üzerinden görünmedi — uygulama açıldı mı?")


# ── Renderer tarafı yardımcıları ───────────────────────────────────────────

ANAHTARLARI_LİSTELE = """
(() => Array.from(document.querySelectorAll('[role="switch"]')).map((d) => ({
  etiket: d.getAttribute('aria-label') || '(etiketsiz)',
  açık: d.getAttribute('aria-checked') === 'true',
  meta: ((d.closest('div, li, section') || d.parentElement || {}).textContent || '').slice(0, 300),
})))()
"""


def _tıkla(etiket: str) -> str:
    kaçış = json.dumps(etiket)
    return f"""
(() => {{
  const d = Array.from(document.querySelectorAll('[role="switch"]'))
    .find((x) => x.getAttribute('aria-label') === {kaçış});
  if (!d) return 'bulunamadı';
  d.click();
  return 'tıklandı';
}})()
"""


def _durum(etiket: str) -> str:
    kaçış = json.dumps(etiket)
    return f"""
(() => {{
  const d = Array.from(document.querySelectorAll('[role="switch"]'))
    .find((x) => x.getAttribute('aria-label') === {kaçış});
  return d ? d.getAttribute('aria-checked') === 'true' : null;
}})()
"""


AYARLARA_GİT = """
(() => {
  const düğmeler = Array.from(document.querySelectorAll('button, a, [role="tab"]'));
  const hedef = düğmeler.find((d) => /ayarlar|settings/i.test(d.textContent || ''));
  if (hedef) { hedef.click(); return 'geçildi'; }
  return 'ayarlar bağlantısı bulunamadı';
})()
"""


# ── Denetim ────────────────────────────────────────────────────────────────


#: Motorun bağlanmasını bekleyen yoklama.
#:
#: Bu beklemeden önce ölçüm yapmak **yanlış alarm üretiyordu**: motor
#: henüz ayakta değilken yapılan IPC çağrıları hata veriyor, anahtar
#: kımıldamıyor ve gerçek bir anahtar "sahte" damgası yiyor. Ölçüm
#: aracının, ölçtüğü sistemin hazır olmasını beklemesi gerekiyor.
MOTOR_HAZIR = """
window.omnivoice.invoke('privacy:get')
  .then(() => 'hazır')
  .catch((e) => 'bekliyor: ' + String(e))
"""


async def motoru_bekle(cdp: Cdp, süre: float = 60.0) -> None:
    son = time.monotonic() + süre
    son_hata = "?"
    while time.monotonic() < son:
        sonuç = str(await cdp.js(MOTOR_HAZIR))
        if sonuç == "hazır":
            # Motor yanıt veriyor; React'in `privacy:get` sonucunu alıp
            # yeniden çizmesi için kısa bir pay.
            await asyncio.sleep(1.5)
            return
        son_hata = sonuç
        await asyncio.sleep(1.0)
    raise SystemExit(f"Motor {süre:.0f} saniyede bağlanmadı — son durum: {son_hata}")


async def denetle(cdp: Cdp) -> list[Bulgu]:
    print("Motorun bağlanması bekleniyor...")
    await motoru_bekle(cdp)
    await cdp.js(AYARLARA_GİT)
    await asyncio.sleep(1.5)

    anahtarlar = await cdp.js(ANAHTARLARI_LİSTELE)
    if not isinstance(anahtarlar, list) or not anahtarlar:
        raise SystemExit("Hiç anahtar bulunamadı — Ayarlar ekranı açıldı mı?")

    print(f"{len(anahtarlar)} anahtar bulundu.\n")
    bulgular: list[Bulgu] = []

    for kayıt in anahtarlar:
        etiket = str(kayıt["etiket"])
        bulgu = Bulgu(
            etiket=etiket,
            başlangıç=bool(kayıt["açık"]),
            meta=str(kayıt.get("meta", "")),
        )

        sonuç = await cdp.js(_tıkla(etiket))
        if sonuç != "tıklandı":
            bulgu.not_ = str(sonuç)
            bulgular.append(bulgu)
            continue

        await asyncio.sleep(TIKLAMA_BEKLEME)
        bulgu.tıklama_sonrası = bool(await cdp.js(_durum(etiket)))
        bulgular.append(bulgu)
        print(f"  - {etiket}: {bulgu.başlangıç} -> {bulgu.tıklama_sonrası}")

    # Kalıcılık: pencereyi yeniden yükleyip değerleri tekrar okuyoruz.
    # Sahte anahtarı asıl ele veren adım: yalnız `useState` tutan bir
    # anahtar burada koda gömülü varsayılanına geri döner.
    print("\nPencere yeniden yükleniyor (kalıcılık ölçümü)...")
    await cdp.çağır("Page.reload", ignoreCache=False)
    await asyncio.sleep(2.0)
    await motoru_bekle(cdp)
    await cdp.js(AYARLARA_GİT)
    await asyncio.sleep(1.5)

    for bulgu in bulgular:
        değer = await cdp.js(_durum(bulgu.etiket))
        bulgu.yeniden_yükleme_sonrası = None if değer is None else bool(değer)

    # Bıraktığımız yerde kalmasın: her anahtar eski değerine döndürülüyor.
    print("Anahtarlar eski değerlerine döndürülüyor...")
    for bulgu in bulgular:
        if bulgu.yeniden_yükleme_sonrası is not None and (
            bulgu.yeniden_yükleme_sonrası != bulgu.başlangıç
        ):
            await cdp.js(_tıkla(bulgu.etiket))
            await asyncio.sleep(0.4)

    return bulgular


def rapor_yaz(bulgular: list[Bulgu]) -> int:
    genişlik = max((len(b.etiket) for b in bulgular), default=10) + 2
    print("\n" + "=" * (genişlik + 58))
    print(f"{'ANAHTAR':<{genişlik}} {'DEĞİŞİM':<16} {'YENİDEN YÜKLEMEDE':<20} HÜKÜM")
    print("=" * (genişlik + 60))

    sahte = 0
    for b in sorted(bulgular, key=lambda x: (x.gerçek, x.etiket)):
        değişim = (
            f"{b.başlangıç} → {b.tıklama_sonrası}"
            if b.görsel_değişti
            else "yok"
        )
        kalıcı = (
            "korundu" if b.kalıcı else f"sıfırlandı → {b.yeniden_yükleme_sonrası}"
        )
        print(f"{b.etiket:<{genişlik}} {değişim:<16} {kalıcı:<20} {b.hüküm}")
        if not b.gerçek:
            sahte += 1
            if b.not_:
                print(f"{'':<{genişlik}} └─ {b.not_}")

    print("=" * (genişlik + 60))
    toplam = len(bulgular)
    print(f"{toplam - sahte}/{toplam} anahtar gerçek.")
    if sahte:
        print(f"\n{sahte} anahtar doğrulanamadı. Yukarıdaki hükme bakın.")
    return 1 if sahte else 0


# ── Ekran denetimi ─────────────────────────────────────────────────────────
#
# Projenin şimdiye kadarki en kötü hatası, paketlenmiş uygulamanın **bomboş**
# açılmasıydı: preload'ın izin listesine eklenmeyen tek bir IPC olayı React
# ağacını çökertti ve ekranda hiçbir şey, hiçbir hata görünmedi. Pencere
# vardı, içi yoktu.
#
# Bunu gözle kontrol etmek işe yaramaz — boş bir pencere de "açıldı" gibi
# görünür. Ölçülebilir olan iki şey var: gövdede gerçekten içerik var mı, ve
# yakalanmamış bir istisna atıldı mı.


@dataclass
class EkranBulgusu:
    ad: str
    metin_uzunluğu: int = 0
    hatalar: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.hatalar is None:
            self.hatalar = []

    @property
    def sağlam(self) -> bool:
        # 40 karakter eşiği: boş bir React kabuğu da birkaç karakter üretiyor
        # (başlık çubuğu, kenar çubuğu iskeleti). Gerçek bir ekran bundan çok
        # daha fazlasını yazıyor.
        return self.metin_uzunluğu > 40 and not self.hatalar

    @property
    def hüküm(self) -> str:
        if self.hatalar:
            return "ÇÖKTÜ"
        if self.metin_uzunluğu <= 40:
            return "BOŞ"
        return "ÇİZİLDİ"


#: Yakalanmamış hataları toplayan tuzak.
#:
#: React bir hata sınırı olmadan çöktüğünde konsola yazıyor ama ekranda
#: hiçbir iz bırakmıyor. `window.onerror` ve reddedilen söz yakalayıcısı,
#: sessiz çöküşü görünür kılan tek yol.
HATA_TUZAĞI = """
(() => {
  if (window.__hatalar) return 'zaten kurulu';
  window.__hatalar = [];
  window.addEventListener('error', (o) => {
    window.__hatalar.push(String((o.error && o.error.stack) || o.message));
  });
  window.addEventListener('unhandledrejection', (o) => {
    window.__hatalar.push('reddedilen söz: ' + String(o.reason));
  });
  return 'kuruldu';
})()
"""

EKRANLARI_LİSTELE = """
(() => Array.from(document.querySelectorAll('nav button'))
  .map((d) => (d.textContent || '').trim())
  .filter((t) => t.length > 0))()
"""


def _ekrana_git(ad: str) -> str:
    kaçış = json.dumps(ad)
    return f"""
(() => {{
  const d = Array.from(document.querySelectorAll('nav button'))
    .find((x) => (x.textContent || '').trim() === {kaçış});
  if (!d) return 'bulunamadı';
  d.click();
  return 'tıklandı';
}})()
"""


GÖVDE_UZUNLUĞU = """
(() => {
  const ana = document.querySelector('main') || document.body;
  return (ana.innerText || '').trim().length;
})()
"""


async def arayüzü_bekle(cdp: Cdp, süre: float = 60.0) -> None:
    """Kenar çubuğu çizilene kadar bekler.

    Ölçmeden önce beklemek şart. Paketlenmiş sürümde arayüz geliştirme
    derlemesinden geç açılıyor ve beklemeden bakınca gezinme hiç
    bulunamıyordu — "hiçbir ekran çizilmiyor" gibi görünen bir yanlış alarm.
    Anahtar denetiminde aynı hata bir kez yapılmıştı.
    """
    son = time.monotonic() + süre
    while time.monotonic() < son:
        if int(await cdp.js("document.querySelectorAll('nav button').length") or 0) > 0:
            return
        await asyncio.sleep(0.5)
    raise SystemExit(f"Arayüz {süre:.0f} saniyede çizilmedi — pencere boş açılmış olabilir.")


async def ekranları_denetle(cdp: Cdp) -> list[EkranBulgusu]:
    await cdp.js(HATA_TUZAĞI)
    await arayüzü_bekle(cdp)
    ekranlar = await cdp.js(EKRANLARI_LİSTELE)
    if not isinstance(ekranlar, list) or not ekranlar:
        return [EkranBulgusu(ad="(gezinme bulunamadı)")]

    bulgular: list[EkranBulgusu] = []
    for ad in ekranlar:
        await cdp.js("window.__hatalar = []")
        if await cdp.js(_ekrana_git(str(ad))) != "tıklandı":
            continue
        await asyncio.sleep(1.2)
        bulgu = EkranBulgusu(ad=str(ad))
        bulgu.metin_uzunluğu = int(await cdp.js(GÖVDE_UZUNLUĞU) or 0)
        bulgu.hatalar = [str(h)[:160] for h in (await cdp.js("window.__hatalar") or [])]
        bulgular.append(bulgu)
        print(f"  - {ad}: {bulgu.metin_uzunluğu} karakter, {bulgu.hüküm}")
    return bulgular


def ekran_raporu(bulgular: list[EkranBulgusu]) -> int:
    genişlik = max((len(b.ad) for b in bulgular), default=10) + 2
    print()
    print("=" * (genişlik + 34))
    print(f"{'EKRAN':<{genişlik}} {'İÇERİK':<12} HÜKÜM")
    print("=" * (genişlik + 34))
    bozuk = 0
    for b in bulgular:
        print(f"{b.ad:<{genişlik}} {str(b.metin_uzunluğu) + ' krk':<12} {b.hüküm}")
        if not b.sağlam:
            bozuk += 1
            for h in b.hatalar[:2]:
                print(f"{'':<{genişlik}} +- {h}")
    print("=" * (genişlik + 34))
    print(f"{len(bulgular) - bozuk}/{len(bulgular)} ekran çiziliyor.")
    return 1 if bozuk else 0


async def main() -> int:
    paketli = "--paketli" in sys.argv
    komut, çalışma_dizini = başlatma_komutu(paketli)
    print("Denetlenen:", "KURULUM PAKETİ" if paketli else "geliştirme derlemesi")

    if not _boş_port_mu(CDP_PORT):
        raise SystemExit(f"{CDP_PORT} portu dolu; başka bir denetim mi çalışıyor?")

    çakışan = çalışan_örnek_var_mı()
    if çakışan:
        raise SystemExit(
            "Çalışan bir DikteX örneği var: "
            + ", ".join(sorted(set(çakışan)))
            + "\n"
            "Tek örnek kilidi yüzünden denetim kendi örneğini açamaz. "
            "Tepsi simgesinden çıkıp tekrar deneyin."
        )

    ortam = dict(os.environ)
    # Denetim gerçek dikte yapmıyor; motor yine de açılıyor çünkü ayarların
    # çoğu oraya yazılıyor ve kalıcılık ölçümü onsuz anlamsız olurdu.
    yedek = AyarYedeği()
    süreç = subprocess.Popen(komut, cwd=çalışma_dizini, env=ortam)
    try:
        adres = await sayfayı_bekle(CDP_PORT, AÇILIŞ_ZAMAN_AŞIMI, süreç)
        async with websockets.connect(adres, max_size=None) as ws:
            cdp = Cdp(ws)
            await cdp.çağır("Runtime.enable")
            await cdp.çağır("Page.enable")
            print()
            print("--- EKRANLAR ---")
            ekranlar = await ekranları_denetle(cdp)
            print()
            print("--- ANAHTARLAR ---")
            bulgular = await denetle(cdp)
        # İkisi de çalışsın istiyoruz; biri patlarsa diğerinin sonucu da
        # görünmeli, yoksa her koşuda tek bir sorun öğreniyoruz.
        kod = ekran_raporu(ekranlar)
        return max(kod, rapor_yaz(bulgular))
    finally:
        süreç.terminate()
        try:
            süreç.wait(timeout=10)
        except subprocess.TimeoutExpired:
            süreç.kill()
        # Motor kapanırken son bir kez yazabiliyor; yedeği ondan SONRA
        # geri koyuyoruz, yoksa geri koyduğumuz değer hemen eziliyor.
        time.sleep(1.5)
        yedek.geri_koy()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
