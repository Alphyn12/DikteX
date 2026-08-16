import { useState } from 'react'
import { useI18n } from '../i18n/useI18n'
import {
  MODE_ROWS,
  PROVIDER_TRAINS_ON_DATA,
  VAULT_KEYS,
  type ModeRow,
  type ProviderId,
} from '../mock/data'
import {
  Badge,
  Card,
  CardLabel,
  Dot,
  Key,
  KeyCap,
  Toggle,
  TrainingBadge,
} from '../components/primitives'
import type { MessageKey } from '../i18n/tr'
import styles from './Settings.module.css'
import { cx } from '../utils/cx'

const PROVIDER_LABEL: Record<ProviderId, MessageKey> = {
  groq: 'provider.groq',
  openrouter: 'provider.openrouter',
  gemini: 'provider.gemini',
  hybrid: 'provider.hybrid',
}

/**
 * Ayarlar ekranı — mockup 1a (Ayarlar görünümü).
 *
 * Anahtarlar Faz 1'de yalnız görsel; durumları bileşen içinde tutuluyor.
 * Faz 2'de kalıcı ayar deposuna bağlanacak.
 */
export function Settings(): React.JSX.Element {
  const { t } = useI18n()

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div className={styles.eyebrow}>{t('settings.eyebrow')}</div>
        <h1 className={styles.title}>{t('settings.title')}</h1>
        <p className={styles.subtitle}>{t('settings.subtitle')}</p>
      </header>

      <div className={styles.body}>
        <div className={styles.main}>
          <ModeTable />
          <Switches />
        </div>

        <aside className={styles.aside}>
          <ChordedShortcut />
          <ApiVault />
          <LocalServer />
        </aside>
      </div>
    </div>
  )
}

// ── Mod / model tablosu ────────────────────────────────────────────────────

function ModeTable(): React.JSX.Element {
  const { t } = useI18n()
  const [active, setActive] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(MODE_ROWS.map((row) => [row.id, row.active])),
  )

  return (
    <div className={styles.table} role="table" aria-label={t('settings.title')}>
      <div className={cx(styles.row, styles.headRow)} role="row">
        <span role="columnheader">{t('table.mode')}</span>
        <span role="columnheader">{t('table.model')}</span>
        <span role="columnheader">{t('table.provider')}</span>
        <span role="columnheader" className={styles.alignEnd}>
          {t('table.latency')}
        </span>
        <span role="columnheader">{t('table.shortcut')}</span>
        <span role="columnheader" className={styles.alignEnd}>
          {t('table.active')}
        </span>
      </div>

      {MODE_ROWS.map((row) => (
        <ModeTableRow
          key={row.id}
          row={row}
          on={active[row.id] ?? false}
          onToggle={(next) => setActive((prev) => ({ ...prev, [row.id]: next }))}
        />
      ))}
    </div>
  )
}

function ModeTableRow({
  row,
  on,
  onToggle,
}: {
  row: ModeRow
  on: boolean
  onToggle: (next: boolean) => void
}): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const modeLabel = t(row.mode)

  // Ondalık ayırıcı da dile göre değişir: 1.1 s / 1,1 sn
  const latencyText =
    row.latency === 'stream'
      ? t('latency.stream')
      : `${formatNumber(row.latency, {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })} ${t('unit.seconds')}`

  const latencyClass =
    row.latencyOk === null
      ? styles.latencyNeutral
      : row.latencyOk
        ? styles.latencyOk
        : styles.latencySlow

  return (
    <div className={cx(styles.row, styles.bodyRow)} role="row">
      <span className={styles.mode} role="cell">
        <Dot module={row.module} />
        <span className={styles.truncate}>{modeLabel}</span>
      </span>

      <span className={cx(styles.model, styles.truncate)} role="cell" title={row.model}>
        {row.model}
      </span>

      <span className={styles.provider} role="cell">
        <span className={styles.truncate}>{t(PROVIDER_LABEL[row.provider])}</span>
        {/*
          Eğitime açık sağlayıcı burada işaretlenir. Kullanıcı bu modu o
          sağlayıcıya alabilir, ama riski görerek alır.
        */}
        {PROVIDER_TRAINS_ON_DATA[row.provider] && (
          <TrainingBadge label={t('training.badge')} tooltip={t('training.tooltip')} />
        )}
      </span>

      <span className={cx(styles.latency, latencyClass, styles.alignEnd, 'tabular')} role="cell">
        {latencyText}
      </span>

      <span className={styles.shortcutCell} role="cell">
        <Key>{row.shortcut}</Key>
      </span>

      <span className={styles.toggleCell} role="cell">
        <Toggle on={on} module={row.module} label={modeLabel} onChange={onToggle} />
      </span>
    </div>
  )
}

