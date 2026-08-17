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
export function History({
  voiceQuery,
}: {
  /** Sesli aramadan gelen sorgu; `seq` aynı sorgunun tekrarını ayırt eder. */
  voiceQuery?: { text: string; seq: number } | null
} = {}): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const { state: engine } = useEngine()

  const [query, setQuery] = useState('')
  const [items, setItems] = useState<HistoryRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState<number | null>(null)
  // Dışa aktarma ve toplu silme aynı satırda geri bildirim veriyor.
  const [notice, setNotice] = useState<string | null>(null)
  // Silme geri alınamaz; yanlışlıkla tıklamayı önlemek için iki adım.
  // Onay penceresi yerine satır içi: modal, listeyi kaybettirirdi.
  const [confirmId, setConfirmId] = useState<number | null>(null)
  // "Tümünü sil" için ayrı onay: tek kayıt silmekten çok daha yıkıcı.
  const [confirmAll, setConfirmAll] = useState(false)

  const deleteAll = useCallback(async () => {
    try {
      const result = await window.omnivoice.invoke('history:delete-all')
      setItems([])
      setConfirmAll(false)
      // Kaç kaydın gittiğini söylüyoruz: liste zaten boşaldığı için
      // başka türlü işlemin gerçekleştiği anlaşılmazdı.
      setNotice(t('history.deletedAll', { count: result.deleted }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [t])

  const deleteItem = useCallback(
    async (id: number) => {
      try {
        await window.omnivoice.invoke('history:delete', id)
        setItems((current) => current.filter((row) => row.id !== id))
        setConfirmId(null)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    },
    [],
  )

  const exportHistory = useCallback(
    async (format: 'markdown' | 'json') => {
      try {
        const result = await window.omnivoice.invoke('history:export', format)
        // İptal bir hata değil; sessizce geçiyoruz.
        if (result.saved) setNotice(t('history.exported', { count: result.count }))
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    },
    [t],
  )

  const copyItem = useCallback(async (id: number) => {
    try {
      const result = await window.omnivoice.invoke('history:copy', id)
      if (!result.ok) {
        setError(t('history.copyFailed'))
        return
      }
      setCopied(id)
      // Geri bildirim kalıcı olmamalı; kullanıcı başka bir kaydı
      // kopyaladığında eskisi hâlâ "kopyalandı" görünmesin.
      setTimeout(() => setCopied((current) => (current === id ? null : current)), 1600)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [t])

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

  // Sesli sorgu geldiğinde kutuyu dolduruyoruz; arama zaten aşağıdaki
  // debounce etkisiyle tetikleniyor.
  useEffect(() => {
    if (voiceQuery) setQuery(voiceQuery.text)
  }, [voiceQuery])

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

      <div className={styles.exportRow}>
        <span className={styles.exportLabel}>{t('history.export')}</span>
        <button
          type="button"
          className={styles.exportButton}
          onClick={() => void exportHistory('markdown')}
        >
          {t('history.exportMd')}
        </button>
        <button
          type="button"
          className={styles.exportButton}
          onClick={() => void exportHistory('json')}
        >
          {t('history.exportJson')}
        </button>
        {notice && <span className={styles.exportDone}>{notice}</span>}

        <span className={styles.spacer} />

        {/* Dışa aktarmanın yanında duruyor: kullanıcı geçmişi temizlemeden
            önce büyük olasılıkla bir kopyasını almak isteyecek. */}
        {confirmAll ? (
          <>
            <button
              type="button"
              className={styles.deleteConfirm}
              onClick={() => void deleteAll()}
            >
              {t('history.deleteAllConfirm')}
            </button>
            <button
              type="button"
              className={styles.delete}
              onClick={() => setConfirmAll(false)}
            >
              {t('history.cancel')}
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.delete}
            // Süzgeç sonucuna değil, geçmişin kendisine bakıyoruz: arama
            // 0 sonuç verirken düğmeyi kapatmak, dolu bir geçmişi
            // silinemez gösterirdi.
            disabled={items.length === 0 && !query}
            onClick={() => setConfirmAll(true)}
          >
            {t('history.deleteAll')}
          </button>
        )}
      </div>

      {/* Dosyanın ham metin içerdiği söyleniyor: kullanıcı onu başka bir
          yere taşıyacaksa içinde ne olduğunu bilmeli. */}
      <p className={styles.exportNote}>{t('history.exportNote')}</p>

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

            <div className={styles.footer}>
              <div className={cx(styles.stats, 'tabular')}>
                {formatNumber(item.total_ms)} ms
                {item.cost_usd > 0 && ` · $${item.cost_usd.toFixed(5)}`}
                {item.audio_seconds > 0 &&
                  ` · ${formatNumber(item.audio_seconds, { maximumFractionDigits: 1 })}${t('unit.seconds')}`}
              </div>

              {/*
                Yeniden yapıştırma panoya yazıyor, doğrudan bir pencereye
                değil: kullanıcı bu ekranda olduğu için odakta DikteX var
                ve "yapıştır" diyecek bir hedef yok.
              */}
              <div className={styles.rowActions}>
                <button
                  type="button"
                  className={cx(styles.copy, copied === item.id && styles.copied)}
                  onClick={() => void copyItem(item.id)}
                >
                  {copied === item.id ? t('history.copied') : t('history.copy')}
                </button>

                {/*
                  İki adımlı silme: kayıt geri alınamaz şekilde gidiyor ve
                  liste kaydırılırken yanlış satıra tıklamak kolay.
                */}
                {confirmId === item.id ? (
                  <>
                    <button
                      type="button"
                      className={styles.deleteConfirm}
                      onClick={() => void deleteItem(item.id)}
                    >
                      {t('history.deleteConfirm')}
                    </button>
                    <button
                      type="button"
                      className={styles.delete}
                      onClick={() => setConfirmId(null)}
                    >
                      {t('history.cancel')}
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className={styles.delete}
                    onClick={() => setConfirmId(item.id)}
                  >
                    {t('history.delete')}
                  </button>
                )}
              </div>
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
