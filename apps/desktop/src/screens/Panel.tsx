import { useI18n } from '../i18n/useI18n'
import { getContent, STATS, type ActionItem, type FeedItem } from '../mock/data'
import { Badge, Card, CardLabel, Dot, Sparkline, Waveform, tone } from '../components/primitives'
import styles from './Panel.module.css'
import { cx } from '../utils/cx'

/**
 * Panel ekranı — mockup 1a.
 *
 * Faz 1'de örnek veriyle çalışır. Faz 2'de `getContent` yerine motordan gelen
 * gerçek veri bağlanacak; bu dosyadaki yerleşim değişmeyecek.
 */
export function Panel(): React.JSX.Element {
  const { t, locale, formatDate } = useI18n()
  const content = getContent(locale)

  const today = formatDate(new Date(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    weekday: 'long',
  })

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{t('panel.title')}</h1>
          <p className={styles.subtitle}>
            {today} ·{' '}
            {t('panel.subtitle', {
              dictations: 27,
              apps: 4,
              meetings: content.meetingCount,
            })}
          </p>
        </div>

        <div className={styles.headerActions}>
          <button type="button" className={styles.primaryButton}>
            {t('panel.startDictation')}
            <span className={styles.primaryShortcut}>Ctrl+Alt+Space</span>
          </button>
          <button type="button" className={styles.secondaryButton}>
            {t('panel.recordMeeting')}
          </button>
        </div>
      </header>

      <div className={styles.body}>
        <div className={styles.main}>
          <Stats />
          <EngineStrip detail={content.engineDetail} />
          <Feed items={content.feed} />
        </div>

        <aside className={styles.aside}>
          <div className={styles.asideScroll}>
            <ActionItems items={content.actionItems} source={content.actionItemsSource} />
            <Scratchpad notes={content.scratchpad} />
            <Vocabulary terms={content.vocabulary} extra={content.vocabularyExtra} />
          </div>
          <BatteryNotice model={content.batteryModel} />
        </aside>
      </div>
    </div>
  )
}

// ── İstatistikler ──────────────────────────────────────────────────────────

function Stats(): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  return (
    <div className={styles.stats}>
      {STATS.map((stat) => (
        <Card key={stat.label} module={stat.module} className={styles.stat}>
          <CardLabel>{t(stat.label)}</CardLabel>
          <div className={styles.statValue}>
            <span className={cx(styles.statNumber, 'tabular')}>{formatNumber(stat.value)}</span>
            <span className={styles.statUnit}>{t(stat.unit)}</span>
          </div>
          <Sparkline values={stat.spark} module={stat.module} />
        </Card>
      ))}
    </div>
  )
}

// ── Motor durum şeridi ─────────────────────────────────────────────────────

function EngineStrip({ detail }: { detail: string }): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  return (
    <div className={styles.engineStrip}>
      <Waveform bars={22} seed={3} module="audio" variant="panel" height={28} />
      <div className={styles.engineText}>
        <div className={styles.engineTitle}>{t('engineStrip.title')}</div>
        <div className={styles.engineDetail} title={detail}>
          {detail}
        </div>
      </div>
      <div className={styles.engineMetric}>
        {/*
          Mockup'ta burada sabit "180 ms" yazıyordu — o bir yerel GPU rakamıydı.
          Faz 2'de bu alan gerçek ölçülen gecikmeyle dolacak; sahte performans
          sayısı gösterilmiyor.
        */}
        <div className={cx(styles.engineLatency, 'tabular')}>{formatNumber(1240)} ms</div>
        <div className={styles.engineNote}>{t('engineStrip.note')}</div>
      </div>
    </div>
  )
}

// ── Dikte akışı ────────────────────────────────────────────────────────────

function Feed({ items }: { items: readonly FeedItem[] }): React.JSX.Element {
  const { t } = useI18n()
  return (
    <section className={styles.feed}>
      <div className={styles.feedHeader}>
        <h2 className={styles.feedTitle}>{t('feed.title')}</h2>
        <span className={styles.rule} />
        <button type="button" className={styles.feedAll}>
          {t('feed.viewAll')}
        </button>
      </div>

      <div className={styles.feedList}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={styles.feedItem}
            style={tone(item.module)}
          >
            <div className={styles.feedMain}>
              <div className={styles.feedTags}>
                <span className={styles.feedApp}>{item.app}</span>
                <Badge module={item.module} variant="tone">
                  {item.tag}
                </Badge>
                <Badge variant="neutral">{item.tag2}</Badge>
              </div>
              <p className={styles.feedBody}>{item.body}</p>
            </div>
            <div className={cx(styles.feedMeta, 'tabular')}>
              {item.time}
              <br />
              {item.meta}
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}

// ── Sağ sütun ──────────────────────────────────────────────────────────────

function ActionItems({
  items,
  source,
}: {
  items: readonly ActionItem[]
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
          <button key={item.id} type="button" className={styles.action}>
            <span
              className={cx(styles.checkbox, item.done ? styles.checkboxDone : '')}
              aria-hidden="true"
            >
              {item.done ? '✓' : ''}
            </span>
            <span className={cx(styles.actionText, item.done ? styles.actionTextDone : '')}>
              {item.text}
              {item.due && <span className={styles.actionOwner}> · {item.due}</span>}
            </span>
          </button>
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
        <button type="button" className={styles.footerAction}>
          {t('aside.compile')}
        </button>
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

function BatteryNotice({ model }: { model: string }): React.JSX.Element {
  const { t } = useI18n()
  return (
    <div className={styles.notice}>
      <span className={styles.noticeDot}>
        <Dot module="automation" />
      </span>
      <p className={styles.noticeText}>
        {t('aside.batteryNotice', { model })}{' '}
        <button type="button" className={styles.noticeAction}>
          {t('aside.undo')}
        </button>
      </p>
    </div>
  )
}
