import type { CSSProperties } from 'react'
import type { EngineStatus, Locale } from '@shared/ipc'
import { TitleBar } from './components/TitleBar'
import { I18nProvider, useI18n } from './i18n/useI18n'
import { useEngine } from './hooks/useEngine'
import type { MessageKey } from './i18n/tr'
import styles from './App.module.css'

/**
 * Faz 0 kabuğu.
 *
 * Amacı iki süreçli mimarinin ayakta olduğunu görünür kılmak: pencere Mica ile
 * açılıyor, kendi başlık çubuğunu çiziyor, Python motoruyla el sıkışıyor ve
 * dil değişimi çalışıyor. Faz 1'de gövde, mockup'taki Panel ekranıyla değişecek.
 */

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

export function App(): React.JSX.Element {
  return (
    <I18nProvider>
      <Shell />
    </I18nProvider>
  )
}

function Shell(): React.JSX.Element {
  return (
    <div className={`${styles.shell} ambient-light`}>
      <TitleBar />
      <div className={styles.body}>
        <EngineCard />
      </div>
    </div>
  )
}

function EngineCard(): React.JSX.Element {
  const { t, locale, setLocale } = useI18n()
  const { state, restart } = useEngine()

  const pending = state.status === 'starting' || state.status === 'disconnected'

  return (
    <section
      className={styles.card}
      style={{ '--status-color': STATUS_COLOR[state.status] } as CSSProperties}
      aria-live="polite"
    >
      <div className={styles.label}>OMNIVOICE ENGINE</div>

      <div className={styles.headline}>
        <span className={`${styles.dot} ${pending ? styles.pulsing : ''}`} />
        <span className={styles.status}>{t(STATUS_MESSAGE[state.status])}</span>
      </div>

      <div className={`${styles.meta} tabular`}>
        <span>
          {t('engine.port')} {state.port}
        </span>
        {state.version && (
          <span>
            {t('engine.version')} {state.version}
          </span>
        )}
        {state.retries > 0 && state.status !== 'connected' && (
          <span>
            {t('engine.retrying')} {state.retries}/5
          </span>
        )}
      </div>

      {state.error && <p className={`${styles.error} selectable`}>{state.error}</p>}

      <div className={styles.actions}>
        {state.status !== 'connected' && (
          <button type="button" className={styles.button} onClick={restart}>
            {t('engine.retry')}
          </button>
        )}
        <div className={styles.spacer} />
        <LocaleSwitch locale={locale} onChange={setLocale} />
      </div>
    </section>
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
          className={`${styles.lang} ${locale === code ? styles.langActive : ''}`}
          aria-pressed={locale === code}
          onClick={() => onChange(code)}
        >
          {code}
        </button>
      ))}
    </div>
  )
}
