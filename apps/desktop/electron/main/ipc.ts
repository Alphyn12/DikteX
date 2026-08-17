import { app, ipcMain, type BrowserWindow } from 'electron'
import type { EngineSupervisor } from './engine'
import type { DictationController } from './dictation'
import type { MeetingController } from './meeting'
import type { HotkeyRegistration } from './hotkeys'
import type {
  AudioDeviceList,
  EngineStats,
  Locale,
  LoopbackDeviceList,
  MeetingHistoryItem,
  ModeList,
  VaultEntry,
  AppModeMap,
  ModeId,
  ModelCatalogResult,
  ModelRole,
  ModelSelection,
  PrivacyState,
  QueueFlushResult,
  QueueList,
  Snippet,
  SnippetList,
  VocabularyList,
} from '@shared/ipc'
import { getLocaleStore } from './locale'
import { resolveRegion } from './windows/regionWindow'

interface IpcDeps {
  engine: EngineSupervisor
  dictation: DictationController
  meeting: MeetingController
  hotkeys: HotkeyRegistration
  getMainWindow: () => BrowserWindow
}

export function registerIpc({
  engine,
  dictation,
  meeting,
  hotkeys,
  getMainWindow,
}: IpcDeps): void {
  // ── Pencere ────────────────────────────────────────────────────────────

  ipcMain.handle('window:minimize', () => {
    getMainWindow().minimize()
  })

  ipcMain.handle('window:toggle-maximize', () => {
    const window = getMainWindow()
    if (window.isMaximized()) window.unmaximize()
    else window.maximize()
    return window.isMaximized()
  })

  // Kapatma uygulamayı sonlandırmaz, tepsiye çeker — global kısayolun
  // çalışmaya devam etmesi gerekiyor (bkz. tray.ts).
  ipcMain.handle('window:close', () => {
    getMainWindow().hide()
  })

  ipcMain.handle('window:is-maximized', () => getMainWindow().isMaximized())

  // ── Motor ──────────────────────────────────────────────────────────────

  ipcMain.handle('engine:get-state', () => engine.getState())
  ipcMain.handle('engine:restart', () => engine.restart())

  // ── Uygulama ───────────────────────────────────────────────────────────

  ipcMain.handle('app:get-version', () => app.getVersion())
  ipcMain.handle('app:get-locale', () => getLocaleStore().get())

  ipcMain.handle('app:set-locale', (_event, next: Locale) => {
    getLocaleStore().set(next)
  })

  // ── Dikte ──────────────────────────────────────────────────────────────

  ipcMain.handle('dictation:get-state', () => dictation.getState())
  ipcMain.handle('dictation:toggle', (_event, mode?: string) => dictation.toggle(mode))

  // Bölge seçim kaplamasından gelen sonuç.
  ipcMain.handle('region:result', (_event, region) => resolveRegion(region))
  ipcMain.handle('dictation:cancel', () => dictation.cancel())
  ipcMain.handle('dictation:toggle-pause', () => dictation.togglePause())
  ipcMain.handle('dictation:paste', (_event, text: string) => dictation.paste(text))

  // ── Toplantı ───────────────────────────────────────────────────────────

  ipcMain.handle('meeting:get-state', () => meeting.getState())
  ipcMain.handle('meeting:toggle', () => meeting.toggle())
  ipcMain.handle('meeting:cancel', () => meeting.cancel())
  ipcMain.handle('meeting:dismiss', () => meeting.dismiss())

  ipcMain.handle('meeting:devices', async (): Promise<LoopbackDeviceList> => {
    const response = await engine.request<LoopbackDeviceList>({ type: 'meeting:devices' })
    return {
      devices: response.devices ?? [],
      available: response.available ?? false,
    }
  })

  ipcMain.handle('meeting:history', async (): Promise<MeetingHistoryItem[]> => {
    const response = await engine.request<{ items: MeetingHistoryItem[] }>({
      type: 'meeting:history',
    })
    return response.items ?? []
  })

  // ── Modlar ─────────────────────────────────────────────────────────────

  ipcMain.handle('modes:list', async (): Promise<ModeList> => {
    const response = await engine.request<ModeList>({ type: 'modes:list' })
    // Kısayol bilgisi Electron tarafında; motor onu bilmiyor. İkisini burada
    // birleştiriyoruz ki arayüz tek bir kaynaktan okusun.
    const modes = (response.modes ?? []).map((mode) => {
      const binding = hotkeys.modes.find((entry) => entry.mode === mode.id)
      return {
        ...mode,
        accelerator: binding?.accelerator,
        conflicted: binding ? !binding.registered : false,
      }
    })
    return { modes, defaultModel: response.defaultModel ?? '' }
  })

  // ── Sözlük ─────────────────────────────────────────────────────────────

  ipcMain.handle('vocabulary:list', () =>
    engine.request<VocabularyList>({ type: 'vocabulary:list' }),
  )

  ipcMain.handle('vocabulary:add', (_event, text: string) =>
    engine.request<VocabularyList>({ type: 'vocabulary:add', text }),
  )

  ipcMain.handle('vocabulary:remove', (_event, text: string) =>
    engine.request<VocabularyList>({ type: 'vocabulary:remove', text }),
  )

  ipcMain.handle('snippets:list', () =>
    engine.request<SnippetList>({ type: 'snippets:list' }),
  )

  ipcMain.handle(
    'snippets:add',
    (_event, name: string, body: string, triggers: string[]) =>
      engine.request<SnippetList>({ type: 'snippets:add', name, body, triggers }),
  )

  ipcMain.handle('snippets:remove', (_event, name: string) =>
    engine.request<SnippetList>({ type: 'snippets:remove', name }),
  )

  ipcMain.handle('snippets:test', (_event, text: string) =>
    engine.request<{ match: Snippet | null }>({ type: 'snippets:test', text }),
  )

  ipcMain.handle('audio:devices-changed', () =>
    engine.request<{ applied: boolean }>({ type: 'devices:changed' }),
  )

  ipcMain.handle('appmodes:get', () =>
    engine.request<AppModeMap>({ type: 'appmodes:get' }),
  )

  ipcMain.handle('appmodes:set', (_event, app: string, mode: ModeId | null) =>
    engine.request<AppModeMap>({ type: 'appmodes:set', app, mode }),
  )

  ipcMain.handle('models:catalog', (_event, force?: boolean) =>
    engine.request<ModelCatalogResult>({ type: 'models:catalog', force }),
  )

  ipcMain.handle('models:get', () =>
    engine.request<ModelSelection>({ type: 'models:get' }),
  )

  ipcMain.handle('models:set', (_event, role: ModelRole, model: string | null) =>
    engine.request<ModelSelection>({ type: 'models:set', role, model }),
  )

  ipcMain.handle('queue:list', () => engine.request<QueueList>({ type: 'queue:list' }))

  ipcMain.handle('queue:flush', () =>
    engine.request<QueueFlushResult>({ type: 'queue:flush' }),
  )

  ipcMain.handle('queue:remove', (_event, id: string) =>
    engine.request<QueueList>({ type: 'queue:remove', id }),
  )

  ipcMain.handle('queue:clear', () => engine.request<QueueList>({ type: 'queue:clear' }))

  ipcMain.handle('privacy:get', () =>
    engine.request<PrivacyState>({ type: 'privacy:get' }),
  )

  ipcMain.handle('privacy:set-masking', (_event, enabled: boolean) =>
    engine.request<PrivacyState>({ type: 'privacy:set-masking', enabled }),
  )

  ipcMain.handle('dictation:set-auto-stop', (_event, seconds: number) =>
    engine.request<PrivacyState>({ type: 'dictation:set-auto-stop', seconds }),
  )

  // ── Mikrofon ───────────────────────────────────────────────────────────

  ipcMain.handle('audio:list-devices', async (): Promise<AudioDeviceList> => {
    const response = await engine.request<AudioDeviceList>({ type: 'devices:list' })
    return {
      devices: response.devices ?? [],
      current: response.current ?? null,
      streaming: response.streaming ?? false,
    }
  })

  ipcMain.handle(
    'audio:set-device',
    async (_event, device: number | null): Promise<AudioDeviceList> => {
      const response = await engine.request<AudioDeviceList>({
        type: 'devices:set',
        device,
      })
      // Motor `devices:set` yanıtında listeyi geri göndermiyor; seçimi
      // uyguladıktan sonra güncel listeyi ayrıca istiyoruz.
      const list = await engine.request<AudioDeviceList>({ type: 'devices:list' })
      return {
        devices: list.devices ?? [],
        current: response.current ?? list.current ?? null,
        streaming: response.streaming ?? list.streaming ?? false,
        // Hata mutlaka taşınmalı: aygıt başka bir uygulama tarafından
        // tutuluyorsa kullanıcı bunu görmeli, yoksa arayüz "hiçbir şey
        // olmadı" gibi davranır.
        error: response.error ?? null,
      }
    },
  )

  // ── Veri ───────────────────────────────────────────────────────────────

  ipcMain.handle('stats:get', () => engine.request<EngineStats>({ type: 'stats:get' }))

  ipcMain.handle('vault:list', async (): Promise<VaultEntry[]> => {
    const response = await engine.request<{ entries: VaultEntry[] }>({ type: 'vault:list' })
    return response.entries ?? []
  })

  ipcMain.handle('history:search', async (_event, query: string) => {
    const response = await engine.request<{ items: Record<string, unknown>[] }>({
      type: 'history:search',
      query,
    })
    return response.items ?? []
  })

  // ── Olay yayınları ─────────────────────────────────────────────────────

  // Dil main process'te de değişebilir (ileride sistem menülerinden);
  // renderer'ı tek bir yerden haberdar ediyoruz.
  getLocaleStore().on('change', (locale: Locale) => {
    const window = getMainWindow()
    if (!window.isDestroyed()) window.webContents.send('app:locale-changed', locale)
  })

  // Pencere düğmesinin simgesi büyütme durumuna göre değişir; kullanıcı
  // pencereyi kenardan sürükleyerek de büyütebileceği için olayı dinliyoruz.
  const window = getMainWindow()
  const notify = (maximized: boolean): void => {
    if (!window.isDestroyed()) window.webContents.send('window:maximize-changed', maximized)
  }
  window.on('maximize', () => notify(true))
  window.on('unmaximize', () => notify(false))
}
