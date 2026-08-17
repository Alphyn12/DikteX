import { useState } from 'react'
import { useI18n } from '../i18n/useI18n'
import { useQueue } from '../hooks/useModes'
import { Card, CardLabel } from './primitives'
import styles from './QueueCard.module.css'

/**
 * Gönderilemeyen kayıtlar (Faz 7.2).
 *
 * Kart **yalnız kuyrukta bir şey varken** görünüyor: boşken yer kaplaması,
 * kullanıcıya olmayan bir sorunu hatırlatmak olurdu.
 *
 * Sesin diskte durduğunu söyleyen not kalıcı. Uygulamanın geri kalanı sesi
 * diske yazmıyor ve bunu kullanıcıya söylüyor; buradaki istisnayı gizlemek
 * o sözü sessizce bozmak olurdu.
 */
export function QueueCard(): React.JSX.Element | null {
  const { t, formatNumber } = useI18n()
  const { queue, error, busy, flush, remove, clear } = useQueue()
  const [lastResult, setLastResult] = useState<string | null>(null)

  const items = queue?.items ?? []
  if (items.length === 0) return null

  const onFlush = async (): Promise<void> => {
    const result = await flush()
    if (!result) return
    setLastResult(
      t('queue.flushResult', {
        sent: result.sent,
        failed: result.failed,
        dropped: result.dropped,
      }),
    )
  }

  return (
    <Card module="automation">
      <div className={styles.head}>
        <CardLabel>{t('queue.title')}</CardLabel>
        <span className={styles.count}>{t('queue.count', { count: items.length })}</span>
      </div>

      <div className={styles.list}>
        {items.map((item) => (
          <div key={item.id} className={styles.item}>
            <div className={styles.itemMain}>
              <div className={styles.itemTop}>
                {t(`mode.${item.mode}` as never)}
                <span className={styles.attempts}>
                  {formatNumber(item.durationSeconds, { maximumFractionDigits: 1 })}
                  {t('unit.seconds')}
                  {item.attempts > 0 && ` · ${t('queue.attempts', { count: item.attempts })}`}
                </span>
              </div>
              <p className={styles.itemError} title={item.error}>
                {item.error}
              </p>
            </div>
            <button
              type="button"
              className={styles.remove}
              onClick={() => void remove(item.id)}
              aria-label={t('queue.remove')}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primary}
          onClick={() => void onFlush()}
          disabled={busy}
        >
          {busy ? t('queue.sending') : t('queue.retry')}
        </button>
        <button
          type="button"
          className={styles.secondary}
          onClick={() => void clear()}
          disabled={busy}
        >
          {t('queue.clear')}
        </button>
      </div>

      {lastResult && <p className={styles.error}>{lastResult}</p>}
      {error && <p className={styles.error}>{error}</p>}

      <p className={styles.privacyNote}>{t('queue.privacyNote')}</p>
    </Card>
  )
}
