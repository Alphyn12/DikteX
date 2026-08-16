import { useCallback, useEffect, useState } from 'react'
import type { EngineStats } from '@shared/ipc'
import { useDictation } from './useDictation'
import { useEngine } from './useEngine'

/** Motordan gelen bir dikte kaydı (SQLite satırı). */
export interface HistoryItem {
  id: number
  created_at: string
  raw_text: string
  final_text: string
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

interface EngineData {
  stats: EngineStats | null
  history: HistoryItem[]
  loading: boolean
  error: string | null
  refresh: () => void
}

/**
 * Panelin gerçek verisi: bugünün sayıları, harcama ve son dikteler.
 *
 * Dikte durumu boşa döndüğünde kendiliğinden tazelenir — yeni bir dikte
 * bittiğinde kullanıcı yenile düğmesi aramak zorunda kalmasın.
 */
export function useEngineData(): EngineData {
  const [stats, setStats] = useState<EngineStats | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { state } = useDictation()
  const { state: engine } = useEngine()

  const load = useCallback(async () => {
    // Motor bağlı değilken istek atmak kalıcı bir hata metni bırakırdı;
    // arayüz motordan önce açılıyor, bu yüzden bağlantıyı bekliyoruz.
    if (engine.status !== 'connected') {
      setError(null)
      return
    }
    try {
      const [nextStats, nextHistory] = await Promise.all([
        window.omnivoice.invoke('stats:get'),
        window.omnivoice.invoke('history:search', ''),
      ])
      setStats(nextStats)
      setHistory(nextHistory as unknown as HistoryItem[])
      setError(null)
    } catch (cause) {
      // Motor bağlı değilse veri yok; panel boş durumunu gösterir.
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [engine.status])

  // Motor bağlanır bağlanmaz (ve her yeniden bağlanışta) veriyi çeker.
  useEffect(() => {
    void load()
  }, [load])

  // Dikte bitip boşa döndüğünde yeni kayıt eklenmiş olabilir.
  useEffect(() => {
    if (state.status === 'idle') void load()
  }, [state.status, load])

  return { stats, history, loading, error, refresh: () => void load() }
}