// ── Anahtar satırları ──────────────────────────────────────────────────────

function Switches(): React.JSX.Element {
  const { t } = useI18n()
  const [dynamicModel, setDynamicModel] = useState(true)
  const [preflight, setPreflight] = useState(true)
  const [pii, setPii] = useState(true)

  return (
    <div className={styles.switches}>
      <SwitchRow
        title={t('toggle.dynamicModel')}
        description={t('toggle.dynamicModel.desc')}
        meta={t('toggle.dynamicModel.meta')}
        module="audio"
        on={dynamicModel}
        onChange={setDynamicModel}
      />
      <SwitchRow
        title={t('toggle.preflight')}
        description={t('toggle.preflight.desc')}
        meta={t('toggle.preflight.meta')}
        module="prompt"
        on={preflight}
        onChange={setPreflight}
      />
      <SwitchRow
        title={t('toggle.pii')}
        description={t('toggle.pii.desc')}
        module="vault"
        badge={t('toggle.pii.badge')}
        on={pii}
        onChange={setPii}
      />
    </div>
  )
}

function SwitchRow({
  title,
  description,
  meta,
  badge,
  module,
  on,
  onChange,
}: {
  title: string
  description: string
  meta?: string
  badge?: string
  module: 'audio' | 'prompt' | 'vault'
  on: boolean
  onChange: (next: boolean) => void
}): React.JSX.Element {
  return (
    <div className={styles.switchRow}>
      <div className={styles.switchText}>
        <div className={styles.switchTitle}>
          {title}
          {badge && (
            <Badge module={module} variant="filled" softTone="var(--mod-vault-soft)">
              {badge}
            </Badge>
          )}
        </div>
        <p className={styles.switchDesc}>{description}</p>
      </div>
      <div className={styles.switchControl}>
        {meta && <span className={styles.switchMeta}>{meta}</span>}
        <Toggle on={on} module={module} label={title} onChange={onChange} />
      </div>
    </div>
  )
}

// ── Sağ sütun ──────────────────────────────────────────────────────────────

function ChordedShortcut(): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card>
      <CardLabel>{t('aside.chorded')}</CardLabel>
      <div className={styles.chord}>
        <KeyCap>Ctrl</KeyCap>
        <span className={styles.chordJoin}>+</span>
        <KeyCap>Alt</KeyCap>
        <span className={styles.chordJoin}>+</span>
        <KeyCap accent>Space</KeyCap>
        <span className={styles.chordJoin}>→</span>
        <KeyCap>K</KeyCap>
      </div>
      <p className={styles.chordDesc}>
        {t('aside.chorded.desc')}{' '}
        {t('aside.chorded.legend', { k: 'K', e: 'E', m: 'M' })
          .split(/(\bK\b|\bE\b|\bM\b)/)
          .map((part, i) =>
            part === 'K' || part === 'E' || part === 'M' ? (
              <b key={i} className={styles.chordKey}>
                {part}
              </b>
            ) : (
              part
            ),
          )}
      </p>
      <div className={styles.chordStatus}>{t('aside.chorded.status', { count: 6 })}</div>
    </Card>
  )
}

function ApiVault(): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card>
      <CardLabel>{t('aside.apiVault')}</CardLabel>
      <div className={styles.keyList}>
        {VAULT_KEYS.map((key) => (
          <div key={key.id} className={styles.keyRow}>
            {key.masked ? <Dot module="vault" /> : <span className={styles.keyEmptyDot} />}
            <span className={cx(styles.keyName, key.masked ? '' : styles.keyNameEmpty)}>
              {key.name}
            </span>
            {key.trainsOnData && (
              <TrainingBadge label={t('training.badge')} tooltip={t('training.tooltip')} />
            )}
            {key.masked ? (
              <span className={styles.keyMasked}>{key.masked}</span>
            ) : (
              <button type="button" className={styles.keyAdd}>
                {t('aside.addKey')}
              </button>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}

function LocalServer(): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card>
      <CardLabel>{t('aside.localServer')}</CardLabel>
      <div className={styles.serverAddress}>localhost:8756</div>
      <p className={styles.serverDesc}>{t('aside.localServer.desc')}</p>
    </Card>
  )
}
