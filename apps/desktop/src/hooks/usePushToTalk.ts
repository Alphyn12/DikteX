import { useCallback, useEffect, useState } from 'react'
import type { PushToTalkState } from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * Basılı tut kipi (Faz 7.7).
 *
 * `failed` ayrı bir durum: kullanıcı açmak istedi ama kanca kurulamadı.
 * Anahtarı sessizce kapalıya çevirmek, kullanıcıya tıklamasının hiçbir şey
 * yapmadığını düşündürürdü.
 */
export function usePushToTalk(): {
  state: PushToTalkState | null
  failed: boolean
  setEnabled: (enabled: boolean) => Promise<void>
} {
  const [state, setState] = useState<PushToTalkState | null>(null)
  const [failed, setFailed] = useState(false)
  const { state: engine } = useEngine()

  useEffect(() => {
    if (engine.status !== 'connected') return
    void (async () => {
      try {
        setState(await window.omnivoice.invoke('ptt:get'))
      } catch {
        // Motor henüz hazır değil; bir sonraki bağlantıda yeniden denenir.
      }
    })()
  }, [engine.status])

  const setEnabled = useCallback(async (enabled: boolean) => {
    try {
      const next = await window.omnivoice.invoke('ptt:set', enabled)
      setState(next)
      setFailed(enabled && !next.enabled)
    } catch {
      setFailed(enabled)
    }
  }, [])

  return { state, failed, setEnabled }
}
