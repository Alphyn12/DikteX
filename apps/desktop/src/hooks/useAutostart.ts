import { useCallback, useEffect, useState } from 'react'
import type { AutostartState } from '@shared/ipc'

/**
 * Windows açılışında otomatik başlatma (Faz 6.5).
 *
 * `supported` alanı ayrı: geliştirme kurulumunda ayar uygulanamıyor ve
 * kullanıcıya "açık" deyip açılışta başlamamak en kötü sonuç olurdu.
 */
export function useAutostart(): {
  state: AutostartState | null
  setEnabled: (enabled: boolean) => Promise<void>
} {
  const [state, setState] = useState<AutostartState | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        setState(await window.omnivoice.invoke('app:get-autostart'))
      } catch {
        // Ana süreç yanıt vermiyorsa anahtar kapalı görünür; zararsız.
      }
    })()
  }, [])

  const setEnabled = useCallback(async (enabled: boolean) => {
    try {
      // Motorun DÖNDÜĞÜ değeri kullanıyoruz, istenen değeri değil:
      // `setLoginItemSettings` sessizce başarısız olabiliyor.
      setState(await window.omnivoice.invoke('app:set-autostart', enabled))
    } catch {
      setState((current) => current)
    }
  }, [])

  return { state, setEnabled }
}
