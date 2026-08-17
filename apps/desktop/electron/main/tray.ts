import { join } from 'node:path'
import { app, Menu, Tray, nativeImage, type BrowserWindow } from 'electron'
import { getLocaleStore } from './locale'
import type { DictationController } from './dictation'

/**
 * Sistem tepsisi ikonu.
 *
 * DikteX bir arka plan uygulamasıdır: global kısayolun her an çalışması
 * gerekir, bu yüzden pencere kapatıldığında uygulama sonlanmaz, tepsiye
 * çekilir. Gerçek çıkış yalnız tepsi menüsünden yapılır.
 */
export function createTray(
  getWindow: () => BrowserWindow,
  dictation: DictationController,
): Tray {
  const iconPath = app.isPackaged
    ? join(process.resourcesPath, 'tray.png')
    : join(app.getAppPath(), 'resources', 'tray.png')

  const tray = new Tray(nativeImage.createFromPath(iconPath))
  tray.setToolTip('DikteX')

  const show = (): void => {
    const window = getWindow()
    if (window.isDestroyed()) return
    if (!window.isVisible()) window.show()
    if (window.isMinimized()) window.restore()
    window.focus()
  }

  const rebuildMenu = (): void => {
    const t = getLocaleStore().messages()
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: t.show, click: show },
        {
          label: `${t.startDictation}\tCtrl+Alt+Space`,
          click: () => dictation.toggle(),
        },
        { type: 'separator' },
        { label: t.quit, click: () => app.quit() },
      ]),
    )
  }

  rebuildMenu()
  getLocaleStore().on('change', rebuildMenu)

  tray.on('click', show)

  return tray
}
