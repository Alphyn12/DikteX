import { useState } from 'react'
import type { Snippet } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useSnippets } from '../hooks/useModes'
import { Card, CardLabel } from './primitives'
import { cx } from '../utils/cx'
import styles from './SnippetEditor.module.css'

/**
 * Snippet & şablon kütüphanesi (Properties V.3).
 *
 * Kayıtlı bir kalıp, adı konuşma içinde geçince isteme eklenir. Eşleşme
 * bulanık — "kod inceleme" kaydı "kod incelemesi yap" ile de tetiklenir —
 * bu yüzden altta bir **deneme alanı** var: kullanıcı bir cümle yazıp hangi
 * şablonun tutacağını canlı dikteyi beklemeden görebiliyor.
 */
export function SnippetEditor(): React.JSX.Element {
  const { t } = useI18n()
  const { snippets, error, add, remove, test } = useSnippets()

  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const [triggers, setTriggers] = useState('')
  const [busy, setBusy] = useState(false)
  const [duplicate, setDuplicate] = useState(false)

  const [probe, setProbe] = useState('')
  // `undefined` = henüz denenmedi, `null` = denendi ve eşleşme yok.
  const [match, setMatch] = useState<Snippet | null | undefined>(undefined)

  const items = snippets?.snippets ?? []
  const canAdd = name.trim().length > 0 && body.trim().length > 0 && !busy

  const submit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    if (!canAdd) return
    setBusy(true)
    setDuplicate(false)
    try {
      const added = await add(
        name.trim(),
        body.trim(),
        triggers
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      )
      if (added) {
        setName('')
        setBody('')
        setTriggers('')
      } else {
        // Form temizlenmiyor: kullanıcı adı düzeltip yeniden denesin.
        setDuplicate(true)
      }
    } finally {
      setBusy(false)
    }
  }

  const runProbe = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    if (!probe.trim()) return
    setMatch(await test(probe.trim()))
  }

  return (
    <Card module="automation">
      <div className={styles.head}>
        <CardLabel>{t('snippets.title')}</CardLabel>
        <span className={styles.count}>
          {t('snippets.count', { count: items.length })}
        </span>
      </div>

      <form className={styles.form} onSubmit={(event) => void submit(event)}>
        <div className={styles.row}>
          <input
            className={cx(styles.input, 'selectable')}
            value={name}
            onChange={(event) => {
              setName(event.target.value)
              setDuplicate(false)
            }}
            placeholder={t('snippets.namePlaceholder')}
            aria-label={t('snippets.name')}
            spellCheck={false}
          />
          <button type="submit" className={styles.addButton} disabled={!canAdd}>
            +
          </button>
        </div>
        <textarea
          className={cx(styles.body, 'selectable')}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder={t('snippets.bodyPlaceholder')}
          aria-label={t('snippets.body')}
          spellCheck={false}
        />
        <input
          className={cx(styles.input, 'selectable')}
          value={triggers}
          onChange={(event) => setTriggers(event.target.value)}
          placeholder={t('snippets.triggersPlaceholder')}
          aria-label={t('snippets.triggers')}
          spellCheck={false}
        />
      </form>

      {duplicate && <p className={styles.error}>{t('snippets.duplicate')}</p>}
      {error && <p className={styles.error}>{error}</p>}

      {items.length === 0 ? (
        <p className={styles.empty}>{t('snippets.empty')}</p>
      ) : (
        <div className={styles.list}>
          {items.map((item) => (
            <div key={item.name} className={styles.item}>
              <div className={styles.itemMain}>
                <div className={styles.itemName}>
                  {item.name}
                  {item.used > 0 && (
                    <span className={styles.used}>
                      {t('snippets.used', { count: item.used })}
                    </span>
                  )}
                </div>
                <p className={styles.itemBody} title={item.body}>
                  {item.body}
                </p>
                {item.triggers.length > 0 && (
                  <div className={styles.triggers}>
                    {item.triggers.map((trigger) => (
                      <span key={trigger} className={styles.trigger}>
                        {trigger}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                type="button"
                className={styles.remove}
                onClick={() => void remove(item.name)}
                aria-label={`${item.name} —`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <form className={styles.tryRow} onSubmit={(event) => void runProbe(event)}>
        <input
          className={cx(styles.input, 'selectable')}
          value={probe}
          onChange={(event) => {
            setProbe(event.target.value)
            setMatch(undefined)
          }}
          placeholder={t('snippets.tryPlaceholder')}
          aria-label={t('snippets.try')}
          spellCheck={false}
        />
        <button
          type="submit"
          className={styles.addButton}
          disabled={probe.trim().length === 0}
        >
          {t('snippets.try')}
        </button>
      </form>

      {match !== undefined && (
        <p className={cx(styles.tryResult, match ? styles.tryHit : styles.tryMiss)}>
          {match ? t('snippets.tryHit', { name: match.name }) : t('snippets.tryMiss')}
        </p>
      )}

      <p className={styles.hint}>{t('snippets.hint')}</p>
    </Card>
  )
}
