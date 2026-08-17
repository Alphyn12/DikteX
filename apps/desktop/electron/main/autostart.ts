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
  return { enabled: app.getLoginItemSettings().openAtLogin, supported: true }
}

export function setAutostart(enabled: boolean): AutostartState {
  if (!app.isPackaged) {
    return { enabled: false, supported: false }
  }

  app.setLoginItemSettings({
    openAtLogin: enabled,
    // Tepsiye inerek başlasın; kullanıcının önüne pencere açmasın.
    args: enabled ? [HIDDEN_FLAG] : [],
  })

  // Yazdığımızı geri OKUYORUZ: `setLoginItemSettings` sessizce başarısız
  // olabiliyor (ilke kısıtları, taşınabilir kurulum). Kullanıcıya "açık"
  // deyip açılışta başlamamak, en kötü sonuç.
  return { enabled: app.getLoginItemSettings().openAtLogin, supported: true }
}

/** Uygulama otomatik başlatmayla mı açıldı? */
export function startedHidden(argv: readonly string[] = process.argv): boolean {
  return argv.includes(HIDDEN_FLAG)
}
