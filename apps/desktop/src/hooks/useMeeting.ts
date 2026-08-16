import { useCallback, useEffect, useState } from 'react'
import { INITIAL_MEETING_STATE, type MeetingState } from '@shared/ipc'

/**
 * Toplantı durumunun canlı görünümü.
 *
 * Dikte ile aynı desen; tek kaynak main process'teki `MeetingController`.
 */
export function useMeeting(): {
  state: MeetingState
  toggle: () => void
  cancel: () => void
  dismiss: () => void
} {
  const [state, setState] = useState<MeetingState>(INITIAL_MEETING_STATE)

  useEffect(() => {
    let cancelled = false
    void window.omnivoice.invoke('meeting:get-state').then((current) => {
      if (!cancelled) setState(current)
    })
    const unsubscribe = window.omnivoice.on('meeting:changed', setState)
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  const toggle = useCallback(() => {
    void window.omnivoice.invoke('meeting:toggle')
  }, [])

  const cancel = useCallback(() => {
    void window.omnivoice.invoke('meeting:cancel')
  }, [])

  const dismiss = useCallback(() => {
    void window.omnivoice.invoke('meeting:dismiss')
  }, [])

  return { state, toggle, cancel, dismiss }
}
