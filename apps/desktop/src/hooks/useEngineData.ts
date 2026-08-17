import { useCallback, useEffect, useState } from 'react'
import type { EngineStats, HistoryRow } from '@shared/ipc'
import { useDictation } from './useDictation'
import { useEngine } from './useEngine'

/**
 * Motordan gelen bir dikte kaydı.
 *
 * Paylaşılan sözleşmeden geliyor. Burada ayrı bir kopya vardı ve çağrı
 * `as unknown as` ile dönüştürülüyordu; o çift dönüşüm tip sistemini tam da
 * işe yarayacağı yerde devre dışı bırakıyordu. `history:search` dönüş şekli
 * değiştiğinde derleme sessiz kaldı, hata ancak çalışma anında görünecekti.
 */
export type HistoryItem = HistoryRow

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
      setHistory(nextHistory.items)
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
