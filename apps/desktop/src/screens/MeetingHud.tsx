import { useEffect } from 'react'
import type { MeetingResult, MeetingState } from '@shared/ipc'
import { Badge, Waveform } from '../components/primitives'
import { useI18n } from '../i18n/useI18n'
import { useMeeting } from '../hooks/useMeeting'
import { cx } from '../utils/cx'
import styles from './Hud.module.css'
import meetingStyles from './MeetingHud.module.css'

/**
 * Toplantı HUD'u (Faz 4).
 *
 * Dikte HUD'uyla aynı pencereyi ve aynı görsel dili paylaşır. Fark, iki ses
 * kanalını birden göstermesi: kendi mikrofonun ve hoparlörden gelen ses.
 * İkisinin ayrı ayrı görünmesi önemli — biri sessizse kullanıcı bunu kayıt
 * bitmeden fark etmeli.
 */
export function MeetingHud(): React.JSX.Element | null {
  const { state, cancel, dismiss } = useMeeting()

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      if (state.status === 'done' || state.status === 'error') dismiss()
      else cancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cancel, dismiss, state.status])

  if (state.status === 'idle') return null

  const toneClass =
    state.status === 'recording'
      ? meetingStyles.recording
      : state.status === 'error'
        ? styles.errored
        : state.status === 'done'
          ? meetingStyles.finished
          : styles.processing

  return (
    <div className={styles.root}>
      <div className={cx(styles.card, toneClass)}>
        {state.status === 'recording' && <Recording state={state} />}
        {(state.status === 'transcribing' || state.status === 'summarizing') && (
          <Working state={state} />
        )}
        {state.status === 'done' && state.result && (
          <Finished result={state.result} onDismiss={dismiss} />
        )}
        {state.status === 'error' && (
          <Failed message={state.error} onDismiss={dismiss} />
        )}
      </div>
    </div>
  )
}

// ── Kaydediyor ─────────────────────────────────────────────────────────────

function Recording({ state }: { state: MeetingState }): React.JSX.Element {
  const { t } = useI18n()

  return (
    <>
      <div className={styles.head}>
        <span className={meetingStyles.dot} />
        <div className={styles.headText}>
          <div className={styles.title}>{t('meeting.recording')}</div>
          <div className={styles.detail}>{t('meeting.recording.hint')}</div>
        </div>
        <span className={cx(styles.timer, 'tabular')}>{formatDuration(state.seconds)}</span>
      </div>

      {/*
        İki kanal ayrı gösteriliyor. Sistem sesi sessizse kullanıcı bunu
        toplantı bitmeden görmeli — sonradan "karşı taraf kaydedilmemiş"
        demek çok geç olur.
      */}
      <div className={meetingStyles.channels}>
        <Channel
          label={t('meeting.channel.mine')}
          level={state.micLevel}
          module="audio"
          seed={5}
        />
        <Channel
          label={t('meeting.channel.theirs')}
          level={state.systemLevel}
          module="meeting"
          seed={7}
        />
      </div>

      <div className={styles.footer}>
        <span className={styles.meta}>{t('meeting.stopHint')}</span>
      </div>
    </>
  )
}

function Channel({
  label,
  level,
  module,
  seed,
}: {
  label: string
  level: number
  module: 'audio' | 'meeting'
  seed: number
}): React.JSX.Element {
  const { t } = useI18n()
  const silent = level <= 0.0008

  return (
    <div className={meetingStyles.channel}>
      <Waveform bars={14} seed={seed} module={module} variant="hud" height={24} level={level} />
      <div className={meetingStyles.channelText}>
        <div className={meetingStyles.channelLabel}>{label}</div>
        {silent && <div className={meetingStyles.channelSilent}>{t('meeting.channel.silent')}</div>}
      </div>
    </div>
  )
}

// ── İşliyor ────────────────────────────────────────────────────────────────

