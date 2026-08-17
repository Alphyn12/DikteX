import { contextBridge, ipcRenderer } from 'electron'
import type {
  IpcEventChannel,
  IpcEventMap,
  IpcInvokeChannel,
  OmniVoiceBridge,
  WindowSurface,
} from '@shared/ipc'

/**
 * Renderer ile main process arasındaki tek geçit.
 *
 * Renderer'da Node ve `ipcRenderer` kapalıdır. Buradan yalnız `shared/ipc.ts`
 * içinde ilan edilmiş kanallar açılır; keyfi kanal çağrısı yapılamaz.
 */

/**
 * İzin verilen çağrı kanalları.
 *
 * `Record<IpcInvokeChannel, true>` biçimi bilinçli: bir kanal sözleşmeye
 * eklenip buraya eklenmezse **derleme hata veriyor**. Düz bir `Set` bunu
 * yakalamıyordu ve olay listesindeki eksik bir kanal, uygulamayı bomboş bir
 * pencereyle açılır hâle getirmişti (bkz. `EVENT_CHANNEL_MAP`).
 */
const INVOKE_CHANNEL_MAP: Record<IpcInvokeChannel, true> = {
  'window:minimize': true,
  'window:toggle-maximize': true,
  'window:close': true,
  'window:is-maximized': true,
  'engine:get-state': true,
  'engine:restart': true,
  'app:get-version': true,
  'app:get-locale': true,
  'app:set-locale': true,
  'app:get-autostart': true,
  'app:set-autostart': true,
  'dictation:get-state': true,
  'dictation:toggle': true,
  'dictation:cancel': true,
  'dictation:toggle-pause': true,
  'dictation:draft': true,
  'dictation:paste': true,
  'audio:list-devices': true,
  'audio:set-device': true,
  'meeting:get-state': true,
  'meeting:toggle': true,
  'meeting:cancel': true,
  'meeting:dismiss': true,
  'meeting:devices': true,
  'meeting:history': true,
  'region:result': true,
  'modes:list': true,
  'vocabulary:list': true,
  'vocabulary:add': true,
  'vocabulary:remove': true,
  'snippets:list': true,
  'snippets:add': true,
  'snippets:remove': true,
  'snippets:test': true,
  'style:get': true,
  'style:set-enabled': true,
  'style:clear': true,
  'replacements:list': true,
  'replacements:add': true,
  'replacements:remove': true,
  'replacements:test': true,
  'replacements:set-numbers': true,
  'ptt:get': true,
  'ptt:set': true,
  'audio:devices-changed': true,
  'appmodes:get': true,
  'appmodes:set': true,
  'models:catalog': true,
  'models:get': true,
  'models:set': true,
  'models:set-provider': true,
  'queue:list': true,
  'queue:flush': true,
  'queue:remove': true,
  'queue:clear': true,
  'privacy:get': true,
  'privacy:set-masking': true,
  'dictation:set-auto-stop': true,
  'dictation:set-preflight': true,
  'stats:get': true,
  'vault:list': true,
  'history:search': true,
  'history:copy': true,
  'history:delete': true,
  'history:delete-all': true,
  'history:export': true,
}

const INVOKE_CHANNELS = new Set<IpcInvokeChannel>(
  Object.keys(INVOKE_CHANNEL_MAP) as IpcInvokeChannel[],
)

/**
 * İzin verilen olay kanalları.
 *
 * `Record<IpcEventChannel, true>` üzerinden kuruluyor, düz bir `Set` olarak
 * değil — fark kritik: bu biçimde **eksik bir kanal derleme hatası** veriyor.
 *
 * Düz liste kullanılıyordu ve `history:query` (Faz 7.13) sözleşmeye eklenip
 * buraya eklenmemişti. Tip denetimi geçti, derleme geçti, ama uygulama
 * açılışta `İzin verilmeyen IPC olayı` fırlatıp React ağacını çökertti:
 * **bomboş bir pencere**, hiçbir hata görünmeden. Aynı tuzağa bir daha
 * düşmemek için liste artık tipten türetiliyor.
 */
const EVENT_CHANNEL_MAP: Record<IpcEventChannel, true> = {
  'engine:state-changed': true,
  'window:maximize-changed': true,
  'app:locale-changed': true,
  'dictation:changed': true,
  'meeting:changed': true,
  'history:query': true,
}

const EVENT_CHANNELS = new Set<IpcEventChannel>(
  Object.keys(EVENT_CHANNEL_MAP) as IpcEventChannel[],
)

/** Hangi pencerede olduğumuzu HTML dosya adından çıkarıyoruz. */
function detectSurface(): WindowSurface {
  const file = location.pathname.split('/').pop() ?? ''
  if (file.startsWith('hud')) return 'hud'
  if (file.startsWith('commandbar')) return 'commandbar'
  if (file.startsWith('region')) return 'region'
  return 'main'
}

const bridge: OmniVoiceBridge = {
  invoke(channel, ...args) {
    if (!INVOKE_CHANNELS.has(channel)) {
      throw new Error(`İzin verilmeyen IPC kanalı: ${channel}`)
    }
    return ipcRenderer.invoke(channel, ...args) as never
  },

  on<C extends IpcEventChannel>(channel: C, listener: (payload: IpcEventMap[C]) => void) {
    if (!EVENT_CHANNELS.has(channel)) {
      throw new Error(`İzin verilmeyen IPC olayı: ${channel}`)
    }
    const wrapped = (_event: unknown, payload: IpcEventMap[C]): void => listener(payload)
    ipcRenderer.on(channel, wrapped)
    return () => {
      ipcRenderer.off(channel, wrapped)
    }
  },

  surface: detectSurface(),
}

contextBridge.exposeInMainWorld('omnivoice', bridge)
