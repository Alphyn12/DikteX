import { useEffect, useState, type CSSProperties } from 'react'
import type { AppView, EngineStatus, Locale } from '@shared/ipc'
import { TitleBar } from './components/TitleBar'
import { Sidebar } from './components/Sidebar'
import { Panel } from './screens/Panel'
import { History } from './screens/History'
import { Settings } from './screens/Settings'
import { I18nProvider, useI18n } from './i18n/useI18n'
import { useEngine } from './hooks/useEngine'
import { useDeviceWatcher } from './hooks/useDeviceWatcher'
import { useVault } from './hooks/useVault'
import type { MessageKey } from './i18n/tr'
import styles from './App.module.css'
import { cx } from './utils/cx'

export function App(): React.JSX.Element {
  return (
    <I18nProvider>
      <Shell />
    </I18nProvider>
  )
}

function Shell(): React.JSX.Element {
  const [view, setView] = useState<AppView>('panel')
  // Sesli aramadan gelen sorgu (Faz 7.13). Geçmiş ekranına aktarılıyor ve
  // sayaçla birlikte taşınıyor: aynı sorgu iki kez söylenirse ekran yine
  // güncellensin.
  const [voiceQuery, setVoiceQuery] = useState<{ text: string; seq: number } | null>(
    null,
  )

  useEffect(() => {
    return window.omnivoice.on('history:query', (query) => {
      setVoiceQuery((current) => ({ text: query, seq: (current?.seq ?? 0) + 1 }))
      setView('history')
    })
  }, [])
  // Kulaklık takılıp çıkarıldığında motorun haberi olsun (Faz 7.6).
  // Ana pencerede dinleniyor: HUD kısa ömürlü ve kapalıyken de olayı
  // yakalamamız gerekiyor.
  useDeviceWatcher()
  // Sayaç mockup listesinden geliyordu ve kullanıcının gerçek kasasıyla
  // ilgisi yoktu; artık motordan okunuyor.
  const { configuredCount: configuredKeys } = useVault()

  return (
    <div className={styles.shell}>
      <TitleBar />

      <div className={styles.body}>
        <Sidebar view={view} onNavigate={setView} vaultKeyCount={configuredKeys} />
        <main className={styles.content}>
          {view === 'panel' && <Panel onNavigate={setView} />}
          {view === 'history' && <History voiceQuery={voiceQuery} />}
          {view === 'settings' && <Settings />}
        </main>
      </div>

      <StatusBar />
    </div>
  )
}

// ── Alt durum çubuğu ───────────────────────────────────────────────────────

const STATUS_COLOR: Record<EngineStatus, string> = {
  starting: 'var(--mod-automation)',
  connected: 'var(--mod-vault)',
  disconnected: 'var(--mod-automation)',
  failed: 'var(--danger)',
}

const STATUS_MESSAGE: Record<EngineStatus, MessageKey> = {
  starting: 'engine.starting',
  connected: 'engine.connected',
  disconnected: 'engine.disconnected',
  failed: 'engine.failed',
}

/**
 * Motorun canlı durumu her ekranda görünür kalır.
 *
 * Faz 0'daki büyük durum kartının yerini aldı: motor sağlıklıyken tek satırlık
 * sessiz bir gösterge, sorun çıktığında hatayı ve yeniden deneme düğmesini
 * gösteren bir uyarı olur.
 */
function StatusBar(): React.JSX.Element {
  const { t, locale, setLocale } = useI18n()
  const { state, restart } = useEngine()

  const pending = state.status === 'starting' || state.status === 'disconnected'
  const healthy = state.status === 'connected'

  return (
    <footer
      className={styles.statusBar}
      style={{ '--status-color': STATUS_COLOR[state.status] } as CSSProperties}
      aria-live="polite"
    >
      <span className={styles.statusItem}>
        <span className={cx(styles.statusDot, pending ? styles.pulsing : '')} />
        {t(STATUS_MESSAGE[state.status])}
      </span>

      {healthy && (
        <span className={cx(styles.statusItem, 'tabular')}>
          {t('engine.port')} {state.port}
        </span>
      )}

      {!healthy && state.retries > 0 && (
        <span className={cx(styles.statusItem, 'tabular')}>
          {t('engine.retrying')} {state.retries}/5
        </span>
      )}

      {!healthy && state.error && (
        <span className={styles.statusError} title={state.error}>
          {state.error.split('\n')[0]}
        </span>
      )}

      {!healthy && (
        <button type="button" className={styles.statusButton} onClick={restart}>
          {t('engine.retry')}
        </button>
      )}

      <span className={styles.statusSpacer} />

      <LocaleSwitch locale={locale} onChange={setLocale} />
    </footer>
  )
}

function LocaleSwitch({
  locale,
  onChange,
}: {
  locale: Locale
  onChange: (locale: Locale) => void
}): React.JSX.Element {
  const { t } = useI18n()
  return (
    <div className={styles.langGroup} role="group" aria-label={t('lang.switch')}>
      {(['tr', 'en'] as const).map((code) => (
        <button
          key={code}
          type="button"
          className={cx(styles.lang, locale === code ? styles.langActive : '')}
          aria-pressed={locale === code}
          onClick={() => onChange(code)}
        >
          {code}
        </button>
      ))}
    </div>
  )
}
