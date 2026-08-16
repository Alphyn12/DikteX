import { app, BrowserWindow, type Tray } from 'electron'
import { EngineSupervisor } from './engine'
import { createMainWindow } from './windows/mainWindow'
import { createTray } from './tray'
import { registerIpc } from './ipc'
import { loadEnv } from './env'

/** Motorun dinlediği port. `.env.local` ile değiştirilebilir. */
const DEFAULT_ENGINE_PORT = 8756

// Tek örnek kilidi: OmniVoice global kısayol ve tek bir motor süreci sahiplenir.
// İkinci bir örnek bunları ele geçirip ilkini bozar.
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  void main()
}

async function main(): Promise<void> {
  const env = loadEnv()
  const port = Number(env['OMNIVOICE_ENGINE_PORT'] ?? DEFAULT_ENGINE_PORT)

  const engine = new EngineSupervisor({ port })

  // `quit()` çağrılmadan pencereyi gerçekten yok etmeyiz; kapatma tepsiye çeker.
  let quitting = false

  app.on('second-instance', () => {
    const window = mainWindow
    if (!window || window.isDestroyed()) return
    if (!window.isVisible()) window.show()
    if (window.isMinimized()) window.restore()
    window.focus()
  })

  await app.whenReady()

  let mainWindow = createMainWindow()
  // Tepsi referansı tutulmazsa çöp toplayıcı ikonu yok eder.
  let tray: Tray | null = null

  const getMainWindow = (): BrowserWindow => {
    if (mainWindow.isDestroyed()) mainWindow = createMainWindow()
    return mainWindow
  }

  registerIpc({ engine, getMainWindow })
  tray = createTray(getMainWindow)

  // Başlık çubuğundaki X ve sistem kapatma isteği pencereyi gizler.
  mainWindow.on('close', (event) => {
    if (quitting) return
    event.preventDefault()
    mainWindow.hide()
  })

  engine.start()

  engine.on('state', (state) => {
    for (const window of BrowserWindow.getAllWindows()) {
      if (!window.isDestroyed()) window.webContents.send('engine:state-changed', state)
    }
  })

  app.on('activate', () => {
    getMainWindow().show()
  })

  // Pencere gizlendiğinde uygulama yaşamaya devam eder — arka planda
  // çalışması OmniVoice'un işleyişinin bir parçası.
  app.on('window-all-closed', () => {
    // Bilerek boş: çıkış yalnız tepsi menüsünden yapılır.
  })

  app.on('before-quit', () => {
    quitting = true
    engine.stop()
    tray?.destroy()
    tray = null
  })
}
