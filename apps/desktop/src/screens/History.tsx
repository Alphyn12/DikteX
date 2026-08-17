import { useCallback, useEffect, useRef, useState } from 'react'
import type { HistoryRow } from '@shared/ipc'
import { Badge } from '../components/primitives'
import { useI18n } from '../i18n/useI18n'
import { useEngine } from '../hooks/useEngine'
import { cx } from '../utils/cx'
import styles from './History.module.css'

/** Yazma durduktan sonra aramanın beklediği süre. */
const DEBOUNCE_MS = 220

/**
 * Geçmiş araması (Faz 6.2).
 *
 * Arama motor tarafında SQLite FTS5 ile yapılıyor; metin hiçbir zaman
 * buluta çıkmıyor. Türkçe için özel bir katlama var: FTS5 ö/ü/ş/ç/ğ'yi
 * kendisi katlıyor ama **ı** ayrı bir harf ve katlamıyor — ölçtük,
 * "veritabani" araması "veritabanı" kaydını bulamıyordu.
 */
export function History(): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const { state: engine } = useEngine()

  const [query, setQuery] = useState('')
  const [items, setItems] = useState<HistoryRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Her tuş vuruşunda sorgu atmak, SQLite yerel olsa da gereksiz iş.
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const search = useCallback(
    async (text: string) => {
      if (engine.status !== 'connected') return
      setLoading(true)
      try {
        const result = await window.omnivoice.invoke('history:search', text)
        setItems(result.items)
        setError(null)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        setLoading(false)
      }
    },
    [engine.status],
  )

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => void search(query), DEBOUNCE_MS)
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [query, search])

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <span className={styles.eyebrow}>{t('history.eyebrow')}</span>
        <h1 className={styles.title}>{t('history.title')}</h1>
        <p className={styles.subtitle}>{t('history.subtitle')}</p>
      </header>

      <div className={styles.searchRow}>
        <input
          className={cx(styles.search, 'selectable')}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('history.placeholder')}
          aria-label={t('history.search')}
          spellCheck={false}
          autoFocus
        />
        {query && (
          <button
            type="button"
            className={styles.clear}
            onClick={() => setQuery('')}
            aria-label={t('history.clear')}
          >
            ×
          </button>
        )}
      </div>

      <div className={styles.meta}>
        {loading
          ? t('history.searching')
          : t('history.results', { count: items.length })}
      </div>

      <div className={styles.list}>
        {error && <p className={styles.empty}>{error}</p>}

        {!error && items.length === 0 && (
          <p className={styles.empty}>
            {query ? t('history.noMatch') : t('history.empty')}
          </p>
        )}

        {items.map((item) => (
          <article key={item.id} className={styles.item}>
            <div className={styles.itemHead}>
              <span className={styles.app}>{item.app_name ?? '—'}</span>
              <Badge variant="neutral">{t(`mode.${item.mode}` as never)}</Badge>
              {item.language && <Badge variant="neutral">{item.language}</Badge>}
              {item.pasted === 1 && (
                <Badge variant="neutral">{t('feed.pasted')}</Badge>
              )}
              <span className={styles.spacer} />
              <span className={cx(styles.time, 'tabular')}>
                {formatDateTime(item.created_at)}
              </span>
            </div>

            <p className={cx(styles.body, 'selectable')}>{item.final_text}</p>

            {/*
              Ham metin yalnız farklıysa gösteriliyor: aynıysa iki kez aynı
              cümleyi okumak listeyi gereksiz uzatır.
            */}
            {item.raw_text !== item.final_text && (
              <p className={cx(styles.raw, 'selectable')}>{item.raw_text}</p>
            )}

            <div className={cx(styles.stats, 'tabular')}>
              {formatNumber(item.total_ms)} ms
              {item.cost_usd > 0 && ` · $${item.cost_usd.toFixed(5)}`}
              {item.audio_seconds > 0 &&
                ` · ${formatNumber(item.audio_seconds, { maximumFractionDigits: 1 })}${t('unit.seconds')}`}
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
