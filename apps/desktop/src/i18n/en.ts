import type { Messages } from './tr'

/** İngilizce metinler. Şekli `tr` belirler; eksik anahtar derleme hatasıdır. */
export const en: Messages = {
  'titlebar.minimize': 'Minimize',
  'titlebar.maximize': 'Maximize',
  'titlebar.restore': 'Restore',
  'titlebar.close': 'Close',

  'nav.panel': 'Dashboard',
  'nav.settings': 'Settings',
  'nav.modules': 'MODULES',

  'engine.starting': 'Starting engine',
  'engine.connected': 'Engine connected',
  'engine.disconnected': 'Engine disconnected',
  'engine.failed': 'Engine failed to start',
  'engine.retry': 'Retry',
  'engine.retrying': 'Reconnecting…',
  'engine.port': 'port',
  'engine.version': 'version',

  'lang.switch': 'Language',
}
