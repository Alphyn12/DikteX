import { useState } from 'react'
import type { ModeInfo } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { VAULT_KEYS, type ModuleId } from '../mock/data'
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
import { MicrophonePicker } from '../components/MicrophonePicker'
import { AppModeCard } from '../components/AppModeCard'
import { ModelPicker } from '../components/ModelPicker'
import { usePrivacy } from '../hooks/useModes'
import { usePushToTalk } from '../hooks/usePushToTalk'
import { SnippetEditor } from '../components/SnippetEditor'
import { VocabularyEditor } from '../components/VocabularyEditor'
import { useModes } from '../hooks/useModes'
import { useDictation } from '../hooks/useDictation'
import { cx } from '../utils/cx'
import type { MessageKey } from '../i18n/tr'
import styles from './Settings.module.css'

/**
 * Ayarlar ekranı — mockup 1a (Ayarlar görünümü).
 *
 * Mod tablosu artık motordan gelen **gerçek** modları gösteriyor: hangi
 * kısayola bağlı, hangi model kullanılıyor, kısayol çakışıyor mu.
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
          <MicrophonePicker />
          <ModelPicker />
          <AppModeCard />
          <VocabularyEditor />
          <SnippetEditor />
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
  const { modes, error } = useModes()

  if (error) {
    return (
      <div className={styles.table}>
        <p className={styles.tableEmpty}>{error}</p>
      </div>
    )
  }

  return (
    <div className={styles.table} role="table" aria-label={t('settings.title')}>
      <div className={cx(styles.row, styles.headRow)} role="row">
        <span role="columnheader">{t('table.mode')}</span>
        <span role="columnheader">{t('table.model')}</span>
        <span role="columnheader">{t('table.provider')}</span>
        <span role="columnheader">{t('table.shortcut')}</span>
        <span role="columnheader" className={styles.alignEnd}>
          {t('table.active')}
        </span>
      </div>

      {(modes?.modes ?? []).map((mode) => (
        <ModeTableRow
          key={mode.id}
          mode={mode}
          defaultModel={modes?.defaultModel ?? ''}
        />
      ))}

      {modes && modes.modes.length === 0 && (
        <p className={styles.tableEmpty}>—</p>
      )}
    </div>
  )
}

function ModeTableRow({
  mode,
  defaultModel,
}: {
  mode: ModeInfo
  defaultModel: string
}): React.JSX.Element {
  const { t } = useI18n()
  const { toggle } = useDictation()
  const label = t(`mode.${mode.id}` as MessageKey)
  const model = mode.model ?? defaultModel

  return (
    <div className={cx(styles.row, styles.bodyRow)} role="row">
      <span className={styles.mode} role="cell">
        <Dot module={mode.module as ModuleId} />
        <span className={styles.modeText}>
          <span className={styles.truncate}>{label}</span>
          <span className={styles.modeDesc}>{t(`mode.${mode.id}.desc` as MessageKey)}</span>
        </span>
      </span>

      <span className={cx(styles.model, styles.truncate)} role="cell" title={model}>
        {model}
      </span>

      <span className={styles.provider} role="cell">
        <span className={styles.truncate}>{t('provider.openrouter')}</span>
      </span>

      <span className={styles.shortcutCell} role="cell">
        {mode.accelerator ? (
          <Key>{mode.accelerator.replace(/Control/g, 'Ctrl').replace(/\+/g, '+')}</Key>
        ) : (
          <span className={styles.noShortcut}>—</span>
        )}
        {/*
          Kısayol başka bir uygulama tarafından kapılmışsa kullanıcı bunu
          bilmeli; yoksa uygulamayı bozuk sanar.
        */}
        {mode.conflicted && (
          <Badge module="automation" variant="tone">
            {t('table.shortcutConflict')}
          </Badge>
        )}
      </span>

      <span className={styles.toggleCell} role="cell">
        <button
          type="button"
          className={styles.runButton}
          onClick={() => toggle(mode.id)}
          title={label}
        >
          ▶
        </button>
      </span>
    </div>
  )
}

