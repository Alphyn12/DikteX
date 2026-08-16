import { useState } from 'react'
import { useI18n } from '../i18n/useI18n'
import { useVocabulary } from '../hooks/useModes'
import { Card, CardLabel } from './primitives'
import { cx } from '../utils/cx'
import styles from './VocabularyEditor.module.css'

/**
 * Özel terim sözlüğü (Properties I.4).
 *
 * Buradaki terimler iki yere birden gider: STT'ye bağlam ipucu olarak (yazımı
 * korunsun diye) ve LLM'e "bunları değiştirme" yönergesi olarak. Ölçtük —
 * sözlükte tireli yazılan `faster-whisper` transkriptte de tireli dönüyor.
 */
export function VocabularyEditor(): React.JSX.Element {
  const { t } = useI18n()
  const { vocabulary, error, add, remove } = useVocabulary()
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)

  const terms = vocabulary?.terms ?? []
  const canAdd = draft.trim().length > 0 && !busy

  const submit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()
    if (!canAdd) return
    setBusy(true)
    try {
      await add(draft.trim())
      setDraft('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card module="audio">
      <div className={styles.head}>
        <CardLabel>{t('vocab.title')}</CardLabel>
        <span className={styles.count}>{t('vocab.count', { count: terms.length })}</span>
      </div>

      <form className={styles.form} onSubmit={(event) => void submit(event)}>
        <input
          className={cx(styles.input, 'selectable')}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t('vocab.placeholder')}
          aria-label={t('vocab.add')}
          spellCheck={false}
        />
        <button type="submit" className={styles.addButton} disabled={!canAdd}>
          +
        </button>
      </form>

      {error && <p className={styles.error}>{error}</p>}

      {terms.length === 0 ? (
        <p className={styles.empty}>{t('vocab.empty')}</p>
      ) : (
        <div className={styles.chips}>
          {terms.map((term) => (
            <span
              key={term.text}
              className={cx(styles.chip, term.suggested && styles.chipSuggested)}
              title={
                term.misspelled > 0
                  ? t('aside.vocabNote', { count: term.misspelled })
                  : undefined
              }
            >
              {term.text}
              <button
                type="button"
                className={styles.remove}
                onClick={() => void remove(term.text)}
                aria-label={`${term.text} —`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <p className={styles.hint}>{t('vocab.hint')}</p>
    </Card>
  )
}
