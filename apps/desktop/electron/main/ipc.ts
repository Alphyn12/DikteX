import { app, ipcMain, type BrowserWindow } from 'electron'
import type { EngineSupervisor } from './engine'
import type { Locale } from '@shared/ipc'

interface IpcDeps {
  engine: EngineSupervisor
  getMainWindow: () => BrowserWindow
}

/** Şimdilik bellekte; Faz 1.7'de kalıcı ayar deposuna taşınacak. */
let locale: Locale = 'tr'

export function registerIpc({ engine, getMainWindow }: IpcDeps): void {
  ipcMain.handle('window:minimize', () => {
    getMainWindow().minimize()
  })

  ipcMain.handle('window:toggle-maximize', () => {
    const window = getMainWindow()
    if (window.isMaximized()) window.unmaximize()
    else window.maximize()
    return window.isMaximized()
  })

  ipcMain.handle('window:close', () => {
    getMainWindow().close()
  })

  ipcMain.handle('window:is-maximized', () => getMainWindow().isMaximized())

  ipcMain.handle('engine:get-state', () => engine.getState())
  ipcMain.handle('engine:restart', () => engine.restart())

  ipcMain.handle('app:get-version', () => app.getVersion())
  ipcMain.handle('app:get-locale', () => locale)

  ipcMain.handle('app:set-locale', (_event, next: Locale) => {
    if (next !== 'tr' && next !== 'en') return
    locale = next
    const window = getMainWindow()
    if (!window.isDestroyed()) window.webContents.send('app:locale-changed', locale)
  })

  // Pencere düğmesinin simgesi büyütme durumuna göre değişir; kullanıcı
  // pencereyi kenardan sürükleyerek de büyütebileceği için olayı dinliyoruz.
  const window = getMainWindow()
  const notify = (maximized: boolean): void => {
    if (!window.isDestroyed()) window.webContents.send('window:maximize-changed', maximized)
  }
  window.on('maximize', () => notify(true))
  window.on('unmaximize', () => notify(false))
}
