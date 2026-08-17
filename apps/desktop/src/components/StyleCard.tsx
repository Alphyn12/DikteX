import { useCallback, useEffect, useState } from 'react'
import type { StyleState } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useEngine } from '../hooks/useEngine'
import { Card, CardLabel } from './primitives'
import styles from './StyleCard.module.css'

/**
 * Öğrenen kişisel stil (Faz 3.13).
 *
 * Pre-flight'ta yaptığınız düzeltmeler saklanıp sonraki istemlere örnek olarak
 * ekleniyor. Bu, **geçmiş dikte içeriğini yeni isteklere taşıyor** — dün
 * yazdığınız kişisel bir not, bugünkü iş diktenizin isteminde yer alabilir.
 *
 * Beklenmeyen veri akışları açık rıza ister. Bu yüzden kip varsayılan kapalı,
 * saklanan her örnek burada **tek tek görünüyor** ve tek düğmeyle siliniyor.
 */
export function StyleCard(): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const { state: engine } = useEngine()
  const [state, setState] = useState<StyleState | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (engine.status !== 'connected') return
    try {
      setState(await window.omnivoice.invoke('style:get'))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [engine.status])

  useEffect(() => {
    void load()
  }, [load])

  const toggle = async (enabled: boolean): Promise<void> => {
    try {
      setState(await window.omnivoice.invoke('style:set-enabled', enabled))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  const clear = async (): Promise<void> => {
    try {
      setState(await window.omnivoice.invoke('style:clear'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  const examples = state?.examples ?? []
  const enabled = state?.enabled ?? false

  return (
    <Card module="prompt">
      <div className={styles.head}>
        <CardLabel>{t('style.title')}</CardLabel>
        <label className={styles.switch}>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => void toggle(event.target.checked)}
          />
          {enabled ? t('style.on') : t('style.off')}
        </label>
      </div>

      <p className={styles.desc}>{t('style.desc')}</p>

      {/*
        Gizlilik notu kalıcı ve kip kapalıyken de görünüyor: kullanıcı
        açmadan önce ne olacağını bilmeli.
      */}
      <p className={styles.privacy}>{t('style.privacy')}</p>

      {enabled && (
        <>
          <div className={styles.countRow}>
            <span className={styles.count}>
              {t('style.count', { count: examples.length })}
            </span>
            {examples.length > 0 && (
              <button type="button" className={styles.clear} onClick={() => void clear()}>
                {t('style.clear')}
              </button>
            )}
          </div>

          {examples.length === 0 ? (
            <p className={styles.empty}>{t('style.empty')}</p>
          ) : (
            <div className={styles.list}>
              {examples
                .slice()
                .reverse()
                .map((example) => (
                  <div key={`${example.createdAt}-${example.before}`} className={styles.item}>
                    <span className={styles.mode}>
                      {t(`mode.${example.mode}` as never)}
                    </span>
                    <p className={styles.before}>{example.before}</p>
                    <p className={styles.after}>{example.after}</p>
                  </div>
                ))}
            </div>
          )}
        </>
      )}

      {error && <p className={styles.error}>{error}</p>}

      {enabled && examples.length > 0 && (
        <p className={styles.hint}>
          {t('style.hint', { count: formatNumber(Math.min(examples.length, 5)) })}
        </p>
      )}
    </Card>
  )
}
