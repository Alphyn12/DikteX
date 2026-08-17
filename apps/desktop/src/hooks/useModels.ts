import { useCallback, useEffect, useState } from 'react'
import type {
  CatalogModel,
  LlmProviderName,
  ModelCatalogResult,
  ModelRole,
  ModelSelection,
} from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * Model seçimi ve canlı katalog (Faz 3.15).
 *
 * Katalog isteğe bağlı yükleniyor (`loadCatalog`): 400'den fazla model var ve
 * kullanıcı ayarları açtığında değil, model değiştirmeye karar verdiğinde
 * gerekiyor.
 */
export function useModels(): {
  selection: ModelSelection | null
  catalog: CatalogModel[]
  catalogError: string | null
  loading: boolean
  error: string | null
  loadCatalog: (force?: boolean) => Promise<void>
  setModel: (role: ModelRole, model: string | null) => Promise<void>
  setProvider: (provider: LlmProviderName) => Promise<boolean>
} {
  const [selection, setSelection] = useState<ModelSelection | null>(null)
  const [catalog, setCatalog] = useState<CatalogModel[]>([])
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  useEffect(() => {
    if (engine.status !== 'connected') return
    void (async () => {
      try {
        setSelection(await window.omnivoice.invoke('models:get'))
        setError(null)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    })()
  }, [engine.status])

  const loadCatalog = useCallback(async (force = false) => {
    setLoading(true)
    try {
      const result: ModelCatalogResult = await window.omnivoice.invoke(
        'models:catalog',
        force,
      )
      setCatalog(result.models)
      // Katalog hatası ayrı tutuluyor: liste boş olsa da kullanıcı mevcut
      // seçimini görmeye devam etmeli.
      setCatalogError(result.error)
    } catch (cause) {
      setCatalogError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [])

  const setModel = useCallback(async (role: ModelRole, model: string | null) => {
    try {
      setSelection(await window.omnivoice.invoke('models:set', role, model))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  const setProvider = useCallback(
    async (provider: LlmProviderName): Promise<boolean> => {
      try {
        const next = await window.omnivoice.invoke('models:set-provider', provider)
        setSelection(next)
        // Sağlayıcı değişince katalog da değişiyor; eskisini göstermek
        // seçilemeyecek modeller listelemek olurdu.
        setCatalog([])
        setError(next.changed ? null : 'anahtar-yok')
        return next.changed
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
        return false
      }
    },
    [],
  )

  return {
    selection,
    catalog,
    catalogError,
    loading,
    error,
    loadCatalog,
    setModel,
    setProvider,
  }
}
