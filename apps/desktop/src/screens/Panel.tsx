import type { EngineStats } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { getContent, type ModuleId } from '../mock/data'
import { Badge, Card, CardLabel, Sparkline, Waveform, tone } from '../components/primitives'
import { useDictation } from '../hooks/useDictation'
import { useEngineData, type HistoryItem } from '../hooks/useEngineData'
import { cx } from '../utils/cx'
import styles from './Panel.module.css'

/**
 * Panel ekranı — mockup 1a.
 *
 * İstatistikler, harcama ve dikte akışı motordan gelen **gerçek** veridir.
 * Sağ sütundaki action items / not defteri / sözlük kartları hâlâ örnek
 * veriyle çalışıyor; onların kaynağı Faz 4 ve Faz 6'da bağlanacak.
 */
export function Panel(): React.JSX.Element {
  const { t, locale, formatDate } = useI18n()
  const content = getContent(locale)
  const { stats, history, error } = useEngineData()

  const today = formatDate(new Date(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    weekday: 'long',
  })

  const dictations = stats?.today.dictations ?? 0
  const apps = stats?.today.apps ?? 0

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{t('panel.title')}</h1>
          <p className={styles.subtitle}>
            {today} ·{' '}
            {t('panel.subtitle', { dictations, apps, meetings: content.meetingCount })}
          </p>
        </div>

        <div className={styles.headerActions}>
          <StartButton />
          <button type="button" className={styles.secondaryButton}>
            {t('panel.recordMeeting')}
          </button>
        </div>
      </header>

      <div className={styles.body}>
        <div className={styles.main}>
          <Stats stats={stats} />
          <EngineStrip stats={stats} />
          <Feed items={history} error={error} />
        </div>

        <aside className={styles.aside}>
          <div className={styles.asideScroll}>
            <SpendCard stats={stats} />
            <ActionItems items={content.actionItems} source={content.actionItemsSource} />
            <Scratchpad notes={content.scratchpad} />
            <Vocabulary terms={content.vocabulary} extra={content.vocabularyExtra} />
          </div>
        </aside>
      </div>
    </div>
  )
}

// ── Dikte başlat ───────────────────────────────────────────────────────────

function StartButton(): React.JSX.Element {
  const { t } = useI18n()
  const { state, toggle } = useDictation()
  const active = state.status !== 'idle'

  return (
    <button
      type="button"
      className={styles.primaryButton}
      // Doğrudan `toggle` geçmek fare olayını mod parametresi olarak
      // gönderirdi; sarmalayıcı bunu engelliyor.
      onClick={() => toggle()}
      aria-pressed={active}
    >
      {active ? t('panel.stopDictation') : t('panel.startDictation')}
      <span className={styles.primaryShortcut}>Ctrl+Alt+Space</span>
    </button>
  )
}

// ── İstatistikler ──────────────────────────────────────────────────────────

/** Her istatistik kartının hangi modül rengini taşıdığı. */
const STAT_TONES: ModuleId[] = ['audio', 'prompt', 'automation', 'system']

function Stats({ stats }: { stats: EngineStats | null }): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const today = stats?.today

  // Kelime sayısı henüz ayrı tutulmuyor; final metinlerin uzunluğundan
  // türetmek yanıltıcı olurdu, bu yüzden dikte sayısını gösteriyoruz.
  const cards = [
    {
      label: 'stat.dictations' as const,
      unit: 'stat.dictations.unit' as const,
      value: today?.dictations ?? 0,
    },
    {
      label: 'stat.audio' as const,
      unit: 'stat.audio.unit' as const,
      value: Math.round(today?.audio_seconds ?? 0),
    },
    {
      label: 'stat.fillers' as const,
      unit: 'stat.fillers.unit' as const,
      value: today?.fillers ?? 0,
    },
    {
      label: 'stat.latency' as const,
      unit: 'stat.latency.unit' as const,
      value: Math.round(today?.avg_ms ?? 0),
    },
  ]

  return (
    <div className={styles.stats}>
      {cards.map((card, index) => {
        const module = STAT_TONES[index] ?? 'audio'
        return (
          <Card key={card.label} module={module} className={styles.stat}>
            <CardLabel>{t(card.label)}</CardLabel>
            <div className={styles.statValue}>
              <span className={cx(styles.statNumber, 'tabular')}>
                {formatNumber(card.value)}
              </span>
              <span className={styles.statUnit}>{t(card.unit)}</span>
            </div>
            {/*
              Sparkline günlük dağılımı gösterecek; o veri henüz toplanmıyor.
              Uydurma bir eğri çizmektense boş bir şerit bırakıyoruz.
            */}
            <Sparkline values={[]} module={module} />
          </Card>
        )
      })}
    </div>
  )
}

// ── Motor durum şeridi ─────────────────────────────────────────────────────

function EngineStrip({ stats }: { stats: EngineStats | null }): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const { state } = useDictation()
  const avgMs = Math.round(stats?.today.avg_ms ?? 0)

  return (
    <div className={styles.engineStrip}>
      <Waveform bars={22} seed={3} module="audio" variant="panel" height={28} />
      <div className={styles.engineText}>
        <div className={styles.engineTitle}>
          {state.status === 'idle' ? t('engineStrip.ready') : t(`hud.${state.status}` as never)}
        </div>
        <div className={styles.engineDetail}>{t('engineStrip.detail')}</div>
      </div>
      <div className={styles.engineMetric}>
        {/*
          Mockup'ta sabit "180 ms" yazıyordu — o bir yerel GPU rakamıydı.
          Burada gösterilen, bugünkü diktelerin gerçek ortalama süresi.
        */}
        <div className={cx(styles.engineLatency, 'tabular')}>
          {avgMs > 0 ? `${formatNumber(avgMs)} ms` : '—'}
        </div>
        <div className={styles.engineNote}>{t('engineStrip.note')}</div>
      </div>
    </div>
  )
}

