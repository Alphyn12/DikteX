import { app } from 'electron'

/**
 * Windows açılışında otomatik başlatma (Faz 6.5).
 *
 * Electron'un `setLoginItemSettings` API'si Windows'ta kayıt defterindeki
 * `Run` anahtarına yazıyor. Elle registry'ye dokunmuyoruz: Electron zaten
 * paketlenmiş/paketlenmemiş farkını ve yol tırnaklamasını doğru hallediyor.
 *
 * ## Neden `--hidden` argümanı
 *
 * Otomatik başlayan bir dikte aracının kullanıcının önüne pencere açması
 * saçma: kullanıcı bilgisayarı başka bir iş için açtı. Uygulama tepsiye
 * inip kısayolu beklemeli. Argüman `index.ts` tarafından okunuyor.
 *
 * ## Geliştirme kurulumunda kapalı
 *
 * `app.isPackaged` false iken kaydolmak, kullanıcının makinesinde
 * `electron.exe`'yi çalıştıran bir açılış girdisi bırakırdı — proje klasörü
 * taşınırsa da bozuk kalırdı. Geliştirmede ayar okunuyor ama uygulanmıyor.
 */

export const HIDDEN_FLAG = '--hidden'

/**
 * Kayıt defterindeki girdinin adı.
 *
 * Ad verilmezse Electron `electron.app.Electron` yazıyor — ölçtük, gerçekten
 * öyle yazmıştı. Görev Yöneticisi'nin "Başlangıç uygulamaları" sekmesinde
 * kullanıcı bunu görüyor ve DikteX'i bulamadığı için ayarın çalışmadığını
 * sanıyor. Kullanıcı bu ekranı, ayarın açık olup olmadığını doğrulamak için
 * açar; orada uygulamanın adını görmesi işlevin kendisi kadar önemli.
 */
const REGISTRY_NAME = 'DikteX'

/** Ad verilmeden yazılmış eski girdiler. Yeniden adlandırmadan önceki sürüm. */
const LEGACY_NAMES = ['electron.app.Electron', 'OmniVoice']

export interface AutostartState {
  enabled: boolean
  /**
   * Ayar gerçekten uygulanabiliyor mu.
   *
   * Geliştirme kurulumunda `false`. Arayüzün bunu göstermesi gerekiyor;
   * yoksa kullanıcı anahtarı açar, hiçbir şey olmaz ve sebebini bilemez.
   */
  supported: boolean
}

export function getAutostart(): AutostartState {
  if (!app.isPackaged) {
    return { enabled: false, supported: false }
  }
  return { enabled: readEnabled(), supported: true }
}

export function setAutostart(enabled: boolean): AutostartState {
  if (!app.isPackaged) {
    return { enabled: false, supported: false }
  }

  clearLegacyEntries()

  app.setLoginItemSettings({
    name: REGISTRY_NAME,
    // `name` verildiğinde Electron yolu kendisi çıkarmıyor; açıkça vermek
    // gerekiyor. Aksi hâlde girdi yazılır ama boş bir komutla.
    path: process.execPath,
    openAtLogin: enabled,
    // Tepsiye inerek başlasın; kullanıcının önüne pencere açmasın.
    args: enabled ? [HIDDEN_FLAG] : [],
  })

  // Yazdığımızı geri OKUYORUZ: `setLoginItemSettings` sessizce başarısız
  // olabiliyor (ilke kısıtları, taşınabilir kurulum). Kullanıcıya "açık"
  // deyip açılışta başlamamak, en kötü sonuç.
  return { enabled: readEnabled(), supported: true }
}

/**
 * Açılış girdisinin gerçekten yazılı ve etkin olup olmadığı.
 *
 * ## Neden `openAtLogin` okumuyoruz — kullanıcının gördüğü hatanın kaynağı
 *
 * Bu ayar "açtım, hiçbir şey olmadı" diye bildirildi. Ölçtük: kayıt defterine
 * girdi **yazılıyordu**, sorun okumadaydı.
 *
 * `getLoginItemSettings().openAtLogin` iki koşulu birden arıyor:
 *   * girdinin adı Electron'un varsayılan adı olacak, **ve**
 *   * seçeneklerde verilen `args` girdideki argümanlarla birebir tutacak.
 *
 * Eski kod `--hidden` ile yazıp seçeneksiz okuyordu; ölçümde bu her zaman
 * `false` döndü. Anahtar açılıyor, `setAutostart` geri `false` okuyor ve
 * arayüz anahtarı kapalı gösteriyordu.
 *
 * Ölçülen değerler (Electron 43, aynı çalıştırma içinde):
 *
 *     adsız yazma + args ile okuma   → openAtLogin: true
 *     adsız yazma + argsız okuma     → openAtLogin: false
 *     adsız yazma + seçeneksiz okuma → openAtLogin: false   ← eski kod
 *     adlı  yazma + args ile okuma   → openAtLogin: false   ← ad yüzünden
 *
 * Kendi adımızla yazdığımız için `openAtLogin` bize hiçbir zaman `true`
 * demeyecek. Doğru kaynak `launchItems`: girdiyi adıyla buluyoruz ve
 * `enabled` alanına bakıyoruz — bu alan Görev Yöneticisi'nden yapılan
 * devre dışı bırakmayı da yansıtıyor, yani kullanıcı oradan kapatırsa
 * arayüz de kapalı gösteriyor.
 */
function readEnabled(): boolean {
  const settings = app.getLoginItemSettings({
    path: process.execPath,
    args: [HIDDEN_FLAG],
  })
  const entry = settings.launchItems?.find((item) => item.name === REGISTRY_NAME)
  return entry?.enabled ?? false
}

/**
 * Eski adla yazılmış açılış girdilerini siler.
 *
 * Uygulama `C:\Program Files\OmniVoice`'tan `DikteX`'e taşındığı için eski
 * girdi artık var olmayan bir yolu gösteriyor. Bırakılırsa Windows her
 * açılışta onu çalıştırmayı deneyip sessizce başarısız olur ve kullanıcının
 * başlangıç listesinde ölü bir satır kalır.
 */
function clearLegacyEntries(): void {
  for (const name of LEGACY_NAMES) {
    if (name === REGISTRY_NAME) continue
    try {
      // Koşulsuz siliyoruz: girdi yoksa bu bir no-op. Varlığını önce
      // sormanın yolu yok — okuma tarafı adı kabul etmiyor.
      app.setLoginItemSettings({ name, openAtLogin: false })
    } catch {
      // Girdi yoksa ya da okunamıyorsa yapacak bir şey yok; temizlik
      // en iyi çaba, ana işlevi engellememeli.
    }
  }
}

/** Uygulama otomatik başlatmayla mı açıldı? */
export function startedHidden(argv: readonly string[] = process.argv): boolean {
  return argv.includes(HIDDEN_FLAG)
}
