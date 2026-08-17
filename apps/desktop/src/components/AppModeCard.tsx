import type { ModeId } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useAppModes } from '../hooks/useAppModes'
import { useModes } from '../hooks/useModes'
import { Card, CardLabel } from './primitives'
import styles from './AppModeCard.module.css'

/**
 * Uygulama başına varsayılan mod (Faz 7.5).
 *
 * Eşleme **yalnız genel kısayolda** uygulanıyor. Kullanıcı Ctrl+Alt+K ile kod
 * modunu açıkça seçtiyse burada tanımlı bir kural onu ezmiyor — karta da bu
 * yazıyor, çünkü aksi hâlde kuralın neden bazen çalışmadığı anlaşılmaz.
 */
export function AppModeCard(): React.JSX.Element {
  const { t } = useI18n()
  const { data, error, refresh, setMode } = useAppModes()
  const { modes } = useModes()

  const entries = Object.entries(data?.modes ?? {})
  const focused = data?.focused ?? null
  const focusedKey = focused
    ? focused.process.toLowerCase().replace(/\.exe$/, '').trim()
    : null
  const alreadyMapped = focusedKey ? focusedKey in (data?.modes ?? {}) : false

  const available: ModeId[] = (modes?.modes ?? []).map((mode) => mode.id)

  return (
    <Card module="prompt">
      <div className={styles.head}>
        <CardLabel>{t('appModes.title')}</CardLabel>
        <button type="button" className={styles.refresh} onClick={() => void refresh()}>
          {t('appModes.refresh')}
        </button>
      </div>

      {entries.length === 0 ? (
        <p className={styles.empty}>{t('appModes.empty')}</p>
      ) : (
        <div className={styles.list}>
          {entries.map(([app, mode]) => (
            <div key={app} className={styles.row}>
              <span className={styles.app}>{app}</span>
              <select
                className={styles.select}
                value={mode}
                onChange={(event) =>
                  void setMode(app, event.target.value as ModeId)
                }
              >
                {available.map((id) => (
                  <option key={id} value={id}>
                    {t(`mode.${id}` as never)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className={styles.remove}
                onClick={() => void setMode(app, null)}
                aria-label={t('appModes.remove')}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/*
        Süreç adını elle yazdırmak yerine odaktakini sunuyoruz. Kullanıcının
        "Code.exe" gibi bir adı bilmesi beklenemez ve yanlış yazılan bir ad
        sessizce hiç eşleşmez.
      */}
      {focused && !alreadyMapped && (
        <div className={styles.add}>
          <span className={styles.addLabel}>
            {t('appModes.addFocused', { app: focused.name })}
          </span>
          <select
            className={styles.select}
            value=""
            onChange={(event) => {
              const mode = event.target.value
              if (mode) void setMode(focused.process, mode as ModeId)
            }}
          >
            <option value="">{t('appModes.pickMode')}</option>
            {available.map((id) => (
              <option key={id} value={id}>
                {t(`mode.${id}` as never)}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}

      <p className={styles.hint}>{t('appModes.hint')}</p>
    </Card>
  )
}
