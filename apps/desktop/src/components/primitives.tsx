import type { CSSProperties, ReactNode } from 'react'
import { MODULE_COLOR, type ModuleId } from '../mock/data'
import styles from './primitives.module.css'
import { cx } from '../utils/cx'

/**
 * Tasarım sisteminin taşıyıcı parçaları.
 * Renk hep `module` üzerinden gelir; bileşenler sabit renk kabul etmez.
 */

/** Modül kimliğini bir CSS değişkenine çevirir. */
export function tone(module: ModuleId | undefined): CSSProperties {
  if (!module) return {}
  return { '--tone': MODULE_COLOR[module] } as CSSProperties
}

// ── Nokta ve şerit ─────────────────────────────────────────────────────────

export function Dot({ module }: { module: ModuleId }): React.JSX.Element {
  return <span className={styles.dot} style={tone(module)} />
}

export function Pill({ module }: { module?: ModuleId }): React.JSX.Element {
  return <span className={styles.pill} style={tone(module)} />
}

// ── Rozetler ───────────────────────────────────────────────────────────────

type BadgeVariant = 'tone' | 'neutral' | 'filled'

// CSS modül anahtarları tip düzeyinde `string | undefined`; `cx` boş değeri
// zaten eliyor.
const BADGE_CLASS: Record<BadgeVariant, string | undefined> = {
  tone: styles.badgeTone,
  neutral: styles.badgeNeutral,
  filled: styles.badgeFilled,
}

export function Badge({
  children,
  module,
  variant = 'neutral',
  softTone,
}: {
  children: ReactNode
  module?: ModuleId
  variant?: BadgeVariant
  /** `filled` varyantında metnin kullanacağı açık ton. */
  softTone?: string
}): React.JSX.Element {
  const style = { ...tone(module), ...(softTone ? { '--tone-soft': softTone } : {}) }
  return (
    <span className={cx(styles.badge, BADGE_CLASS[variant])} style={style as CSSProperties}>
      {children}
    </span>
  )
}

/**
 * Eğitime açık sağlayıcı uyarısı.
 * Kullanıcı bu sağlayıcıyı seçebilir, ama riski görerek seçer.
 */
export function TrainingBadge({ label, tooltip }: { label: string; tooltip: string }): React.JSX.Element {
  return (
    <span className={cx(styles.badge, styles.badgeWarn)} title={tooltip}>
      {label}
    </span>
  )
}

// ── Klavye tuşları ─────────────────────────────────────────────────────────

export function Key({ children }: { children: ReactNode }): React.JSX.Element {
  return <span className={styles.key}>{children}</span>
}

export function KeyCap({
  children,
  accent = false,
}: {
  children: ReactNode
  accent?: boolean
}): React.JSX.Element {
  return (
    <span className={cx(styles.keyCap, accent ? styles.keyCapAccent : '')}>{children}</span>
  )
}

// ── Kart ───────────────────────────────────────────────────────────────────

export function Card({
  children,
  module,
  className = '',
  style,
}: {
  children: ReactNode
  /** Verilirse kartın üst kenarına 2 px modül şeridi eklenir. */
  module?: ModuleId
  className?: string
  style?: CSSProperties
}): React.JSX.Element {
  return (
    <section
      className={cx(styles.card, module ? styles.cardTopped : '', className)}
      style={{ ...tone(module), ...style }}
    >
      {children}
    </section>
  )
}

export function CardLabel({ children }: { children: ReactNode }): React.JSX.Element {
  return <div className={styles.cardLabel}>{children}</div>
}

// ── Anahtar ────────────────────────────────────────────────────────────────

export function Toggle({
  on,
  module,
  label,
  onChange,
}: {
  on: boolean
  module: ModuleId
  /** Ekran okuyucu için; anahtarın yanındaki görünür başlıkla aynı olmalı. */
  label: string
  onChange?: (next: boolean) => void
}): React.JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      className={cx(styles.toggle, on ? styles.toggleOn : '')}
      style={tone(module)}
      onClick={() => onChange?.(!on)}
    >
      <span className={styles.toggleKnob} />
    </button>
  )
}

// ── Ses dalgası ────────────────────────────────────────────────────────────

/**
 * Mockup'taki gecikme dağılımını üretir: her çubuk kendi fazında başlar,
 * böylece dalga tek bir nabız gibi değil, akan bir ses gibi görünür.
 */
function waveDelays(count: number, seed: number): number[] {
  return Array.from({ length: count }, (_, i) => Number(((((i * seed) % 10) / 10) - 0.5).toFixed(2)))
}

/** Dalganın hangi bağlamda çalıştığı — temposunu bu belirler. */
export type WaveVariant = 'panel' | 'commandbar' | 'hud'

const WAVE_CLASS: Record<WaveVariant, string | undefined> = {
  panel: styles.wavePanel,
  commandbar: styles.waveCommandbar,
  hud: styles.waveHud,
}

/**
 * Ham RMS'i göze uygun bir genliğe çevirir.
 *
 * Konuşma sesi RMS olarak 0.02–0.2 aralığında gezinir; bunu doğrusal
 * kullanmak dalgayı hep düz gösterirdi. Karekök eğrisi düşük sesleri
 * yükselterek insan kulağının algısına yaklaştırıyor.
 */
function levelToAmplitude(level: number | undefined): number {
  if (level === undefined) return 1 // seviye bilgisi yoksa (statik gösterim)
  if (level <= 0.0008) return 0.06 // sinyal yok — ince bir çizgi kalsın
  return Math.min(1, 0.15 + Math.sqrt(Math.min(level, 0.25) / 0.25) * 0.85)
}

export function Waveform({
  bars,
  seed,
  module,
  variant,
  height,
  level,
}: {
  bars: number
  seed: number
  module: ModuleId
  variant: WaveVariant
  height: number
  /**
   * Anlık ses seviyesi 0–1. Verilmezse dalga sabit genlikle oynar (panel
   * gibi dekoratif kullanımlar için).
   */
  level?: number
}): React.JSX.Element {
  const delays = waveDelays(bars, seed)
  const amplitude = levelToAmplitude(level)
  const silent = level !== undefined && level <= 0.0008

  return (
    <div
      className={cx(styles.wave, WAVE_CLASS[variant], silent && styles.waveSilent)}
      style={{ ...tone(module), height, '--amp': amplitude } as CSSProperties}
      aria-hidden="true"
    >
      {delays.map((delay, i) => (
        <span
          key={i}
          className={styles.waveBar}
          style={
            {
              '--delay': `${delay}s`,
              // Hareket kapalıyken donmuş dalganın şekli.
              '--static-scale': 0.3 + ((i * 7) % 10) / 14,
            } as CSSProperties
          }
        />
      ))}
    </div>
  )
}

// ── Sparkline ──────────────────────────────────────────────────────────────

export function Sparkline({
  values,
  module,
}: {
  values: readonly number[]
  module: ModuleId
}): React.JSX.Element {
  return (
    <div className={styles.spark} style={tone(module)} aria-hidden="true">
      {values.map((height, i) => (
        <span key={i} className={styles.sparkBar} style={{ height: `${height}%` }} />
      ))}
    </div>
  )
}
