/**
 * Türkçe metinler — referans dil.
 *
 * Bu dosya sözlüğün şeklini belirler; diğer diller bundan tip alır, böylece
 * eksik veya fazla anahtar derleme zamanında hata verir.
 */
export const tr = {
  'titlebar.minimize': 'Simge durumuna küçült',
  'titlebar.maximize': 'Ekranı kapla',
  'titlebar.restore': 'Önceki boyut',
  'titlebar.close': 'Kapat',

  'nav.panel': 'Panel',
  'nav.settings': 'Ayarlar',
  'nav.modules': 'MODÜLLER',

  'engine.starting': 'Motor başlatılıyor',
  'engine.connected': 'Motor bağlı',
  'engine.disconnected': 'Motor bağlantısı koptu',
  'engine.failed': 'Motor başlatılamadı',
  'engine.retry': 'Yeniden dene',
  'engine.retrying': 'Yeniden bağlanılıyor…',
  'engine.port': 'port',
  'engine.version': 'sürüm',

  'lang.switch': 'Dil',
} as const

export type MessageKey = keyof typeof tr
export type Messages = Record<MessageKey, string>
