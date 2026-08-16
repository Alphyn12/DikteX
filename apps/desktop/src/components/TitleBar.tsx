import { useEffect, useState } from 'react'
import logoUrl from '../assets/logo.png'
import { useI18n } from '../i18n/useI18n'
import styles from './TitleBar.module.css'

/** Segoe Fluent Icons kod noktaları — Windows 11'in kendi pencere simgeleri. */
const ICON = {
  minimize: '',
  maximize: '',
  restore: '',
  close: '',
} as const

export function TitleBar(): React.JSX.Element {
  const { t } = useI18n()
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    void window.omnivoice.invoke('window:is-maximized').then(setMaximized)
    return window.omnivoice.on('window:maximize-changed', setMaximized)
  }, [])

  return (
    <div className={`${styles.bar} drag-region`}>
      <img className={styles.logo} src={logoUrl} alt="" />
      <span className={styles.title}>OmniVoice</span>

      <div className={styles.spacer} />

      <div className={`${styles.buttons} no-drag`}>
        <button
          type="button"
          className={styles.button}
          title={t('titlebar.minimize')}
          aria-label={t('titlebar.minimize')}
          onClick={() => void window.omnivoice.invoke('window:minimize')}
        >
          {ICON.minimize}
        </button>
        <button
          type="button"
          className={styles.button}
          title={maximized ? t('titlebar.restore') : t('titlebar.maximize')}
          aria-label={maximized ? t('titlebar.restore') : t('titlebar.maximize')}
          onClick={() => void window.omnivoice.invoke('window:toggle-maximize')}
        >
          {maximized ? ICON.restore : ICON.maximize}
        </button>
        <button
          type="button"
          className={`${styles.button} ${styles.close}`}
          title={t('titlebar.close')}
          aria-label={t('titlebar.close')}
          onClick={() => void window.omnivoice.invoke('window:close')}
        >
          {ICON.close}
        </button>
      </div>
    </div>
  )
}
