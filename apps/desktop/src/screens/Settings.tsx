import type { ModeInfo } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useVault } from '../hooks/useVault'
import { type ModuleId } from '../mock/data'
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
import { ReplacementCard } from '../components/ReplacementCard'
import { StyleCard } from '../components/StyleCard'
import { ModelPicker } from '../components/ModelPicker'
import { usePrivacy } from '../hooks/useModes'
import { usePushToTalk } from '../hooks/usePushToTalk'
import { useAutostart } from '../hooks/useAutostart'
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
          <ReplacementCard />
          <SnippetEditor />
          <StyleCard />
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
          <Key>{formatAccelerator(mode.accelerator)}</Key>
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
        {/*
          Yedeğe düşülmüşse kullanıcı bunu bilmeli: Ctrl+Alt+K bekleyip
          Ctrl+Shift+Alt+K'ya düşmüşse ve haberi yoksa kısayolun
          "çalışmadığını" düşünür.
        */}
        {mode.reassignedFrom && (
          <Badge module="system" variant="tone">
            {t('table.shortcutMoved', { from: formatAccelerator(mode.reassignedFrom) })}
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
  // PII anahtarı artık motordaki gerçek bayrağa bağlı. Diğer ikisi hâlâ
  // yerel durum — karşılıkları henüz yok (3.15 ve mod başına pre-flight).
  const {
    privacy,
    setMasking,
    setAutoStop,
    setPreflight,
    normalizeNumbers,
    setNormalizeNumbers,
    sttLanguages,
    setSttLanguages,
  } = usePrivacy()
  const ptt = usePushToTalk()
  const autostart = useAutostart()

  return (
    <div className={styles.switches}>
      <SwitchRow
        title={t('toggle.preflight')}
        description={t('toggle.preflight.desc')}
        meta={t('toggle.preflight.meta')}
        module="prompt"
        on={privacy?.preflight ?? true}
        onChange={(next) => void setPreflight(next)}
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
        title={t('toggle.autostart')}
        description={t('toggle.autostart.desc')}
        meta={
          autostart.state?.supported === false
            ? t('toggle.autostart.dev')
            : t('toggle.autostart.meta')
        }
        module="system"
        on={autostart.state?.enabled ?? false}
        onChange={(next) => void autostart.setEnabled(next)}
      />
      <SwitchRow
        title={t('toggle.numbers')}
        description={t('toggle.numbers.desc')}
        meta={t('toggle.numbers.meta')}
        module="audio"
        on={normalizeNumbers}
        onChange={(next) => void setNormalizeNumbers(next)}
      />
      <LanguageRow selected={sttLanguages} onChange={setSttLanguages} />
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

/** Electron hızlandırıcısını okunur hâle getirir: `Control+Alt+K` → `Ctrl+Alt+K`. */
function formatAccelerator(accelerator: string): string {
  return accelerator.replace(/Control/g, 'Ctrl').replace(/Super/g, 'Win')
}

/** Dikte edilebilecek diller — kod ve gösterilen ad. */
const DIKTE_DILLERI: readonly { kod: string; ad: string }[] = [
  { kod: 'tr', ad: 'Türkçe' },
  { kod: 'en', ad: 'English' },
]

/**
 * Konuştuğunuz diller (Faz 7.17).
 *
 * Anahtar değil, çoklu seçim: kullanıcı gün içinde iki dili de kullanıyor
 * ve birini sabitlemek diğerini bozardı. Ölçülen hata şuydu — Whisper dili
 * kendi tahmin ederken Türkçe konuşmayı **İzlandaca** sandı ve çıktı
 * kullanılamaz hâle geldi.
 *
 * Hiçbiri seçili değilken denetim kapalı: her tespit olduğu gibi kabul
 * ediliyor. Bu bilinçli bir seçenek, kaza değil — açıklaması altında yazıyor.
 */
function LanguageRow({
  selected,
  onChange,
}: {
  selected: string[]
  onChange: (languages: string[]) => Promise<void>
}): React.JSX.Element {
  const { t } = useI18n()

  const topla = (kod: string): string[] =>
    selected.includes(kod) ? selected.filter((x) => x !== kod) : [...selected, kod]

  return (
    <div className={styles.switchRow}>
      <div className={styles.switchText}>
        <div className={styles.switchTitle}>{t('language.title')}</div>
        <p className={styles.switchDesc}>
          {selected.length === 0 ? t('language.off') : t('language.desc')}
        </p>
      </div>
      <div className={styles.switchControl}>
        {DIKTE_DILLERI.map(({ kod, ad }) => (
          <button
            key={kod}
            type="button"
            role="switch"
            aria-checked={selected.includes(kod)}
            aria-label={`${t('language.title')}: ${ad}`}
            className={cx(styles.langChip, selected.includes(kod) && styles.langChipOn)}
            onClick={() => void onChange(topla(kod))}
          >
            {ad}
          </button>
        ))}
      </div>
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
  // Elle yazılmış dar bir birlik yerine paylaşılan tip: yeni bir modül
  // rengi kullanmak istendiğinde burayı da düzenlemek gerekiyordu.
  module: ModuleId
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

/** Sağlayıcının kullanıcıya gösterilen adı. */
const SAGLAYICI_ADI: Record<string, string> = {
  openrouter: 'OpenRouter',
  groq: 'Groq',
  gemini: 'Gemini',
}

/**
 * Sağlayıcının verisi model eğitiminde kullanılıyor mu.
 *
 * Gemini'nin ücretsiz katmanı kullanıyor; OpenRouter üzerinden giden aynı
 * model kullanmıyor. Kullanıcı anahtarı görürken riski de görmeli.
 */
const EGITIME_ACIK = new Set(['gemini'])

/**
 * API kasası — **gerçek** içerik.
 *
 * Bu kart mockup'tan kalma sabit bir listeyi gösteriyordu: kullanıcının hiç
 * sahip olmadığı bir kayıt ("Webhook (Notion)") ve gerçeğine benzeyen ama
 * uydurma maskeler. `vault:list` motorda ve IPC'de baştan beri hazırdı,
 * yalnız buradan çağrılmıyordu.
 */
function ApiVault(): React.JSX.Element {
  const { t } = useI18n()
  const { entries, error } = useVault()

  return (
    <Card>
      <CardLabel>{t('aside.apiVault')}</CardLabel>
      <div className={styles.keyList}>
        {entries.map((entry) => (
          <div key={entry.provider} className={styles.keyRow}>
            {entry.configured ? <Dot module="vault" /> : <span className={styles.keyEmptyDot} />}
            <span
              className={cx(styles.keyName, entry.configured ? '' : styles.keyNameEmpty)}
            >
              {SAGLAYICI_ADI[entry.provider] ?? entry.provider}
            </span>
            {entry.configured && EGITIME_ACIK.has(entry.provider) && (
              <TrainingBadge label={t('training.badge')} tooltip={t('training.tooltip')} />
            )}
            {entry.masked ? (
              <span className={styles.keyMasked}>{entry.masked}</span>
            ) : (
              <span className={styles.keyNameEmpty}>{t('aside.noKey')}</span>
            )}
          </div>
        ))}
        {/* Motor bağlanmadan liste boş; "anahtarınız yok" demek yanlış olurdu. */}
        {entries.length === 0 && !error && (
          <span className={styles.keyNameEmpty}>{t('aside.vaultLoading')}</span>
        )}
        {error && <span className={styles.keyNameEmpty}>{error}</span>}
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