function Working({ state }: { state: MeetingState }): React.JSX.Element {
  const { t } = useI18n()
  const transcribing = state.status === 'transcribing'

  return (
    <>
      <div className={styles.head}>
        <div className={styles.ring} />
        <div className={styles.headText}>
          <div className={styles.title}>
            {transcribing ? t('meeting.transcribing') : t('meeting.summarizing')}
          </div>
          <div className={styles.detail}>
            {transcribing && state.chunks > 1
              ? t('meeting.chunkProgress', { done: state.chunk, total: state.chunks })
              : t('meeting.working.hint')}
          </div>
        </div>
      </div>
    </>
  )
}

// ── Bitti ──────────────────────────────────────────────────────────────────

function Finished({
  result,
  onDismiss,
}: {
  result: MeetingResult
  onDismiss: () => void
}): React.JSX.Element {
  const { t, formatNumber } = useI18n()

  const copy = (text: string): void => {
    void navigator.clipboard.writeText(text)
  }

  return (
    <>
      <div className={styles.head}>
        <span className={styles.title}>{t('meeting.done')}</span>
        <div className={styles.spacer} />
        <span className={cx(styles.detail, 'tabular')}>
          {formatDuration(result.durationSeconds)}
        </span>
      </div>

      <div className={meetingStyles.summary}>
        {result.summary ? (
          <pre className={cx(meetingStyles.summaryText, 'selectable')}>{result.summary}</pre>
        ) : (
          <p className={meetingStyles.summaryEmpty}>{t('meeting.noSummary')}</p>
        )}
      </div>

      {result.actionItems.length > 0 && (
        <div className={meetingStyles.actions}>
          <div className={meetingStyles.actionsLabel}>{t('aside.actionItems')}</div>
          {result.actionItems.map((item, index) => (
            <div key={index} className={meetingStyles.actionItem}>
              <span className={meetingStyles.actionBox} aria-hidden="true" />
              <span className={meetingStyles.actionText}>
                {item.task}
                {item.owner && <span className={meetingStyles.actionMeta}> · {item.owner}</span>}
                {item.due && <span className={meetingStyles.actionMeta}> · {item.due}</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primary}
          onClick={() => copy(result.summary || result.transcript)}
        >
          {t('meeting.copySummary')}
        </button>
        <button
          type="button"
          className={styles.secondary}
          onClick={() => copy(result.transcript)}
        >
          {t('meeting.copyTranscript')}
        </button>
        <div className={styles.spacer} />
        <button type="button" className={styles.secondary} onClick={onDismiss}>
          {t('hud.dismiss')}
        </button>
      </div>

      <div className={styles.footer}>
        {/* Hangi kanalların gerçekten ses içerdiği — sonradan "karşı taraf
            kaydedilmemiş" sürprizini önler. */}
        <Badge module="audio" variant={result.hadMicrophone ? 'filled' : 'neutral'}>
          {t('meeting.channel.mine')}
        </Badge>
        <Badge module="meeting" variant={result.hadSystemAudio ? 'filled' : 'neutral'}>
          {t('meeting.channel.theirs')}
        </Badge>
        <span className={cx(styles.meta, 'tabular')}>
          {formatNumber(result.sttMs + result.llmMs)} ms
          {result.costUsd > 0 && ` · $${result.costUsd.toFixed(4)}`}
        </span>
      </div>
    </>
  )
}

// ── Hata ───────────────────────────────────────────────────────────────────

function Failed({
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
        <span className={styles.title}>{t('meeting.error')}</span>
      </div>
      <p className={cx(styles.errorText, 'selectable')}>{message ?? ''}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.secondary} onClick={onDismiss}>
          {t('hud.dismiss')}
        </button>
      </div>
    </>
  )
}

function formatDuration(seconds: number): string {
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const mm = String(minutes).padStart(2, '0')
  const ss = String(secs).padStart(2, '0')
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`
}
