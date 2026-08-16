import { join } from 'node:path'
import { BrowserWindow, screen } from 'electron'
import type { DictationState, MeetingState } from '@shared/ipc'
import { loadRenderer } from './mainWindow'

/**
 * Canlı dikte HUD'u (mockup 1c).
 *
 * Ekranın alt ortasında, çerçevesiz ve saydam bir pencere. İçerik alta
 * yaslanır, kart yukarı doğru büyür — pencereyi her durum için yeniden
 * boyutlandırmaya gerek kalmaz.
 *
 * Odak davranışı burada kritiktir:
 *   dinliyor / işliyor → odak alınmaz, kullanıcı yazmaya devam edebilir
 *   pre-flight         → odak alınır, çünkü Enter/Esc ve düzenleme gerekiyor
 */

const WIDTH = 560
const HEIGHT = 460
/** Görev çubuğunun üstünde kalması için alt boşluk. */
const BOTTOM_MARGIN = 72

export function createHudWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: WIDTH,
    height: HEIGHT,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    focusable: false,
    alwaysOnTop: true,
    // Gölge saydam pencerede kutunun kenarını gösterir; kartın kendi gölgesi var.
    hasShadow: false,
    webPreferences: {
      // Windows'ta `import.meta.url` yolu "/C:/..." biçiminde üretir ve
      // Electron bunu mutlak yol saymaz; `__dirname` doğru sonucu verir.
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // Tam ekran oyun/sunum üstünde de görünsün.
  window.setAlwaysOnTop(true, 'screen-saver')
  window.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })

  loadRenderer(window, 'hud')
  return window
}

/** HUD'u imlecin bulunduğu ekranın alt ortasına yerleştirir. */
export function positionHud(window: BrowserWindow): void {
  const cursor = screen.getCursorScreenPoint()
  const display = screen.getDisplayNearestPoint(cursor)
  const { x, y, width, height } = display.workArea

  window.setBounds({
    x: Math.round(x + (width - WIDTH) / 2),
    y: Math.round(y + height - HEIGHT - BOTTOM_MARGIN),
    width: WIDTH,
    height: HEIGHT,
  })
}

/**
 * HUD'u dikte durumuna göre gösterir, gizler ve odak davranışını ayarlar.
 */
export function syncHud(window: BrowserWindow, state: DictationState): void {
  // Pre-flight, hata ve sessizlik durumları kullanıcıdan karar bekler;
  // klavyenin HUD'a ulaşması gerekir.
  const needsFocus =
    state.status === 'preflight' || state.status === 'error' || state.status === 'silent'
  applyHudVisibility(window, state.status !== 'idle', needsFocus)
}

/**
 * Toplantı HUD'u. Dikte HUD'uyla aynı pencereyi paylaşır — ikisi aynı anda
 * çalışamadığı için (motor da engelliyor) tek pencere yeterli.
 */
export function syncMeetingHud(window: BrowserWindow, state: MeetingState): void {
  // Sonuç ve hata ekranlarında kullanıcı okuyup karar veriyor.
  const needsFocus = state.status === 'done' || state.status === 'error'
  applyHudVisibility(window, state.status !== 'idle', needsFocus)
}

function applyHudVisibility(
  window: BrowserWindow,
  visible: boolean,
  needsFocus: boolean,
): void {
  if (window.isDestroyed()) return

  if (!visible) {
    if (window.isVisible()) window.hide()
    return
  }

  if (!window.isVisible()) {
    positionHud(window)
    // `showInactive` odağı çalmadan gösterir — kullanıcı konuşurken hâlâ
    // kendi uygulamasında yazıyor olabilir.
    window.showInactive()
  }

  if (needsFocus && !window.isFocused()) {
    window.setFocusable(true)
    window.focus()
  } else if (!needsFocus && window.isFocusable()) {
    window.setFocusable(false)
  }
}
