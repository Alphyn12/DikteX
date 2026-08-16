import { useCallback, useEffect, useState } from 'react'
import type { EngineState } from '@shared/ipc'

const INITIAL: EngineState = {
  status: 'starting',
  version: null,
  port: 0,
  error: null,
  retries: 0,
}

/**
 * Python motorunun canlı durumu.
 *
 * Main process durum değiştikçe olay yayar; ilk değeri de bir kez sorarız,
 * çünkü pencere motor bağlandıktan sonra açılmış olabilir ve o olayı kaçırmış
 * olabiliriz.
 */
export function useEngine(): { state: EngineState; restart: () => void } {
  const [state, setState] = useState<EngineState>(INITIAL)

  useEffect(() => {
    let cancelled = false
    void window.omnivoice.invoke('engine:get-state').then((current) => {
      if (!cancelled) setState(current)
    })
    const unsubscribe = window.omnivoice.on('engine:state-changed', setState)
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  const restart = useCallback(() => {
    void window.omnivoice.invoke('engine:restart').then(setState)
  }, [])

  return { state, restart }
}
