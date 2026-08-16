import { app, BrowserWindow } from 'electron'
import { EngineSupervisor } from './engine'
import { createMainWindow } from './windows/mainWindow'
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

  app.on('second-instance', () => {
    const [window] = BrowserWindow.getAllWindows()
    if (!window) return
    if (window.isMinimized()) window.restore()
    window.focus()
  })

  await app.whenReady()

  const mainWindow = createMainWindow()
  registerIpc({ engine, getMainWindow: () => mainWindow })

  engine.start()

  // Motorun durumu değiştikçe arayüzü haberdar et.
  engine.on('state', (state) => {
    for (const window of BrowserWindow.getAllWindows()) {
      if (!window.isDestroyed()) window.webContents.send('engine:state-changed', state)
    }
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow()
  })

  // Windows'ta son pencere kapanınca uygulama biter. (Tepsi ikonu Faz 1.6'da
  // eklenince bu davranış değişecek: pencere kapanacak, uygulama yaşayacak.)
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })

  // Motor süreci uygulamayla birlikte ölmeli; yoksa arkada yetim kalır.
  app.on('before-quit', () => engine.stop())
}
