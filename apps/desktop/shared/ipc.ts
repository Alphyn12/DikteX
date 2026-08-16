/**
 * Renderer ↔ main process sözleşmesi.
 *
 * Bu dosya iki tarafın da tek gerçek kaynağıdır. Bir kanal buraya yazılmadan
 * kullanılamaz; böylece derleme zamanında yanlış kanal adı veya yanlış yük
 * tipi yakalanır.
 */

/** Python motorunun yaşam döngüsü durumu. */
export type EngineStatus =
  | 'starting' // süreç başlatıldı, henüz el sıkışılmadı
  | 'connected' // el sıkışıldı, komut kabul ediyor
  | 'disconnected' // bağlantı koptu, yeniden denenecek
  | 'failed' // yeniden deneme hakkı tükendi

export interface EngineState {
  status: EngineStatus
  /** Motor sürümü — yalnız `connected` durumunda dolu. */
  version: string | null
  /** Motorun dinlediği port. */
  port: number
  /** Son hata mesajı — yalnız `failed` / `disconnected` durumunda dolu. */
  error: string | null
  /** Şu ana kadarki yeniden bağlanma denemesi sayısı. */
  retries: number
}

/** Uygulama penceresinin hangi ekranı gösterdiği. */
export type AppView = 'panel' | 'settings'

export type Locale = 'tr' | 'en'

/**
 * Renderer'ın çağırdığı, main process'in cevapladığı kanallar (istek/yanıt).
 * `args` çağrı argümanlarının demeti, `result` dönüş tipidir.
 */
export interface IpcInvokeMap {
  'window:minimize': { args: []; result: void }
  'window:toggle-maximize': { args: []; result: boolean }
  'window:close': { args: []; result: void }
  'window:is-maximized': { args: []; result: boolean }
  'engine:get-state': { args: []; result: EngineState }
  'engine:restart': { args: []; result: EngineState }
  'app:get-version': { args: []; result: string }
  'app:get-locale': { args: []; result: Locale }
  'app:set-locale': { args: [locale: Locale]; result: void }
}

/**
 * Main process'in renderer'a kendiliğinden gönderdiği olaylar (tek yön).
 */
export interface IpcEventMap {
  'engine:state-changed': EngineState
  'window:maximize-changed': boolean
  'app:locale-changed': Locale
}

export type IpcInvokeChannel = keyof IpcInvokeMap
export type IpcEventChannel = keyof IpcEventMap

/** Preload'un renderer'a açtığı yüzey. `window.omnivoice` olarak erişilir. */
export interface OmniVoiceBridge {
  invoke<C extends IpcInvokeChannel>(
    channel: C,
    ...args: IpcInvokeMap[C]['args']
  ): Promise<IpcInvokeMap[C]['result']>

  /** Olaya abone olur. Dönen fonksiyon aboneliği iptal eder. */
  on<C extends IpcEventChannel>(channel: C, listener: (payload: IpcEventMap[C]) => void): () => void

  /** Hangi pencerede çalıştığımız — HUD ve komut çubuğu aynı kodu paylaşır. */
  readonly surface: WindowSurface
}

export type WindowSurface = 'main' | 'hud' | 'commandbar'
