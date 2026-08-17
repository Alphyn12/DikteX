import { useState } from 'react'
import type { ReplacementTest } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useReplacements } from '../hooks/useReplacements'
import { Card, CardLabel } from './primitives'
import { cx } from '../utils/cx'
import styles from './ReplacementCard.module.css'

/**
 * Otomatik değiştirme kuralları (Faz 7.8).
 *
 * Sözlükten farkı karta yazılı: sözlük konuşma tanımaya **ipucu** veriyor,
 * burası **kesin** bul-değiştir. Whisper bazı özel adları ısrarla aynı
 * biçimde yanlış yazıyor ve ipucu her zaman tutmuyor.
 *
 * Deneme alanı şart: kural metni doğrudan değiştirdiği için kullanıcı
 * kuralını canlı diktede sınamak zorunda kalmamalı.
 */
export function ReplacementCard(): React.JSX.Element {
  const { t } = useI18n()
  const { list, error, add, remove, test } = useReplacements()

  const [find, setFind] = useState('')
  const [replace, setReplace] = useState('')
  const [wholeWord, setWholeWord] = useState(true)
  const [duplicate, setDuplicate] = useState(false)

  const [probe, setProbe] = useState('')
  const [result, setResult] = useState<ReplacementTest | null>(null)

  const rules = list?.rules ?? []
  const canAdd = find.trim().length > 0 && find.trim() !== replace.trim()

  const submit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    if (!canAdd) return
    const added = await add(find.trim(), replace.trim(), wholeWord)
    if (added) {
      setFind('')
      setReplace('')
      setDuplicate(false)
    } else {
      // Form temizlenmiyor: kullanıcı düzeltip yeniden denesin.
      setDuplicate(true)
    }
  }

  const runProbe = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    if (!probe.trim()) return
    setResult(await test(probe))
  }

  return (
    <Card module="audio">
      <div className={styles.head}>
        <CardLabel>{t('replace.title')}</CardLabel>
        <span className={styles.count}>
          {t('replace.count', { count: rules.length })}
        </span>
      </div>

      <form className={styles.form} onSubmit={(event) => void submit(event)}>
        <div className={styles.row}>
          <input
            className={cx(styles.input, 'selectable')}
            value={find}
            onChange={(event) => {
              setFind(event.target.value)
              setDuplicate(false)
            }}
            placeholder={t('replace.findPlaceholder')}
            aria-label={t('replace.find')}
            spellCheck={false}
          />
          <span className={styles.arrow}>→</span>
          <input
            className={cx(styles.input, 'selectable')}
            value={replace}
            onChange={(event) => setReplace(event.target.value)}
            placeholder={t('replace.replacePlaceholder')}
            aria-label={t('replace.replace')}
            spellCheck={false}
          />
          <button type="submit" className={styles.addButton} disabled={!canAdd}>
            +
          </button>
        </div>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={wholeWord}
            onChange={(event) => setWholeWord(event.target.checked)}
          />
          {t('replace.wholeWord')}
        </label>
      </form>

      {duplicate && <p className={styles.error}>{t('replace.duplicate')}</p>}
      {error && <p className={styles.error}>{error}</p>}

      {rules.length === 0 ? (
        <p className={styles.empty}>{t('replace.empty')}</p>
      ) : (
        <div className={styles.list}>
          {rules.map((rule) => (
            <div key={rule.find} className={styles.item}>
              <span className={styles.pair}>
                <span className={styles.from}>{rule.find}</span>
                <span className={styles.arrow}>→</span>
                <span className={styles.to}>{rule.replace}</span>
              </span>
              {rule.used > 0 && (
                <span className={styles.used}>
                  {t('replace.used', { count: rule.used })}
                </span>
              )}
              <button
                type="button"
                className={styles.remove}
                onClick={() => void remove(rule.find)}
                aria-label={t('replace.remove')}
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
            setResult(null)
          }}
          placeholder={t('replace.tryPlaceholder')}
          aria-label={t('replace.try')}
          spellCheck={false}
        />
        <button
          type="submit"
          className={styles.addButton}
          disabled={probe.trim().length === 0}
        >
          {t('replace.try')}
        </button>
      </form>

      {result && (
        <p className={cx(styles.tryResult, result.applied.length > 0 && styles.tryHit)}>
          {result.output}
        </p>
      )}

      <p className={styles.hint}>{t('replace.hint')}</p>
    </Card>
  )
}
