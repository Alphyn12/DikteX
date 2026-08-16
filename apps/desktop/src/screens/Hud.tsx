import { useEffect, useRef, useState } from 'react'
import type { DictationResult, DictationState } from '@shared/ipc'
import type { ModuleId } from '../mock/data'
import { Badge, Waveform } from '../components/primitives'
import { useI18n } from '../i18n/useI18n'
import { useDictation } from '../hooks/useDictation'
import { cx } from '../utils/cx'
import styles from './Hud.module.css'

/**
 * Canlı dikte HUD'u — mockup 1c'nin üç durumu.
 *
 *   dinliyor  → dalga formu, süre, canlı metin
 *   işliyor   → dönen halka, aşama listesi
 *   pre-flight→ düzenlenebilir önizleme, Yapıştır / İptal
 *
 * Hiçbir çıktı kullanıcı onaylamadan yapıştırılmaz.
 */
export function Hud(): React.JSX.Element | null {
  const { state, cancel, paste } = useDictation()

  /*
   * Esc yalnız HUD odaktayken çalışır — yani pre-flight ve hata durumunda.
   *
   * Dinleme ve işleme sırasında HUD bilinçli olarak odak almaz: kullanıcı
   * konuşurken kendi uygulamasında yazmaya devam edebilmeli. Odak almayan bir
   * pencere klavye olayı da alamaz, bu yüzden o durumlarda iptal global
   * kısayolla yapılır. Arayüzdeki ipucu da buna göre değişiyor — yanlış
   * kısayol göstermek kullanıcıyı takılı bırakır.
   */
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

  if (state.status === 'idle') return null

  const toneClass =
    state.status === 'listening'
      ? styles.listening
      : state.status === 'processing'
        ? styles.processing
        : state.status === 'error'
          ? styles.errored
          : styles.preflight

  return (
    <div className={styles.root}>
      <div className={cx(styles.card, toneClass)}>
        {state.status === 'listening' && <Listening state={state} />}
        {state.status === 'processing' && <Processing state={state} />}
        {state.status === 'preflight' && state.result && (
          <Preflight result={state.result} warning={state.warning} onPaste={paste} onCancel={cancel} />
        )}
        {state.status === 'error' && <Errored message={state.error} onDismiss={cancel} />}
      </div>
    </div>
  )
}

// ── 01 · Dinliyor ──────────────────────────────────────────────────────────

/** Mod → renk kimliği. Motor tarafındaki `Mode.module` ile aynı. */
const MODE_MODULE: Record<string, ModuleId> = {
  quick: 'audio',
  code: 'prompt',
  translate_en: 'system',
  mega_prompt: 'prompt',
  image_prompt: 'meeting',
  sql: 'automation',
  commit: 'automation',
}

function modeModule(mode: string): ModuleId {
  return MODE_MODULE[mode] ?? 'audio'
}

function Listening({ state }: { state: DictationState }): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const module = modeModule(state.mode)

  return (
    <>
      <div className={styles.head}>
        <Waveform bars={16} seed={5} module={module} variant="hud" height={34} />
        <div className={styles.headText}>
          <div className={styles.title}>{t('hud.listening')}</div>
          <div className={styles.detail}>
            {t('hud.preRoll', {
              seconds: formatNumber(state.preRollSeconds, { minimumFractionDigits: 1 }),
            })}
          </div>
        </div>
        <span className={cx(styles.timer, 'tabular')}>{formatDuration(state.seconds)}</span>
      </div>

      <div className={styles.footer}>
        {/* Hangi modda olunduğu her an görünür — yanlış modda konuşmak
            kullanıcının en sık yapacağı hata. */}
        <Badge module={module} variant="filled">
          {t(`mode.${state.mode}` as never)}
        </Badge>
        {state.appName && <Badge variant="neutral">{state.appName}</Badge>}
        {/*
          Dinlerken HUD odakta değil, bu yüzden düz Esc buraya ulaşmaz.
          Gösterilen kısayol gerçekten çalışan kısayol olmalı.
        */}
        <span className={styles.meta}>{t('hud.stopHint')}</span>
      </div>
    </>
  )
}

// ── 02 · İşliyor ───────────────────────────────────────────────────────────

function Processing({ state }: { state: DictationState }): React.JSX.Element {
  const { t } = useI18n()
  const sttDone = state.step === 'llm'

  return (
    <>
      <div className={styles.head}>
        <div className={styles.ring} />
        <div className={styles.headText}>
          <div className={styles.title}>{t('hud.processing')}</div>
          <div className={styles.detail}>
            {sttDone ? t('hud.step.llm') : t('hud.step.stt')}
          </div>
        </div>
      </div>

      <div className={styles.steps}>
        <Step done={sttDone} active={!sttDone} label={t('hud.step.transcribe')} />
        <Step
          done={false}
          active={sttDone}
          label={t('hud.step.fillers', { count: state.fillersRemoved })}
        />
        {/* Seçili metin okunduysa kullanıcı bunu bilmeli: gizlice pano
            üzerinden bir şey okunduğunu görmeden geçmemeli. */}
        {state.selectionChars > 0 && (
          <Step
            done={sttDone}
            active={false}
            label={t('hud.step.selection', { count: state.selectionChars })}
          />
        )}
        <Step done={false} active={false} label={t('hud.step.polish')} />
      </div>

      {state.rawText && <div className={styles.transcript}>{state.rawText}</div>}
    </>
  )
}

