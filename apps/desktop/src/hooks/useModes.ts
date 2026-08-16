import { useCallback, useEffect, useState } from 'react'
import type {
  ModeList,
  PrivacyState,
  Snippet,
  SnippetList,
  VocabularyList,
} from '@shared/ipc'
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

/**
 * Snippet ve şablon kütüphanesi (Properties V.3).
 *
 * `test` ayrı duruyor çünkü eşleşme bulanık: kullanıcı bir cümle yazıp hangi
 * snippet'in tetikleneceğini, canlı dikteyi beklemeden görebilmeli.
 */
export function useSnippets(): {
  snippets: SnippetList | null
  error: string | null
  add: (name: string, body: string, triggers: string[]) => Promise<boolean>
  remove: (name: string) => Promise<void>
  test: (text: string) => Promise<Snippet | null>
} {
  const [snippets, setSnippets] = useState<SnippetList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  const load = useCallback(async () => {
    if (engine.status !== 'connected') return
    try {
      setSnippets(await window.omnivoice.invoke('snippets:list'))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [engine.status])

  useEffect(() => {
    void load()
  }, [load])

  const add = useCallback(
    async (name: string, body: string, triggers: string[]): Promise<boolean> => {
      try {
        const next = await window.omnivoice.invoke('snippets:add', name, body, triggers)
        setSnippets(next)
        setError(null)
        // Aynı ad zaten varsa motor eklemez. Bunu motorun `added` alanından
        // okuyoruz; listede ada bakmak yanıltırdı — çakışan kayıt zaten orada.
        return next.added
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
        return false
      }
    },
    [],
  )

  const remove = useCallback(async (name: string) => {
    try {
      setSnippets(await window.omnivoice.invoke('snippets:remove', name))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  const test = useCallback(async (text: string): Promise<Snippet | null> => {
    try {
      const { match } = await window.omnivoice.invoke('snippets:test', text)
      setError(null)
      return match
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      return null
    }
  }, [])

  return { snippets, error, add, remove, test }
}

/**
 * Gizlilik ayarları (Properties VI.1).
 *
 * `sttCovered` da taşınıyor çünkü arayüzün maskelemenin **sınırını** söylemesi
 * gerekiyor: ses kaydı konuşma tanımaya maskelenmeden gidiyor.
 */
export function usePrivacy(): {
  privacy: PrivacyState | null
  error: string | null
  setMasking: (enabled: boolean) => Promise<void>
} {
  const [privacy, setPrivacy] = useState<PrivacyState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  useEffect(() => {
    if (engine.status !== 'connected') return
    void (async () => {
      try {
        setPrivacy(await window.omnivoice.invoke('privacy:get'))
        setError(null)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    })()
  }, [engine.status])

  const setMasking = useCallback(async (enabled: boolean) => {
    try {
      setPrivacy(await window.omnivoice.invoke('privacy:set-masking', enabled))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  return { privacy, error, setMasking }
}
