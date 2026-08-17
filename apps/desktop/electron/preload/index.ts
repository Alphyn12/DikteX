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

const INVOKE_CHANNELS = new Set<IpcInvokeChannel>([
  'window:minimize',
  'window:toggle-maximize',
  'window:close',
  'window:is-maximized',
  'engine:get-state',
  'engine:restart',
  'app:get-version',
  'app:get-locale',
  'app:set-locale',
  'dictation:get-state',
  'dictation:toggle',
  'dictation:cancel',
  'dictation:toggle-pause',
  'dictation:paste',
  'audio:list-devices',
  'audio:set-device',
  'meeting:get-state',
  'meeting:toggle',
  'meeting:cancel',
  'meeting:dismiss',
  'meeting:devices',
  'meeting:history',
  'region:result',
  'modes:list',
  'vocabulary:list',
  'vocabulary:add',
  'vocabulary:remove',
  'snippets:list',
  'snippets:add',
  'snippets:remove',
  'snippets:test',
  'style:get',
  'style:set-enabled',
  'style:clear',
  'replacements:list',
  'replacements:add',
  'replacements:remove',
  'replacements:test',
  'replacements:set-numbers',
  'ptt:get',
  'ptt:set',
  'audio:devices-changed',
  'appmodes:get',
  'appmodes:set',
  'models:catalog',
  'models:get',
  'models:set',
  'queue:list',
  'queue:flush',
  'queue:remove',
  'queue:clear',
  'privacy:get',
  'privacy:set-masking',
  'dictation:set-auto-stop',
  'stats:get',
  'vault:list',
  'history:search',
])

const EVENT_CHANNELS = new Set<IpcEventChannel>([
  'engine:state-changed',
  'window:maximize-changed',
  'app:locale-changed',
  'dictation:changed',
  'meeting:changed',
])

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