function Step({
  done,
  active,
  label,
}: {
  done: boolean
  active: boolean
  label: string
}): React.JSX.Element {
  return (
    <div className={cx(styles.step, active && styles.stepActive, !done && !active && styles.stepPending)}>
      <span
        className={cx(
          styles.stepBox,
          done && styles.stepBoxDone,
          active && !done && styles.stepBoxActive,
        )}
      >
        {done ? '✓' : ''}
      </span>
      {label}
    </div>
  )
}

// ── 03 · Pre-flight ────────────────────────────────────────────────────────

function Preflight({
  result,
  warning,
  onPaste,
  onCancel,
}: {
  result: DictationResult
  warning: string | null
  onPaste: (text: string) => void
  onCancel: () => void
}): React.JSX.Element {
  const { t, formatNumber } = useI18n()
  const [text, setText] = useState(result.finalText)
  const areaRef = useRef<HTMLTextAreaElement>(null)

  // Yeni bir sonuç geldiğinde düzenleme alanını tazele.
  useEffect(() => setText(result.finalText), [result.finalText])

  // Alanı odakla ama imleci sona koy — kullanıcı hemen Enter'a basabilsin
  // ya da düzenlemeye başlayabilsin.
  useEffect(() => {
    const area = areaRef.current
    if (!area) return
    area.focus()
    area.setSelectionRange(area.value.length, area.value.length)
  }, [])

  const submit = (): void => onPaste(text)

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    // Enter yapıştırır; Shift+Enter satır ekler.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <>
      <div className={styles.head}>
        <span className={styles.title}>{t('hud.readyToPaste')}</span>
        <div className={styles.spacer} />
        {result.language && <span className={styles.detail}>{result.language}</span>}
      </div>

      <textarea
        ref={areaRef}
        className={cx(styles.preview, 'selectable')}
        value={text}
        rows={Math.min(8, Math.max(2, Math.ceil(text.length / 60)))}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        aria-label={t('hud.readyToPaste')}
      />

      {warning && <div className={styles.warning}>{warning}</div>}

      <div className={styles.actions}>
        <button type="button" className={styles.primary} onClick={submit}>
          {t('hud.paste')}
          <span className={styles.shortcut}>Enter</span>
        </button>
        <button type="button" className={styles.secondary} onClick={onCancel}>
          {t('hud.cancel')}
          <span className={styles.shortcut} style={{ marginInlineStart: 6 }}>
            Esc
          </span>
        </button>
        <div className={styles.spacer} />
        {/*
          Gerçek ölçümler. Mockup'ta sabit "180 ms" yazıyordu; burada
          gösterilen değer o dikteye ait gerçek süredir.
        */}
        <span className={cx(styles.meta, 'tabular')}>
          {formatNumber(result.totalMs)} ms
          {result.costUsd > 0 && ` · $${result.costUsd.toFixed(5)}`}
        </span>
      </div>

      <div className={styles.footer}>
        <Badge module={modeModule(result.mode)} variant="filled">
          {t(`mode.${result.mode}` as never)}
        </Badge>
        {result.appName && <Badge variant="neutral">{result.appName}</Badge>}
        {result.fillersRemoved > 0 && (
          <Badge module="automation" variant="tone">
            {t('hud.fillersRemoved', { count: result.fillersRemoved })}
          </Badge>
        )}
        {result.selectionChars > 0 && (
          <Badge module="prompt" variant="tone">
            {t('hud.selectionUsed', { count: result.selectionChars })}
          </Badge>
        )}
        {result.variables.map((name) => (
          <Badge key={name} variant="neutral">{`{${name}}`}</Badge>
        ))}
        <span className={styles.meta}>
          {result.sttProvider} · {result.llmProvider ?? t('hud.localOnly')}
        </span>
      </div>
    </>
  )
}

// ── Hata ───────────────────────────────────────────────────────────────────

function Errored({
  message,
  onDismiss,
}: {
  message: string | null
  onDismiss: () => void
}): React.JSX.Element {
  const { t } = useI18n()
  return (
    <>
      <div className={styles.head}>
        <span className={styles.title}>{t('hud.error')}</span>
      </div>
      <p className={cx(styles.errorText, 'selectable')}>{message ?? ''}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.secondary} onClick={onDismiss}>
          {t('hud.dismiss')}
          <span className={styles.shortcut} style={{ marginInlineStart: 6 }}>
            Esc
          </span>
        </button>
      </div>
    </>
  )
}

// ── Yardımcı ───────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const total = Math.floor(seconds)
  const minutes = Math.floor(total / 60)
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
