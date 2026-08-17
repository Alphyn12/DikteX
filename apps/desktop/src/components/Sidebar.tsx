import type { AppView } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { MODULES } from '../mock/data'
import { Dot, Pill } from './primitives'
import styles from './Sidebar.module.css'
import { cx } from '../utils/cx'

/**
 * Sol gezinme.
 *
 * Üstte iki gerçek gezinme hedefi (Panel / Ayarlar), altında modül sayaçları.
 * Modül satırları gezinme değil durum göstergesidir — bu yüzden seçim pili
 * almazlar ve daha sönük renktedirler.
 */
export function Sidebar({
  view,
  onNavigate,
  vaultKeyCount,
}: {
  view: AppView
  onNavigate: (view: AppView) => void
  vaultKeyCount: number
}): React.JSX.Element {
  const { t } = useI18n()

  return (
    <nav className={styles.sidebar} aria-label={t('nav.label')}>
      <NavItem label={t('nav.panel')} active={view === 'panel'} onClick={() => onNavigate('panel')} />
      <NavItem
        label={t('nav.history')}
        active={view === 'history'}
        onClick={() => onNavigate('history')}
      />
      <NavItem
        label={t('nav.settings')}
        active={view === 'settings'}
        onClick={() => onNavigate('settings')}
      />

      <div className={styles.gap} />
      <div className={styles.sectionLabel}>{t('nav.modules')}</div>

      {MODULES.map((module) => (
        <button key={module.id} type="button" className={cx(styles.item, styles.module)}>
          <Pill />
          <Dot module={module.id} />
          <span className={styles.moduleLabel}>{t(module.label)}</span>
          {module.count && <span className={cx(styles.count, 'tabular')}>{module.count}</span>}
        </button>
      ))}

      <div className={styles.spacer} />

      <div className={styles.vault}>
        <div className={styles.vaultHead}>
          <Dot module="vault" />
          <span className={styles.vaultTitle}>{t('vault.unlocked')}</span>
        </div>
        <p className={styles.vaultSummary}>{t('vault.summary', { count: vaultKeyCount })}</p>
      </div>
    </nav>
  )
}

function NavItem({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}): React.JSX.Element {
  return (
    <button
      type="button"
      className={cx(styles.item, active ? styles.itemActive : '')}
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
    >
      {/* Seçim pili vurgu rengini taşır; seçili değilken görünmez. */}
      <Pill module={active ? 'prompt' : undefined} />
      <span className={styles.itemLabel}>{label}</span>
    </button>
  )
}
