import { EventEmitter } from 'node:events'
import { app } from 'electron'
import type { Locale } from '@shared/ipc'

/**
 * Main process tarafındaki dil durumu.
 *
 * Renderer'ın kendi sözlüğü var; burada yalnız main process'in çizdiği
 * yüzeylerin (tepsi menüsü, sistem menüleri) metinleri tutulur. İki sözlüğü
 * birleştirmek yerine ayrı tutuyoruz: main process'in ihtiyacı bir avuç
 * dizeden ibaret ve renderer paketini buraya taşımanın anlamı yok.
 */

const TRAY_MESSAGES = {
  tr: {
    show: 'DikteX’i göster',
    startDictation: 'Dikte başlat',
    quit: 'Çıkış',
  },
  en: {
    show: 'Show DikteX',
    startDictation: 'Start dictation',
    quit: 'Quit',
  },
} as const satisfies Record<Locale, Record<string, string>>

/**
 * `as const` metin değerlerini birebir tipe kilitler; burada bizi ilgilendiren
 * anahtar kümesi, değerlerin kendisi değil. Bu yüzden değerleri `string`e
 * genişletiyoruz — yoksa İngilizce sözlük Türkçe tipine uymaz.
 */
export type TrayMessages = Record<keyof (typeof TRAY_MESSAGES)['tr'], string>

class LocaleStore extends EventEmitter {
  private current: Locale = 'tr'

  constructor() {
    super()
    // Sistem dili Türkçe değilse İngilizce ile aç; kullanıcı yine de değiştirebilir.
    const system = app.getLocale().toLowerCase()
    this.current = system.startsWith('tr') ? 'tr' : 'en'
  }

  get(): Locale {
    return this.current
  }

  set(next: Locale): void {
    if (next !== 'tr' && next !== 'en') return
    if (next === this.current) return
    this.current = next
    this.emit('change', next)
  }

  messages(): TrayMessages {
    return TRAY_MESSAGES[this.current]
  }
}

let store: LocaleStore | null = null

/** Depoyu döndürür. `app.whenReady()` sonrasında çağrılmalı. */
export function getLocaleStore(): LocaleStore {
  store ??= new LocaleStore()
  return store
}
