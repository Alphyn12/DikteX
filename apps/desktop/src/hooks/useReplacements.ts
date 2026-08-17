import { useCallback, useEffect, useState } from 'react'
import type { ReplacementList, ReplacementTest } from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * Otomatik değiştirme kuralları (Faz 7.8).
 *
 * `test` ayrı duruyor çünkü kural kullanıcının metnini **doğrudan**
 * değiştiriyor: yanlış bir kural sessizce yanlış metin üretir ve kullanıcı
 * bunu ancak yapıştırdığı yerde görür.
 */
export function useReplacements(): {
  list: ReplacementList | null
  error: string | null
  add: (find: string, replace: string, wholeWord: boolean) => Promise<boolean>
  remove: (find: string) => Promise<void>
  test: (text: string) => Promise<ReplacementTest | null>
} {
  const [list, setList] = useState<ReplacementList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  useEffect(() => {
    if (engine.status !== 'connected') return
    void (async () => {
      try {
        setList(await window.omnivoice.invoke('replacements:list'))
        setError(null)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    })()
  }, [engine.status])

  const add = useCallback(
    async (find: string, replace: string, wholeWord: boolean): Promise<boolean> => {
      try {
        const next = await window.omnivoice.invoke(
          'replacements:add',
          find,
          replace,
          wholeWord,
        )
        setList(next)
        setError(null)
        return next.added
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
        return false
      }
    },
    [],
  )

  const remove = useCallback(async (find: string) => {
    try {
      setList(await window.omnivoice.invoke('replacements:remove', find))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  const test = useCallback(async (text: string): Promise<ReplacementTest | null> => {
    try {
      return await window.omnivoice.invoke('replacements:test', text)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      return null
    }
  }, [])

  return { list, error, add, remove, test }
}
