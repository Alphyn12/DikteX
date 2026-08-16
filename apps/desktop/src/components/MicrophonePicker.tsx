import { useCallback, useEffect, useState } from 'react'
import type { AudioDeviceList } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { Card, CardLabel } from './primitives'
import { cx } from '../utils/cx'
import styles from './MicrophonePicker.module.css'

/**
 * Mikrofon kaynağı seçici.
 *
 * Liste motordan gelir ve zaten temizlenmiştir: aynı fiziksel aygıtın farklı
 * host API kopyaları ve sürücü yolu adları elenmiş durumda (bkz.
 * `audio/capture.py::list_input_devices`).
 *
 * "Sistem varsayılanı" ayrı bir seçenek olarak sunulur — kullanıcı Windows'ta
 * aygıt değiştirdiğinde OmniVoice'un da onunla birlikte değişmesini isteyebilir.
 */
export function MicrophonePicker(): React.JSX.Element {
  const { t } = useI18n()
  const [list, setList] = useState<AudioDeviceList | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setList(await window.omnivoice.invoke('audio:list-devices'))
      setError(null)
    } catch (cause) {
      // Motor bağlı değilse liste alınamaz; kart boş kalmasın, sebep yazsın.
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const select = async (device: number | null): Promise<void> => {
    if (busy || list?.current === device) return
    setBusy(true)
    try {
      const next = await window.omnivoice.invoke('audio:set-device', device)
      setList(next)
      // Motor aygıtı açamadıysa eskisine döner ve sebebini bildirir.
      // Bunu göstermezsek kullanıcı tıklar, hiçbir şey olmaz, sebebini bilemez.
      setError(next.error ?? null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }

  const devices = list?.devices ?? []

  return (
    <Card>
      <div className={styles.head}>
        <CardLabel>{t('mic.title')}</CardLabel>
        <button type="button" className={styles.refresh} onClick={() => void load()}>
          {t('mic.refresh')}
        </button>
      </div>

      {/* Hata listenin yerine geçmez, üstüne çıkar: kullanıcı hem sebebi
          görmeli hem de başka bir aygıt seçebilmeli. */}
      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.list} role="radiogroup" aria-label={t('mic.title')}>
        <Option
          active={list?.current === null || list?.current === undefined}
          name={t('mic.systemDefault')}
          sub={t('mic.systemDefaultHint')}
          onSelect={() => void select(null)}
        />

        {devices.map((device) => (
          <Option
            key={device.index}
            active={list?.current === device.index}
            name={device.name}
            sub={`${device.hostApi} · ${device.sampleRate} Hz${
              device.isSystemDefault ? ' · Windows' : ''
            }`}
            onSelect={() => void select(device.index)}
          />
        ))}

        {devices.length === 0 && <p className={styles.empty}>{t('mic.noDevices')}</p>}
      </div>

      <div className={styles.status}>
        <span className={cx(styles.dot, !list?.streaming && styles.dotOff)} />
        {list?.streaming ? t('mic.streaming') : t('mic.stopped')}
      </div>

      {/*
        Sürekli dinleme sıfır gecikmeli ön belleğin bedeli. Kullanıcı bunu
        ayarlarda gizli bir satırdan değil, mikrofon kartının kendisinden
        görmeli.
      */}
      <div className={styles.privacy}>
        <div className={styles.privacyTitle}>{t('mic.alwaysListening')}</div>
        <p className={styles.privacyBody}>{t('mic.alwaysListeningHint')}</p>
      </div>
    </Card>
  )
}

function Option({
  active,
  name,
  sub,
  onSelect,
}: {
  active: boolean
  name: string
  sub: string
  onSelect: () => void
}): React.JSX.Element {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      className={cx(styles.option, active && styles.optionActive)}
      onClick={onSelect}
    >
      <span className={styles.marker} />
      <span className={styles.optionText}>
        <span className={styles.name} title={name}>
          {name}
        </span>
        <span className={styles.sub}>{sub}</span>
      </span>
    </button>
  )
}
