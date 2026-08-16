import { useCallback, useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/useI18n'
import styles from './RegionSelector.module.css'

/**
 * Ekran bölgesi seçici (Properties V.2).
 *
 * Kullanıcı fareyle bir dikdörtgen çizer. Seçim yalnız fare bırakıldığında
 * kesinleşir; `Esc` veya sağ tık iptal eder.
 *
 * Kazara yapılan tek tıklamayı seçim saymıyoruz: kaplama açıldığında refleksle
 * tıklayan kullanıcı 1×1 piksellik bir bölge seçmiş olurdu.
 */
const MIN_SIZE = 8

interface Point {
  x: number
  y: number
}

export function RegionSelector(): React.JSX.Element {
  const { t } = useI18n()
  const [origin, setOrigin] = useState<Point | null>(null)
  const [current, setCurrent] = useState<Point | null>(null)
  // Seçim gönderildikten sonra ikinci kez gönderilmesin.
  const settled = useRef(false)

  const cancel = useCallback(() => {
    if (settled.current) return
    settled.current = true
    void window.omnivoice.invoke('region:result', null)
  }, [])

  const commit = useCallback((rect: DOMRect | null) => {
    if (settled.current) return
    if (!rect || rect.width < MIN_SIZE || rect.height < MIN_SIZE) {
      cancel()
      return
    }
    settled.current = true
    void window.omnivoice.invoke('region:result', {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    })
  }, [cancel])

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        event.preventDefault()
        cancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cancel])

  const rect = origin && current ? toRect(origin, current) : null

  return (
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        // Sağ tık iptal — seçim çizerken fikir değiştirmenin en hızlı yolu.
        if (event.button !== 0) {
          cancel()
          return
        }
        setOrigin({ x: event.clientX, y: event.clientY })
        setCurrent({ x: event.clientX, y: event.clientY })
      }}
      onMouseMove={(event) => {
        if (origin) setCurrent({ x: event.clientX, y: event.clientY })
      }}
      onMouseUp={() => commit(rect)}
      onContextMenu={(event) => event.preventDefault()}
    >
      {!origin && (
        <div className={styles.hint}>
          <span>{t('region.hint')}</span>
          <span className={styles.hintKey}>Esc</span>
          <span className={styles.hintDim}>{t('region.cancel')}</span>
        </div>
      )}

      {rect && (
        <>
          <div
            className={styles.selection}
            style={{
              left: rect.x,
              top: rect.y,
              width: rect.width,
              height: rect.height,
            }}
          />
          <SizeBadge rect={rect} />
        </>
      )}
    </div>
  )
}

/**
 * Boyut göstergesi. Seçimin altına sığmıyorsa üstüne geçer — ekranın en
 * altından seçim yapıldığında etiket görünmez kalmasın.
 */
function SizeBadge({ rect }: { rect: DOMRect }): React.JSX.Element {
  const below = rect.y + rect.height + 26 < window.innerHeight
  return (
    <div
      className={styles.size}
      style={{
        left: rect.x,
        top: below ? rect.y + rect.height + 6 : Math.max(0, rect.y - 24),
      }}
    >
      {Math.round(rect.width)} × {Math.round(rect.height)}
    </div>
  )
}

function toRect(a: Point, b: Point): DOMRect {
  // Kullanıcı her yöne sürükleyebilir; dikdörtgeni normalize ediyoruz.
  const x = Math.min(a.x, b.x)
  const y = Math.min(a.y, b.y)
  return new DOMRect(x, y, Math.abs(a.x - b.x), Math.abs(a.y - b.y))
}
