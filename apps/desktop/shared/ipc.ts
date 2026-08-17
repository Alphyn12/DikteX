/**
 * Renderer ↔ main process sözleşmesi.
 *
 * Bu dosya iki tarafın da tek gerçek kaynağıdır. Bir kanal buraya yazılmadan
 * kullanılamaz; böylece derleme zamanında yanlış kanal adı veya yanlış yük
 * tipi yakalanır.
 */

import type { HistoryRow } from './history'
import type {
  AppModeMap,
  AudioDeviceList,
  DictationState,
  EngineStats,
  ModeId,
  ModeList,
  ModelCatalogResult,
  ModelRole,
  ModelSelection,
  PrivacyState,
  PushToTalkState,
  QueueFlushResult,
  QueueList,
  ReplacementList,
  ReplacementTest,
  Snippet,
  StyleState,
  SnippetList,
  VaultEntry,
  VocabularyList,
} from './dictation'
import type {
  LoopbackDeviceList,
  MeetingHistoryItem,
  MeetingState,
} from './meeting'

export type {
  LoopbackDevice,
  LoopbackDeviceList,
  MeetingActionItem,
  MeetingHistoryItem,
  MeetingResult,
  MeetingState,
  MeetingStatus,
} from './meeting'
export { INITIAL_MEETING_STATE } from './meeting'

