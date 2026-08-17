/**
 * Geçmiş kaydı — motordaki `dictations` tablosunun satır biçimi.
 *
 * Alan adları **snake_case**: doğrudan SQLite satırından geliyor ve ara bir
 * dönüşüm katmanı eklemek, tek kazancı isimlendirme tutarlılığı olan bir
 * kopyalama işi olurdu.
 */
export interface HistoryRow {
  id: number
  created_at: string
  raw_text: string
  final_text: string
  mode: string
  app_name: string | null
  window_title: string | null
  language: string | null
  stt_provider: string | null
  stt_model: string | null
  llm_provider: string | null
  llm_model: string | null
  audio_seconds: number
  fillers_removed: number
  stt_ms: number
  llm_ms: number
  total_ms: number
  cost_usd: number
  pasted: number
}
