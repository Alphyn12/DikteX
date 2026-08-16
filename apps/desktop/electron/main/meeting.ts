import { BrowserWindow } from 'electron'
import type { EngineSupervisor } from './engine'
import {
  INITIAL_MEETING_STATE,
  type MeetingResult,
  type MeetingState,
  type MeetingStatus,
} from '@shared/ipc'

/**
 * Toplantı durumunun main process tarafındaki tek kaynağı.
 *
 * Dikte denetleyicisiyle aynı desen: motordan gelen parçalı olayları tek bir
 * duruma birleştirir ve arayüze yayar.
 */
export class MeetingController {
  private state: MeetingState = { ...INITIAL_MEETING_STATE }

  constructor(
    private readonly engine: EngineSupervisor,
    private readonly onChange: (state: MeetingState) => void,
  ) {
    engine.on('message', (message: unknown) => this.handleEngineMessage(message))

    // Motor koparsa arayüzde donmuş bir "kaydediyor" kalmasın — kullanıcı
    // kaydın sürdüğünü sanıp konuşmaya devam etmemeli.
    engine.on('state', (engineState: { status: string }) => {
      if (engineState.status !== 'connected' && this.state.status !== 'idle') {
        this.reset()
      }
    })
  }

  getState(): MeetingState {
    return { ...this.state }
  }

  private patch(changes: Partial<MeetingState>): void {
    this.state = { ...this.state, ...changes }
    this.onChange(this.getState())
  }

  private reset(): void {
    this.patch({ ...INITIAL_MEETING_STATE })
  }

  private handleEngineMessage(message: unknown): void {
    if (typeof message !== 'object' || message === null || !('type' in message)) return
    const event = message as Record<string, unknown>

    switch (event['type']) {
      case 'meeting:state':
        this.applyStatus(event)
        break

      case 'meeting:tick':
        if (this.state.status === 'recording') {
          this.patch({
            seconds: Number(event['seconds'] ?? 0),
            micLevel: Number(event['micLevel'] ?? 0),
            systemLevel: Number(event['systemLevel'] ?? 0),
          })
        }
        break

      case 'meeting:progress':
        this.patch({
          chunk: Number(event['chunk'] ?? 0),
          chunks: Number(event['chunks'] ?? 0),
          channel: event['channel'] ? String(event['channel']) : null,
        })
        break

      case 'meeting:warning':
        this.patch({ warning: String(event['message'] ?? '') })
        break

      default:
        break
    }
  }

  private applyStatus(event: Record<string, unknown>): void {
    const status = String(event['state']) as MeetingStatus

    switch (status) {
      case 'recording':
        this.patch({ ...INITIAL_MEETING_STATE, status })
        break

      case 'transcribing':
      case 'summarizing':
        this.patch({ status, micLevel: 0, systemLevel: 0 })
        break

      case 'done':
        this.patch({
          status,
          result: (event['result'] as MeetingResult | undefined) ?? null,
        })
        break

      case 'error':
        this.patch({ status, error: String(event['message'] ?? 'Bilinmeyen hata') })
        break

      case 'idle':
        this.reset()
        break

      default:
        break
    }
  }

  // ── Komutlar ──────────────────────────────────────────────────────────

  toggle(): void {
    this.engine.send({ type: 'meeting:toggle' })
  }

  cancel(): void {
    this.engine.send({ type: 'meeting:cancel' })
    this.reset()
  }

  dismiss(): void {
    this.engine.send({ type: 'meeting:dismiss' })
    this.reset()
  }
}

/** Durumu tüm pencerelere yayar. */
export function broadcastMeeting(state: MeetingState): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) window.webContents.send('meeting:changed', state)
  }
}
