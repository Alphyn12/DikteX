import { useEffect } from 'react'

/**
 * Ses aygıtı değişikliklerini motora bildirir (Faz 7.6).
 *
 * Kaynak Chromium'un `devicechange` olayı. Motor tarafında yoklama yapmak
 * mümkün değil: PortAudio'nun aygıt listesini tazelemek kütüphaneyi yeniden
 * başlatıyor ve **açık akışları geçersiz kılıyor** — saniyede bir bunu yapmak
 * mikrofonu sürekli keserdi.
 *
 * Olay **gürültülü**: tek bir kulaklık takma iki-üç kez tetikliyor (giriş ve
 * çıkış aygıtları ayrı bildiriliyor). Bu yüzden geciktiriliyor; her tetikte
 * PortAudio'yu yeniden başlatmak mikrofonu boşuna keserdi.
 */
const DEBOUNCE_MS = 800

export function useDeviceWatcher(): void {
  useEffect(() => {
    if (!navigator.mediaDevices?.addEventListener) return

    let timer: ReturnType<typeof setTimeout> | undefined

    const onChange = (): void => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        void window.omnivoice.invoke('audio:devices-changed').catch(() => {
          // Motor kapalıysa yapacak bir şey yok; bir sonraki değişiklikte
          // yeniden denenir.
        })
      }, DEBOUNCE_MS)
    }

    navigator.mediaDevices.addEventListener('devicechange', onChange)
    return () => {
      if (timer) clearTimeout(timer)
      navigator.mediaDevices.removeEventListener('devicechange', onChange)
    }
  }, [])
}
