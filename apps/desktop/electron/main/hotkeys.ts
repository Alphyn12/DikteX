import { globalShortcut } from 'electron'
import type { DictationController } from './dictation'

/**
 * Global kısayollar (Faz 2.2 · Faz 3.5).
 *
 * ## Neden chord değil, ayrı hızlandırıcılar
 *
 * Mockup "Ctrl+Alt+Space → K" biçiminde bir chord gösteriyor: basılı tut,
 * sonra mod harfine bas. Bunu gerçekten yapmak düşük seviyeli bir klavye
 * kancası (`WH_KEYBOARD_LL`) gerektirir, çünkü Electron'un `globalShortcut`
 * API'si yalnız tuşa basmayı bildirir, bırakmayı bildirmez.
 *
 * O kanca üç bedel getiriyor: antivirüs yazılımları düşük seviyeli klavye
 * kancalarını sık sık keylogger sanıyor, ayrı bir mesaj döngüsü iş parçacığı
 * gerekiyor ve kancanın kendisi tüm sistem klavyesini yavaşlatabiliyor.
 *
 * Ayrı hızlandırıcılar (`Ctrl+Alt+K`, `Ctrl+Alt+E` …) aynı yeteneği —
 * klavyeden mod seçimi — tam olarak ve güvenilir biçimde veriyor. Bedeli daha
 * çok global kısayol kaydetmek; onu da çakışma bildirimiyle görünür kılıyoruz.
 *
 * ## Kayıt başarısız olursa
 *
 * Bir kısayol başka bir uygulama tarafından kapılmış olabilir. Bunu sessizce
 * geçmiyoruz: kullanıcı neden çalışmadığını bilmeli, yoksa uygulamayı bozuk
 * sanar.
 */

/** Modun kimliği ile kısayolu. Motor tarafındaki `ModeId` ile eşleşir. */
export interface ModeBinding {
  mode: string
  accelerator: string
  /** Kayıt başarılı oldu mu? Başarısızsa arayüzde uyarı gösterilir. */
  registered: boolean
}

/**
 * Mod → kısayol eşlemesi.
 *
 * Harfler motor tarafındaki `Mode.chord_key` değerleriyle aynı; mockup'taki
 * "K kod, E İngilizce, M mega-prompt" gösterimi böylece hâlâ doğru okunuyor.
 */
const MODE_ACCELERATORS: ReadonlyArray<{ mode: string; key: string }> = [
  { mode: 'quick', key: 'Space' },
  { mode: 'code', key: 'K' },
  { mode: 'translate_en', key: 'E' },
  { mode: 'mega_prompt', key: 'M' },
  { mode: 'image_prompt', key: 'G' },
  { mode: 'sql', key: 'S' },
  { mode: 'commit', key: 'C' },
  { mode: 'screen', key: 'R' },
]

export interface HotkeyRegistration {
  modes: ModeBinding[]
  /** Kaydedilemeyen kısayollar — arayüzde uyarı olarak gösterilir. */
  conflicts: string[]
}

export function registerHotkeys(dictation: DictationController): HotkeyRegistration {
  const modes: ModeBinding[] = []
  const conflicts: string[] = []

  for (const { mode, key } of MODE_ACCELERATORS) {
    const accelerator = `Control+Alt+${key}`
    const registered = globalShortcut.register(accelerator, () => {
      void dictation.toggle(mode)
    })

    if (!registered) {
      conflicts.push(accelerator)
      console.warn(
        `[kısayol] ${accelerator} kaydedilemedi — başka bir uygulama kullanıyor olabilir`,
      )
    }
    modes.push({ mode, accelerator, registered })
  }

  // İptal her modda aynı.
  const cancelAccelerator = 'Control+Alt+Escape'
  if (!globalShortcut.register(cancelAccelerator, () => dictation.cancel())) {
    conflicts.push(cancelAccelerator)
  }

  return { modes, conflicts }
}

export function unregisterHotkeys(): void {
  globalShortcut.unregisterAll()
}
