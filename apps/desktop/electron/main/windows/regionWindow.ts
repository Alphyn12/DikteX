import { join } from 'node:path'
import { BrowserWindow, screen } from 'electron'
import { loadRenderer } from './mainWindow'

/**
 * Ekran bölgesi seçim kaplaması (Properties V.2).
 *
 * Tüm sanal masaüstünü kaplayan saydam bir pencere. Kullanıcı fareyle bir
 * dikdörtgen çizer, seçim ekran koordinatlarında geri döner.
 *
 * Çoklu ekran: pencere tek tek ekranları değil, hepsini kapsayan **sanal
 * masaüstünü** kaplar. Yalnız birincil ekranı kaplamak, ikinci ekrandaki
 * bir hata penceresini seçmeyi imkânsız kılardı.
 */

export interface SelectedRegion {
  x: number
  y: number
  width: number
  height: number
}

/** Tüm ekranları kapsayan dikdörtgen. */
function virtualBounds(): SelectedRegion {
  const displays = screen.getAllDisplays()
  const left = Math.min(...displays.map((d) => d.bounds.x))
  const top = Math.min(...displays.map((d) => d.bounds.y))
  const right = Math.max(...displays.map((d) => d.bounds.x + d.bounds.width))
  const bottom = Math.max(...displays.map((d) => d.bounds.y + d.bounds.height))
  return { x: left, y: top, width: right - left, height: bottom - top }
}

let overlay: BrowserWindow | null = null
let pending: ((region: SelectedRegion | null) => void) | null = null

/**
 * Kaplamayı açar ve kullanıcının seçtiği bölgeyi döndürür.
 *
 * İptal edilirse (`Esc` veya sağ tık) `null` döner. Zaten bir seçim açıksa
 * yenisi açılmaz — üst üste iki kaplama kullanıcıyı kilitler.
 */
export function selectRegion(): Promise<SelectedRegion | null> {
  if (overlay && !overlay.isDestroyed()) {
    overlay.focus()
    return Promise.resolve(null)
  }

  const bounds = virtualBounds()

  overlay = new BrowserWindow({
    ...bounds,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    hasShadow: false,
    // Kaplama klavye (Esc) alabilmeli, bu yüzden odaklanabilir.
    focusable: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  overlay.setAlwaysOnTop(true, 'screen-saver')
  overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  loadRenderer(overlay, 'region')

  return new Promise<SelectedRegion | null>((resolve) => {
    let settled = false
    const finish = (region: SelectedRegion | null): void => {
      if (settled) return
      settled = true
      pending = null
      if (overlay && !overlay.isDestroyed()) overlay.close()
      overlay = null
      resolve(region)
    }

    pending = finish

    overlay?.once('ready-to-show', () => {
      overlay?.show()
      overlay?.focus()
    })

    // Kullanıcı kaplamayı bir şekilde kapatırsa söz askıda kalmasın.
    overlay?.once('closed', () => finish(null))
  })
}

/** Renderer'dan gelen seçim sonucunu bekleyen söze iletir. */
export function resolveRegion(region: SelectedRegion | null): void {
  // Seçim ekran koordinatlarına çevriliyor: renderer kaplamanın kendi
  // koordinat düzleminde çalışıyor, kaplama ise sanal masaüstünün sol üst
  // köşesinden başlıyor olabilir (negatif koordinatlı ikinci ekran).
  if (region && overlay && !overlay.isDestroyed()) {
    const bounds = overlay.getBounds()
    pending?.({
      x: Math.round(bounds.x + region.x),
      y: Math.round(bounds.y + region.y),
      width: Math.round(region.width),
      height: Math.round(region.height),
    })
    return
  }
  pending?.(region)
}

export function isRegionSelectorOpen(): boolean {
  return overlay !== null && !overlay.isDestroyed()
}
