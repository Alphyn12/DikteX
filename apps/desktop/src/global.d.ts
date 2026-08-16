import type { OmniVoiceBridge } from '@shared/ipc'

declare global {
  interface Window {
    /** Preload'un açtığı köprü. Renderer'ın main process'e tek erişim yolu. */
    readonly omnivoice: OmniVoiceBridge
  }
}

export {}
