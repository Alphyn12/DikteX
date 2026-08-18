import { useCallback, useEffect, useState } from 'react'
import type { VaultEntry } from '@shared/ipc'
import { useEngine } from './useEngine'

/**
 * API kasasının gerçek içeriği (Faz 2.4).
 *
 * Bu kanca sonradan yazıldı: Ayarlar'daki kasa kartı ve kenar çubuğundaki
 * "N anahtar" sayacı, mockup'tan kalma **sabit bir listeyi** gösteriyordu.
 * Listede kullanıcının hiç sahip olmadığı bir kayıt ("Webhook (Notion)") ve
 * gerçeğine benzeyen ama uydurma maskeler vardı. `vault:list` uç noktası
 * motorda, IPC'de ve preload izin listesinde baştan beri hazırdı; yalnız
 * arayüz onu çağırmıyordu.
 *
 * Anahtar değerleri buraya **hiç gelmiyor**: motor yalnız maskelenmiş
 * biçimi yayınlıyor.
 */
export function useVault(): {
  entries: VaultEntry[]
  configuredCount: number
  error: string | null
  reload: () => Promise<void>
} {
  const [entries, setEntries] = useState<VaultEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const { state: engine } = useEngine()

  const reload = useCallback(async () => {
    try {
      setEntries(await window.omnivoice.invoke('vault:list'))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  useEffect(() => {
    // Motor bağlı değilken çağırmak hata veriyor ve kasa boş görünürdü —
    // "anahtarınız yok" demek, "henüz bilmiyorum" demekten çok farklı.
    if (engine.status !== 'connected') return
    void reload()
  }, [engine.status, reload])

  return {
    entries,
    configuredCount: entries.filter((entry) => entry.configured).length,
    error,
    reload,
  }
}
