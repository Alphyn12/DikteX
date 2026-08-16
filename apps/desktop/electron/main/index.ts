import { app, BrowserWindow, type Tray } from 'electron'
import { EngineSupervisor } from './engine'
import { createMainWindow } from './windows/mainWindow'
import { createHudWindow, syncHud } from './windows/hudWindow'
import { createTray } from './tray'
import { registerIpc } from './ipc'
import { loadEnv } from './env'
import { DictationController, broadcastDictation } from './dictation'
import { registerHotkeys, unregisterHotkeys } from './hotkeys'

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
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (!mainWindow.isVisible()) mainWindow.show()
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  })

  await app.whenReady()

  let mainWindow = createMainWindow()
  let hudWindow = createHudWindow()
  // Tepsi referansı tutulmazsa çöp toplayıcı ikonu yok eder.
  let tray: Tray | null = null

  const getMainWindow = (): BrowserWindow => {
    if (mainWindow.isDestroyed()) mainWindow = createMainWindow()
    return mainWindow
  }

  const getHudWindow = (): BrowserWindow => {
    if (hudWindow.isDestroyed()) hudWindow = createHudWindow()
    return hudWindow
  }

  const dictation = new DictationController(engine, (state) => {
    broadcastDictation(state)
    syncHud(getHudWindow(), state)
  })

  registerIpc({ engine, dictation, getMainWindow })
  tray = createTray(getMainWindow, dictation)
  registerHotkeys(dictation)

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
    unregisterHotkeys()
    engine.stop()
    tray?.destroy()
    tray = null
  })
}