// ── Dikte akışı ────────────────────────────────────────────────────────────

function Feed({
  items,
  error,
}: {
  items: HistoryItem[]
  error: string | null
}): React.JSX.Element {
  const { t, formatNumber } = useI18n()

  return (
    <section className={styles.feed}>
      <div className={styles.feedHeader}>
        <h2 className={styles.feedTitle}>{t('feed.title')}</h2>
        <span className={styles.rule} />
        <span className={styles.feedAll}>{t('feed.viewAll')}</span>
      </div>

      <div className={styles.feedList}>
        {error && <p className={styles.feedEmpty}>{error}</p>}

        {!error && items.length === 0 && (
          <p className={styles.feedEmpty}>{t('feed.empty')}</p>
        )}

        {items.map((item) => (
          <article key={item.id} className={styles.feedItem} style={tone('audio')}>
            <div className={styles.feedMain}>
              <div className={styles.feedTags}>
                <span className={styles.feedApp}>{item.app_name ?? '—'}</span>
                {item.fillers_removed > 0 && (
                  <Badge module="automation" variant="tone">
                    {t('hud.fillersRemoved', { count: item.fillers_removed })}
                  </Badge>
                )}
                {item.language && <Badge variant="neutral">{item.language}</Badge>}
                {item.pasted === 1 && <Badge variant="neutral">{t('feed.pasted')}</Badge>}
              </div>
              <p className={cx(styles.feedBody, 'selectable')}>{item.final_text}</p>
            </div>
            <div className={cx(styles.feedMeta, 'tabular')}>
              {formatTime(item.created_at)}
              <br />
              {formatNumber(item.total_ms)} ms
              {item.cost_usd > 0 && (
                <>
                  <br />${item.cost_usd.toFixed(5)}
                </>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

// ── Harcama ────────────────────────────────────────────────────────────────

function SpendCard({ stats }: { stats: EngineStats | null }): React.JSX.Element {
  const { t } = useI18n()
  const spend = stats?.spend

  const month = spend?.monthUsd ?? 0
  const budget = spend?.budgetUsd ?? 0
  const ratio = budget > 0 ? Math.min(1, month / budget) : 0

  return (
    <Card module="vault">
      <CardLabel>{t('spend.title')}</CardLabel>

      <div className={styles.spendRow}>
        <span className={styles.spendLabel}>{t('spend.today')}</span>
        <span className={cx(styles.spendValue, 'tabular')}>
          ${(spend?.todayUsd ?? 0).toFixed(4)}
        </span>
      </div>
      <div className={styles.spendRow}>
        <span className={styles.spendLabel}>{t('spend.month')}</span>
        <span className={cx(styles.spendValue, 'tabular')}>${month.toFixed(4)}</span>
      </div>

      {budget > 0 && (
        <>
          <div className={styles.spendBar}>
            <span className={styles.spendFill} style={{ width: `${ratio * 100}%` }} />
          </div>
          <div className={styles.spendFooter}>
            <span>{t('spend.budget')} ${budget.toFixed(2)}</span>
            <span>{t('spend.calls', { count: spend?.callCount ?? 0 })}</span>
          </div>
        </>
      )}
    </Card>
  )
}

// ── Sağ sütun (örnek veri — Faz 4/6'da bağlanacak) ─────────────────────────

function ActionItems({
  items,
  source,
}: {
  items: readonly { id: string; text: string; due: string; done: boolean }[]
  source: string
}): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card module="meeting">
      <div className={styles.asideHead}>
        <CardLabel>{t('aside.actionItems')}</CardLabel>
        <span className={styles.asideSource}>{source}</span>
      </div>
      <div className={styles.list}>
        {items.map((item) => (
          <div key={item.id} className={styles.action}>
            <span
              className={cx(styles.checkbox, item.done && styles.checkboxDone)}
              aria-hidden="true"
            >
              {item.done ? '✓' : ''}
            </span>
            <span className={cx(styles.actionText, item.done && styles.actionTextDone)}>
              {item.text}
              {item.due && <span className={styles.actionOwner}> · {item.due}</span>}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

function Scratchpad({ notes }: { notes: readonly string[] }): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card module="prompt">
      <CardLabel>{t('aside.scratchpad')}</CardLabel>
      <div className={styles.list}>
        {notes.map((note) => (
          <p key={note} className={styles.note}>
            {note}
          </p>
        ))}
      </div>
      <div className={styles.cardFooter}>
        <span className={styles.footerMeta}>{t('aside.rawIdeas', { count: notes.length })}</span>
        <span className={styles.footerAction}>{t('aside.compile')}</span>
      </div>
    </Card>
  )
}

function Vocabulary({
  terms,
  extra,
}: {
  terms: readonly string[]
  extra: number
}): React.JSX.Element {
  const { t } = useI18n()
  return (
    <Card module="audio">
      <CardLabel>{t('aside.vocabulary')}</CardLabel>
      <div className={styles.chips}>
        {terms.map((term) => (
          <span key={term} className={styles.chip} style={tone('audio')}>
            {term}
          </span>
        ))}
        <span className={cx(styles.chip, styles.chipMore)}>+{extra}</span>
      </div>
      <p className={styles.vocabNote}>{t('aside.vocabNote', { count: 4 })}</p>
    </Card>
  )
}

// ── Yardımcı ───────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
