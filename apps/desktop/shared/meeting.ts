/**
 * Toplantı protokolü — Python motoruyla paylaşılan sözleşme.
 *
 * Motor tarafındaki karşılığı `omnivoice_engine/pipeline/meeting.py`.
 */

export type MeetingStatus =
  | 'idle'
  | 'recording'
  | 'transcribing'
  | 'summarizing'
  | 'done'
  | 'error'

export interface MeetingActionItem {
  task: string
  owner: string | null
  due: string | null
}

export interface MeetingResult {
  /** [BEN] / [DİĞER KATILIMCILAR] etiketli tam döküm. */
  transcript: string
  /** Markdown özet. LLM düşerse boş kalır ama döküm yine durur. */
  summary: string
  actionItems: MeetingActionItem[]
  durationSeconds: number
  language: string | null
  /** Mikrofon kanalında konuşma var mıydı? */
  hadMicrophone: boolean
  /** Sistem sesi kanalında konuşma var mıydı? */
  hadSystemAudio: boolean
  sttMs: number
  llmMs: number
  costUsd: number
  recordId: number | null
}

export interface MeetingState {
  status: MeetingStatus
  seconds: number
  /** Kendi mikrofonunun anlık seviyesi. */
  micLevel: number
  /** Hoparlörden gelen sesin anlık seviyesi. */
  systemLevel: number
  /** Uzun kayıtta hangi parçanın çevrildiği. */
  chunk: number
  chunks: number
  /** Hangi kanalın çevrildiği: 'mine' | 'theirs' | null */
  channel: string | null
  result: MeetingResult | null
  error: string | null
  warning: string | null
}

export const INITIAL_MEETING_STATE: MeetingState = {
  status: 'idle',
  seconds: 0,
  micLevel: 0,
  systemLevel: 0,
  chunk: 0,
  chunks: 0,
  channel: null,
  result: null,
  error: null,
  warning: null,
}

/** Kaydedilebilir çıkış aygıtı (hoparlör / kulaklık). */
export interface LoopbackDevice {
  name: string
  isSystemDefault: boolean
}

export interface LoopbackDeviceList {
  devices: LoopbackDevice[]
  /** Bu makinede sistem sesi kaydı mümkün mü? */
  available: boolean
}

/** Geçmiş toplantı kaydı (SQLite satırı). */
export interface MeetingHistoryItem {
  id: number
  created_at: string
  transcript: string
  summary: string
  action_items: MeetingActionItem[]
  duration_seconds: number
  language: string | null
  cost_usd: number
}
