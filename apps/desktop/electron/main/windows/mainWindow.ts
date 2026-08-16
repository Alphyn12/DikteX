import { join } from 'node:path'
import { BrowserWindow, shell } from 'electron'

/**
 * Ana pencere.
 *
 * Mockup'taki pencere gövdesi 1308×812. Varsayılan boyutu buna yakın tutup
 * kenar boşluğu bırakıyoruz. Başlık çubuğu gizli — 40 px'lik çubuğu kendimiz
 * çiziyoruz (bkz. DESIGN-TOKENS.md § 6).
 */
export function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1320,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    // Mica'nın duvar kağıdını süzebilmesi için gövdenin saydam olması gerekir.
    backgroundColor: '#00000000',
    backgroundMaterial: 'mica',
    roundedCorners: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      // Renderer'ın dosya sistemine veya Node'a doğrudan erişimi yoktur;
      // her şey preload'daki dar köprüden geçer.
    },
  })

  // Pencere boyanmadan gösterilirse beyaz bir çakma görülür.
  window.once('ready-to-show', () => window.show())

  // Dış bağlantılar uygulamanın içinde değil, varsayılan tarayıcıda açılır.
  window.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  loadRenderer(window, 'main')

  return window
}

/**
 * Geliştirmede Vite sunucusundan, ürün sürümünde derlenmiş dosyadan yükler.
 * Her yüzen katman kendi HTML giriş noktasına sahiptir.
 */
export function loadRenderer(window: BrowserWindow, entry: 'main' | 'hud' | 'commandbar'): void {
  const devServer = process.env['ELECTRON_RENDERER_URL']
  if (devServer) {
    void window.loadURL(`${devServer}/${entry}.html`)
  } else {
    void window.loadFile(join(__dirname, `../renderer/${entry}.html`))
  }
}
