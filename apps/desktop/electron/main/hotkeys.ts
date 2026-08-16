import { globalShortcut } from 'electron'
import type { DictationController } from './dictation'

/**
 * Global kısayollar (Faz 2.2).
 *
 * `Ctrl+Alt+Space` bas-bırak değil, **aç-kapa** çalışır: bir kez basınca kayıt
 * başlar, ikinci kez basınca biter.
 *
 * Neden bas-basılı-tut değil: Electron'un `globalShortcut` API'si yalnız tuşa
 * basma anını bildirir, bırakma anını bildirmez. Basılı tutma davranışı düşük
 * seviyeli bir klavye kancası (`WH_KEYBOARD_LL`) gerektirir. O kanca zaten
 * Faz 3.5'teki chorded shortcut'lar için kurulacak; bas-basılı-tut da o zaman
 * gelecek. Aç-kapa modeli bu fazda hem güvenilir hem de uzun diktede parmağı
 * yormuyor.
 */

export interface HotkeyBinding {
  accelerator: string
  description: string
  handler: () => void
}

export function registerHotkeys(dictation: DictationController): HotkeyBinding[] {
  const bindings: HotkeyBinding[] = [
    {
      accelerator: 'Control+Alt+Space',
      description: 'Dikte başlat / bitir',
      handler: () => dictation.toggle(),
    },
    {
      accelerator: 'Control+Alt+Escape',
      description: 'Dikteyi iptal et',
      handler: () => dictation.cancel(),
    },
  ]

  for (const binding of bindings) {
    // Kısayol başka bir uygulama tarafından kapılmış olabilir; bu ölümcül
    // değil ama sessizce geçilmemeli — kullanıcı neden çalışmadığını bilmeli.
    const registered = globalShortcut.register(binding.accelerator, binding.handler)
    if (!registered) {
      console.warn(
        `[kısayol] ${binding.accelerator} kaydedilemedi — başka bir uygulama kullanıyor olabilir`,
      )
    }
  }

  return bindings
}

export function unregisterHotkeys(): void {
  globalShortcut.unregisterAll()
}
