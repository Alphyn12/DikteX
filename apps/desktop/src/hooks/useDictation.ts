import { useCallback, useEffect, useState } from 'react'
import { INITIAL_DICTATION_STATE, type DictationState, type ModeId } from '@shared/ipc'

/**
 * Dikte durumunun canlı görünümü.
 *
 * Hem HUD hem ana pencere aynı durumu okur; tek kaynak main process'teki
 * `DictationController`.
 */
export function useDictation(): {
  state: DictationState
  /** Mod belirtilmezse hızlı dikte başlar. */
  toggle: (mode?: ModeId) => void
  cancel: () => void
  paste: (text: string) => void
} {
  const [state, setState] = useState<DictationState>(INITIAL_DICTATION_STATE)

  useEffect(() => {
    let cancelled = false
    // İlk değeri bir kez soruyoruz: pencere dikte başladıktan sonra açılmış
    // olabilir ve o olayı kaçırmış olabilir.
    void window.omnivoice.invoke('dictation:get-state').then((current) => {
      if (!cancelled) setState(current)
    })
    const unsubscribe = window.omnivoice.on('dictation:changed', setState)
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  const toggle = useCallback((mode?: ModeId) => {
    void window.omnivoice.invoke('dictation:toggle', mode)
  }, [])

  const cancel = useCallback(() => {
    void window.omnivoice.invoke('dictation:cancel')
  }, [])

  const paste = useCallback((text: string) => {
    void window.omnivoice.invoke('dictation:paste', text)
  }, [])

  return { state, toggle, cancel, paste }
}
