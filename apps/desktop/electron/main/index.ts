import { app, BrowserWindow, type Tray } from 'electron'
import { EngineSupervisor } from './engine'
import { createMainWindow } from './windows/mainWindow'
import {
  createHudWindow,
  releaseHudFocus,
  syncHud,
  syncMeetingHud,
} from './windows/hudWindow'
import { createTray } from './tray'
import { registerIpc } from './ipc'
import { loadEnv } from './env'
import {
  DictationController,
  broadcastDictation,
  setHudFocusReleaser,
  setMainWindowResolver,
} from './dictation'
import { MeetingController, broadcastMeeting } from './meeting'
import { registerHotkeys, unregisterHotkeys } from './hotkeys'

/** Motorun dinlediği port. `.env.local` ile değiştirilebilir. */
const DEFAULT_ENGINE_PORT = 8756

// Tek örnek kilidi: DikteX global kısayol ve tek bir motor süreci sahiplenir.
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

  // Sesli arama sonucu ana pencereye gidiyor (Faz 7.13); dikte denetleyicisi
  // pencereyi kendisi bulamaz, çünkü HUD ve bölge kaplaması da birer
  // BrowserWindow.
  setMainWindowResolver(getMainWindow)

  const getHudWindow = (): BrowserWindow => {
    if (hudWindow.isDestroyed()) hudWindow = createHudWindow()
    return hudWindow
  }

  // Yapıştırmadan önce HUD ön planı bırakıyor: motor ön planda olmadığı
  // için hedef pencereyi kendi başına öne getirmekte zorlanıyor.
  setHudFocusReleaser(() => releaseHudFocus(getHudWindow()))

  const dictation = new DictationController(engine, (state) => {
    broadcastDictation(state)
    syncHud(getHudWindow(), state)
  })

  const meeting = new MeetingController(engine, (state) => {
    broadcastMeeting(state)
    // Toplantı HUD'u dikte HUD'uyla aynı pencereyi paylaşıyor; ikisi aynı
    // anda çalışamaz (motor da bunu engelliyor), bu yüzden tek pencere yeterli.
    syncMeetingHud(getHudWindow(), state)
  })

  // Kısayolları IPC'den önce kaydediyoruz: `modes:list` yanıtı hangi
  // kısayolun kaydedilebildiğini de taşıyor.
  const hotkeys = registerHotkeys(dictation)
  if (hotkeys.conflicts.length > 0) {
    console.warn(`[kısayol] çakışan kısayollar: ${hotkeys.conflicts.join(', ')}`)
  }

  registerIpc({ engine, dictation, meeting, hotkeys, getMainWindow })
  tray = createTray(getMainWindow, dictation)

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
  // çalışması DikteX'in işleyişinin bir parçası.
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
