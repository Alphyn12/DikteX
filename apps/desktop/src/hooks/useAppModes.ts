import { useCallback, useEffect, useState } from 'react'
import type { AppModeMap, ModeId } from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * Uygulama başına varsayılan mod (Faz 7.5).
 *
 * `refresh` dışarı veriliyor çünkü "odaktaki uygulama" zamanla değişiyor:
 * kullanıcı ayarları açık bırakıp başka bir pencereye geçebilir ve döndüğünde
 * eskimiş bir isim görmemeli.
 */
export function useAppModes(): {
  data: AppModeMap | null
  error: string | null
  refresh: () => Promise<void>
  setMode: (app: string, mode: ModeId | null) => Promise<void>
} {
  const [data, setData] = useState<AppModeMap | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  const refresh = useCallback(async () => {
    if (engine.status !== 'connected') return
    try {
      setData(await window.omnivoice.invoke('appmodes:get'))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [engine.status])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setMode = useCallback(async (app: string, mode: ModeId | null) => {
    try {
      setData(await window.omnivoice.invoke('appmodes:set', app, mode))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  return { data, error, refresh, setMode }
}