export type {
  AppModeMap,
  AudioDevice,
  AudioDeviceList,
  CatalogModel,
  DictationResult,
  DictationState,
  DictationStatus,
  EngineStats,
  ModeId,
  ModeInfo,
  ModeList,
  ModelCatalogResult,
  ModelRole,
  ModelSelection,
  OutputProfile,
  PrivacyState,
  PushToTalkState,
  QueueFlushResult,
  QueueList,
  QueuedClip,
  ReplacementList,
  ReplacementRule,
  ReplacementTest,
  RoleModel,
  StyleExample,
  StyleState,
  Snippet,
  SnippetList,
  SpendStats,
  TodayStats,
  VaultEntry,
  VocabularyList,
  VocabularyTerm,
} from './dictation'
export { INITIAL_DICTATION_STATE } from './dictation'
export type { HistoryRow } from './history'

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
export type AppView = 'panel' | 'history' | 'settings'

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

  // ── Dikte ──────────────────────────────────────────────────────────────
  'dictation:get-state': { args: []; result: DictationState }
  /** Modu belirtilmezse hızlı dikte başlar. */
  'dictation:toggle': { args: [mode?: ModeId]; result: void }
  'dictation:cancel': { args: []; result: void }
  /** Kaydı duraklatır veya sürdürür. */
  'dictation:toggle-pause': { args: []; result: void }
  /** Pre-flight'taki metni yapıştırır. Kullanıcı düzenlemişse düzenlenmiş hâli. */
  'dictation:paste': { args: [text: string]; result: void }

  // ── Toplantı ───────────────────────────────────────────────────────────
  'meeting:get-state': { args: []; result: MeetingState }
  'meeting:toggle': { args: []; result: void }
  'meeting:cancel': { args: []; result: void }
  'meeting:dismiss': { args: []; result: void }
  'meeting:devices': { args: []; result: LoopbackDeviceList }
  'meeting:history': { args: []; result: MeetingHistoryItem[] }

  // ── Ekran bölgesi ──────────────────────────────────────────────────────
  /** Kaplamadaki seçimi main process'e bildirir. `null` iptal demektir. */
  'region:result': {
    args: [region: { x: number; y: number; width: number; height: number } | null]
    result: void
  }

  // ── Modlar ─────────────────────────────────────────────────────────────
  'modes:list': { args: []; result: ModeList }

  // ── Sözlük ─────────────────────────────────────────────────────────────
  'vocabulary:list': { args: []; result: VocabularyList }
  'vocabulary:add': { args: [text: string]; result: VocabularyList }
  'vocabulary:remove': { args: [text: string]; result: VocabularyList }

  // ── Snippet kütüphanesi ────────────────────────────────────────────────
  'snippets:list': { args: []; result: SnippetList }
  /**
   * `added: false` demek "aynı ad zaten var" demek — motor sessizce
   * yok saymıyor, arayüz bunu kullanıcıya söyleyebilsin diye bildiriyor.
   */
  'snippets:add': {
    args: [name: string, body: string, triggers: string[]]
    result: SnippetList & { added: boolean }
  }
  'snippets:remove': { args: [name: string]; result: SnippetList }
  /**
   * Yazılan cümleyle hangi snippet'in tetikleneceğini önceden denemek için.
   *
   * Eşleşme bulanık olduğu için bu şart: aksi hâlde kullanıcı ayarını ancak
   * canlı dikte sırasında sınayabilir.
   */
  'snippets:test': { args: [text: string]; result: { match: Snippet | null } }

  // ── Öğrenen kişisel stil (Faz 3.13) ────────────────────────────────────
  'style:get': { args: []; result: StyleState }
  'style:set-enabled': { args: [enabled: boolean]; result: StyleState }
  'style:clear': { args: []; result: StyleState }

  // ── Otomatik değiştirme (Faz 7.8 / 7.9) ────────────────────────────────
  'replacements:list': { args: []; result: ReplacementList }
  'replacements:add': {
    args: [find: string, replace: string, wholeWord: boolean]
    result: ReplacementList & { added: boolean }
  }
  'replacements:remove': { args: [find: string]; result: ReplacementList }
  /** Kuralı canlı diktede sınamadan denemek için. */
  'replacements:test': { args: [text: string]; result: ReplacementTest }
  /** Türkçe sayıları rakama çevirme (Faz 7.9). */
  'replacements:set-numbers': { args: [enabled: boolean]; result: { enabled: boolean } }

  // ── Basılı tut kipi (Faz 7.7) ──────────────────────────────────────────
  'ptt:get': { args: []; result: PushToTalkState }
  'ptt:set': { args: [enabled: boolean]; result: PushToTalkState }

  // ── Uygulama başına mod (Faz 7.5) ──────────────────────────────────────
  'appmodes:get': { args: []; result: AppModeMap }
  /** `mode: null` eşlemeyi kaldırır. */
  'appmodes:set': { args: [app: string, mode: ModeId | null]; result: AppModeMap }

  // ── Modeller (Faz 3.15) ────────────────────────────────────────────────
  /** Canlı katalog. Koda gömülü liste bir model kalkınca yalan söylerdi. */
  'models:catalog': { args: [force?: boolean]; result: ModelCatalogResult }
  'models:get': { args: []; result: ModelSelection }
  'models:set': { args: [role: ModelRole, model: string | null]; result: ModelSelection }

  // ── Başarısız kayıt kuyruğu ────────────────────────────────────────────
  'queue:list': { args: []; result: QueueList }
  /** Bekleyen kayıtları yeniden gönderir. Sonuç yapıştırılmaz, geçmişe yazılır. */
  'queue:flush': { args: []; result: QueueFlushResult }
  'queue:remove': { args: [id: string]; result: QueueList }
  'queue:clear': { args: []; result: QueueList }

  // ── Gizlilik ───────────────────────────────────────────────────────────
  'privacy:get': { args: []; result: PrivacyState }
  'privacy:set-masking': { args: [enabled: boolean]; result: PrivacyState }
  /** Sessizlikte otomatik durdurma eşiği; 0 kapatır. */
  'dictation:set-auto-stop': { args: [seconds: number]; result: PrivacyState }

  // ── Mikrofon ───────────────────────────────────────────────────────────
  'audio:list-devices': { args: []; result: AudioDeviceList }
  'audio:set-device': { args: [device: number | null]; result: AudioDeviceList }
  /**
   * Ses aygıtları değişti (Faz 7.6).
   *
   * Sinyal renderer'dan geliyor: motor tarafında yoklama yapmak mümkün
   * değil, çünkü PortAudio'nun aygıt listesini tazelemek kütüphaneyi
   * yeniden başlatıyor ve açık akışları geçersiz kılıyor.
   */
  'audio:devices-changed': { args: []; result: { applied: boolean } }

  // ── Veri ───────────────────────────────────────────────────────────────
  'stats:get': { args: []; result: EngineStats }
  'vault:list': { args: []; result: VaultEntry[] }
  /**
   * Geçmişte tam metin arama (Faz 6.2).
   *
   * Boş sorgu son kayıtları döndürür — arama kutusu temizlenince liste
   * boş kalmasın.
   */
  'history:search': { args: [query: string]; result: { items: HistoryRow[] } }
  /**
   * Geçmişteki bir kaydı panoya kopyalar (Faz 7.12).
   *
   * Dikte akışının aksine hedef pencere yok: kullanıcı arama ekranında,
   * yani odakta OmniVoice var. Metin panoya yazılıyor ve kullanıcı istediği
   * yere Ctrl+V ile koyuyor.
   */
  'history:copy': { args: [recordId: number]; result: { ok: boolean; chars: number } }
  /**
   * Tüm geçmişi dosyaya aktarır (Faz 7.14).
   *
   * `saved: false` kullanıcının kaydetme penceresini iptal ettiği anlamına
   * gelir; hata değil, bu yüzden ayrı bir alan.
   */
  'history:export': {
    args: [format: 'markdown' | 'json']
    result: { saved: boolean; count: number; path: string | null }
  }
}

/**
 * Main process'in renderer'a kendiliğinden gönderdiği olaylar (tek yön).
 */
export interface IpcEventMap {
  'engine:state-changed': EngineState
  'window:maximize-changed': boolean
  'app:locale-changed': Locale
  'dictation:changed': DictationState
  /**
   * Sesli arama sorgusu hazır (Faz 7.13).
   *
   * Ana pencere bunu alınca geçmiş ekranına geçip kutuyu dolduruyor.
   */
  'history:query': string
  'meeting:changed': MeetingState
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

export type WindowSurface = 'main' | 'hud' | 'commandbar' | 'region'