// ── Anahtar satırları ──────────────────────────────────────────────────────

function Switches(): React.JSX.Element {
  const { t } = useI18n()
  const [dynamicModel, setDynamicModel] = useState(true)
  const [preflight, setPreflight] = useState(true)
  // PII anahtarı artık motordaki gerçek bayrağa bağlı. Diğer ikisi hâlâ
  // yerel durum — karşılıkları henüz yok (3.15 ve mod başına pre-flight).
  const { privacy, setMasking, setAutoStop } = usePrivacy()
  const ptt = usePushToTalk()

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
      {/*
        Otomatik durdurma varsayılan olarak AÇIK. Eşiği koda gömmek yerine
        kapatılabilir yaptık: doğru değeri ancak konuşan kişi bilir ve yanlış
        eşik kaydı yarıda keser.
      */}
      <SwitchRow
        title={t('toggle.autoStop')}
        description={t('toggle.autoStop.desc')}
        meta={t('toggle.autoStop.meta', {
          seconds: privacy?.autoStopSeconds ?? 1.6,
        })}
        module="audio"
        on={(privacy?.autoStopSeconds ?? 0) > 0}
        onChange={(next) => void setAutoStop(next ? 1.6 : 0)}
      />
      {/*
        Basılı tut varsayılan olarak KAPALI ve öyle kalmalı: kip sistemdeki
        her tuşu gören bir kanca kuruyor. Ne yaptığı ve ne yapmadığı
        anahtarın hemen altında yazıyor — bunu gizlemek savunulamazdı.
      */}
      <SwitchRow
        title={t('toggle.ptt')}
        description={t('toggle.ptt.desc')}
        meta={t('toggle.ptt.meta')}
        module="prompt"
        on={ptt.state?.enabled ?? false}
        onChange={(next) => void ptt.setEnabled(next)}
      />
      {ptt.failed && <p className={styles.privacyLimit}>{t('toggle.ptt.failed')}</p>}
      {ptt.state?.enabled && (
        <p className={styles.privacyLimit}>{t('toggle.ptt.privacy')}</p>
      )}
      <SwitchRow
        title={t('toggle.pii')}
        description={t('toggle.pii.desc')}
        module="vault"
        badge={t('toggle.pii.badge')}
        on={privacy?.maskPii ?? true}
        onChange={(next) => void setMasking(next)}
      />
      {/*
        Maskelemenin sınırı burada yazıyor. Bunu gizlemek kullanıcıya
        korunduğundan fazlasını vaat etmek olurdu: ses kaydı konuşma tanıma
        sağlayıcısına maskelenmeden gidiyor.
      */}
      {privacy && !privacy.sttCovered && (
        <p className={styles.privacyLimit}>{t('toggle.pii.limit')}</p>
      )}
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
  const { modes } = useModes()
  const bound = (modes?.modes ?? []).filter((m) => m.accelerator && !m.conflicted)

  return (
    <Card>
      <CardLabel>{t('aside.chorded')}</CardLabel>
      <div className={styles.chord}>
        <KeyCap>Ctrl</KeyCap>
        <span className={styles.chordJoin}>+</span>
        <KeyCap>Alt</KeyCap>
        <span className={styles.chordJoin}>+</span>
        <KeyCap accent>Space</KeyCap>
      </div>
      <p className={styles.chordDesc}>{t('aside.chorded.desc')}</p>

      <div className={styles.chordList}>
        {(modes?.modes ?? [])
          .filter((mode) => mode.chordKey && mode.chordKey !== 'Space')
          .map((mode) => (
            <div key={mode.id} className={styles.chordRow}>
              <KeyCap>{mode.chordKey}</KeyCap>
              <span className={styles.chordLabel}>{t(`mode.${mode.id}` as MessageKey)}</span>
            </div>
          ))}
      </div>

      <div className={styles.chordStatus}>
        {t('aside.chorded.status', { count: bound.length })}
      </div>
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
