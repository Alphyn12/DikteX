import { useCallback, useEffect, useState } from 'react'
import type { ModeList, VocabularyList } from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * Modlar ve sözlük — motordan gelen gerçek yapılandırma.
 *
 * Motor bağlanmadan istek atmak kalıcı bir hata metni bırakırdı; arayüz
 * motordan önce açıldığı için bağlantıyı bekliyoruz.
 */
export function useModes(): { modes: ModeList | null; error: string | null } {
  const [modes, setModes] = useState<ModeList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  useEffect(() => {
    if (engine.status !== 'connected') return
    let cancelled = false
    window.omnivoice
      .invoke('modes:list')
      .then((result) => {
        if (!cancelled) {
          setModes(result)
          setError(null)
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      })
    return () => {
      cancelled = true
    }
  }, [engine.status])

  return { modes, error }
}

export function useVocabulary(): {
  vocabulary: VocabularyList | null
  error: string | null
  add: (text: string) => Promise<void>
  remove: (text: string) => Promise<void>
} {
  const [vocabulary, setVocabulary] = useState<VocabularyList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  const load = useCallback(async () => {
    if (engine.status !== 'connected') return
    try {
      setVocabulary(await window.omnivoice.invoke('vocabulary:list'))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [engine.status])

  useEffect(() => {
    void load()
  }, [load])

  const add = useCallback(async (text: string) => {
    try {
      setVocabulary(await window.omnivoice.invoke('vocabulary:add', text))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  const remove = useCallback(async (text: string) => {
    try {
      setVocabulary(await window.omnivoice.invoke('vocabulary:remove', text))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  return { vocabulary, error, add, remove }
}
