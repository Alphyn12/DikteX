/**
 * Dikte protokolü — Python motoru ile paylaşılan sözleşme.
 *
 * Motor tarafındaki karşılığı `omnivoice_engine/pipeline/dictation.py`.
 * Alan adları oradaki `to_payload()` çıktısıyla birebir aynı olmalı.
 */

export type DictationStatus =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'preflight'
  | 'error'

/** Pre-flight'ta gösterilen sonuç. Tüm ölçümler gerçek, tahmin yok. */
export interface DictationResult {
  rawText: string
  finalText: string
  fillersRemoved: number
  language: string | null
  sttProvider: string
  sttModel: string
  sttMs: number
  llmProvider: string | null
  llmModel: string | null
  llmMs: number
  totalMs: number
  costUsd: number
  audioSeconds: number
  appName: string | null
  windowTitle: string | null
  recordId: number | null
}

/** HUD'un çizdiği tüm durum. */
export interface DictationState {
  status: DictationStatus
  /** Anlık ses seviyesi 0–1; yalnız `listening` sırasında anlamlı. */
  level: number
  /** Kayıt süresi, saniye. */
  seconds: number
  /** Ön bellekten alınan pre-roll süresi. */
  preRollSeconds: number
  /** İşleme sırasında hangi adımda olunduğu. */
  step: 'stt' | 'llm' | null
  /** İşleme sırasında elde edilen ham metin — kullanıcı ilerlemeyi görsün. */
  rawText: string | null
  fillersRemoved: number
  /** Dikte başladığında odakta olan uygulama. */
  appName: string | null
  windowTitle: string | null
  result: DictationResult | null
  error: string | null
  /** LLM atlandı gibi ölümcül olmayan uyarılar. */
  warning: string | null
}

export const INITIAL_DICTATION_STATE: DictationState = {
  status: 'idle',
  level: 0,
  seconds: 0,
  preRollSeconds: 0,
  step: null,
  rawText: null,
  fillersRemoved: 0,
  appName: null,
  windowTitle: null,
  result: null,
  error: null,
  warning: null,
}

// ── Mikrofon ────────────────────────────────────────────────────────────

export interface AudioDevice {
  index: number
  name: string
  hostApi: string
  channels: number
  sampleRate: number
  isSystemDefault: boolean
}

export interface AudioDeviceList {
  devices: AudioDevice[]
  /** Seçili aygıt; `null` ise sistem varsayılanı kullanılıyor. */
  current: number | null
  streaming: boolean
}

// ── İstatistik ve harcama ───────────────────────────────────────────────

export interface TodayStats {
  dictations: number
  apps: number
  fillers: number
  audio_seconds: number
  avg_ms: number
}

export interface SpendStats {
  todayUsd: number
  monthUsd: number
  totalUsd: number
  callCount: number
  budgetUsd: number
}

export interface EngineStats {
  today: TodayStats
  spend: SpendStats
}

// ── Kasa ────────────────────────────────────────────────────────────────

export interface VaultEntry {
  provider: string
  configured: boolean
  masked: string | null
}
