import { app, ipcMain, type BrowserWindow } from 'electron'
import type { EngineSupervisor } from './engine'
import type { Locale } from '@shared/ipc'
import { getLocaleStore } from './locale'

interface IpcDeps {
  engine: EngineSupervisor
  getMainWindow: () => BrowserWindow
}

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

  // Kapatma uygulamayı sonlandırmaz, tepsiye çeker — global kısayolun
  // çalışmaya devam etmesi gerekiyor (bkz. tray.ts).
  ipcMain.handle('window:close', () => {
    getMainWindow().hide()
  })

  ipcMain.handle('window:is-maximized', () => getMainWindow().isMaximized())

  ipcMain.handle('engine:get-state', () => engine.getState())
  ipcMain.handle('engine:restart', () => engine.restart())

  ipcMain.handle('app:get-version', () => app.getVersion())
  ipcMain.handle('app:get-locale', () => getLocaleStore().get())

  ipcMain.handle('app:set-locale', (_event, next: Locale) => {
    getLocaleStore().set(next)
  })

  // Dil main process'te de değişebilir (ileride sistem menülerinden);
  // renderer'ı tek bir yerden haberdar ediyoruz.
  getLocaleStore().on('change', (locale: Locale) => {
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
