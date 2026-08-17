/**
 * Dikte protokolü — Python motoru ile paylaşılan sözleşme.
 *
 * Motor tarafındaki karşılığı `omnivoice_engine/pipeline/dictation.py`.
 * Alan adları oradaki `to_payload()` çıktısıyla birebir aynı olmalı.
 */

export type DictationStatus =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'preflight'
  /** Kayıtta konuşma yoktu. Hata değil ama kullanıcıya söylenmeli. */
  | 'silent'
  /**
   * Doğrudan yapıştırılamadı; metin panoda bekliyor.
   *
   * Ayrı bir durum çünkü HUD `idle` olunca kapanıyor. Kullanıcıya Ctrl+V'ye
   * basması gerektiğini söylemeden kaybolursak metnin yok olduğunu sanır.
   */
  | 'clipboard'
  | 'error'

/** Dikte modları — motor tarafındaki `ModeId` ile birebir aynı. */
export type ModeId =
  | 'quick'
  | 'code'
  | 'translate_en'
  | 'mega_prompt'
  | 'image_prompt'
  | 'sql'
  | 'commit'

/** Aktif uygulamanın çıktı profili — `context/apps.py` ile aynı. */
export type OutputProfile =
  | 'code'
  | 'chat'
  | 'document'
  | 'terminal'
  | 'spreadsheet'
  | 'email'
  | 'browser'
  | 'plain'

/** Pre-flight'ta gösterilen sonuç. Tüm ölçümler gerçek, tahmin yok. */
export interface DictationResult {
  rawText: string
  finalText: string
  fillersRemoved: number
  language: string | null
  sttProvider: string
  sttModel: string
  sttMs: number
  llmProvider: string | null
  llmModel: string | null
  llmMs: number
  totalMs: number
  costUsd: number
  audioSeconds: number
  appName: string | null
  windowTitle: string | null
  recordId: number | null
  mode: ModeId
  profile: OutputProfile
  /** Seçili metnin uzunluğu; 0 ise seçim kullanılmadı. */
  selectionChars: number
  /** Doldurulan dinamik değişkenler ({SelectedText} gibi). */
  variables: string[]
  /** Sesle istenen yapıştırma biçimi; `null` ise dönüşüm yok. */
  pasteFormat: PasteFormat | null
  /**
   * Tetiklenen snippet'in adı.
   *
   * Pre-flight'ta gösterilmesi şart: eşleşme bulanık olduğu için yanlış
   * şablon tetiklenebilir ve kullanıcı bunu yalnız çıktıya bakarak anlar.
   */
  snippet: string | null
  /**
   * Buluta gitmeden önce maskelenen hassas değer sayısı.
   *
   * Sıfırdan büyükse pre-flight'ta rozet çıkıyor: kullanıcı neyin
   * gizlendiğini yapıştırmadan önce bilmeli.
   */
  piiMasked: number
}

/** Yapıştırma biçimi — motordaki `PasteFormat` ile birebir. */
export type PasteFormat =
  | 'plain'
  | 'markdown'
  | 'plain_from_markdown'
  | 'json_string'
  | 'html'
  | 'code_block'

/** Bir dikte modunun tanımı. */
export interface ModeInfo {
  id: ModeId
  /** Kısayolun mod harfi (K, E, M…). */
  chordKey: string | null
  /** Renk kimliği (bkz. DESIGN-TOKENS.md § 2). */
  module: string
  /** Bu moda özel model; `null` ise varsayılan kullanılır. */
  model: string | null
  requirePreflight: boolean
  usesSelection: boolean
  /** Electron tarafında kaydedilen global kısayol. */
  accelerator?: string
  /** Kısayol başka bir uygulama tarafından kapılmış mı? */
  conflicted?: boolean
}

export interface ModeList {
  modes: ModeInfo[]
  defaultModel: string
}

// ── Sözlük ──────────────────────────────────────────────────────────────

export interface VocabularyTerm {
  text: string
  misspelled: number
  suggested: boolean
}

export interface VocabularyList {
  path: string
  terms: VocabularyTerm[]
  confirmedCount: number
  suggestionCount: number
}

// ── Gizlilik ────────────────────────────────────────────────────────────

export interface PrivacyState {
  /** Hassas veri maskeleme açık mı. */
  maskPii: boolean
  /**
   * Konuşma tanıma ayağı korunuyor mu — **her zaman `false`**.
   *
   * Maskeleme metin üzerinde çalışıyor, ama STT'ye giden şey ses. Metin
   * oradan geliyor, yani maskelenecek bir şey henüz yok. Arayüz bunu
   * kullanıcıya söylemek zorunda: "korunuyorsun" demek yanlış olurdu.
   */
  sttCovered: boolean
  /** LLM ayağı korunuyor mu — asıl sızıntı yolu burası. */
  llmCovered: boolean
  /**
   * Kaydı bitiren sessizlik süresi; 0 ise otomatik durdurma kapalı (Faz 7.3).
   *
   * Gizlilik durumuyla aynı mesajda taşınıyor çünkü ikisi de motorun canlı
   * ayarları; ayrı bir tur atmanın karşılığı yok.
   */
  autoStopSeconds: number
}

// ── Uygulama başına mod (Faz 7.5) ───────────────────────────────────────

export interface AppModeMap {
  /** Süreç adı (küçük harf, `.exe` eki atılmış) → mod kimliği. */
  modes: Record<string, ModeId>
  /**
   * O an odaktaki uygulama.
   *
   * Kullanıcının süreç adını (`Code.exe`) elle yazması beklenemez; arayüz
   * "şu an açık olanı ekle" diyebilmeli.
   */
  focused: { process: string; name: string } | null
}

// ── Model kataloğu (Faz 3.15) ───────────────────────────────────────────

/** OpenRouter kataloğundan gelen bir model. */
export interface CatalogModel {
  id: string
  name: string
  /** 1M jeton başına dolar; `null` ise bilinmiyor (tahmin uydurulmuyor). */
  inputPrice: number | null
  outputPrice: number | null
  contextLength: number | null
  /** Görsel girdi kabul ediyor mu — ekran gözü modu bunu gerektiriyor. */
  supportsImages: boolean
  /** Kimlikteki `:` ekinden gelen varyant: `free`, `batch`, `thinking`. */
  variant: string | null
  /**
   * Anlık işler için kullanılabilir mi.
   *
   * `:batch` modelleri eşzamansız toplu işleme uç noktaları — dikte için
   * seçilirse hiçbir şey dönmez. Adları normalden yalnız iki nokta ile
   * ayrıldığı için arayüzün bunu göstermesi şart.
   */
  interactive: boolean
}

export type ModelRole = 'llm' | 'stt' | 'vision'

/** Bir rolün etkin modeli ve değerin nereden geldiği. */
export interface RoleModel {
  model: string
  /** `user` = kullanıcı seçti · `default` = dağıtım varsayılanı · `llm` = LLM'den miras. */
  source: 'user' | 'default' | 'llm'
}

export type ModelSelection = Record<ModelRole, RoleModel>

export interface ModelCatalogResult {
  models: CatalogModel[]
  /** Katalog alınamadıysa sebebi; liste boş ama sebep gösterilmeli. */
  error: string | null
}

// ── Başarısız kayıt kuyruğu ─────────────────────────────────────────────

/**
 * Diskte bekleyen bir kayıt.
 *
 * Bu kayıtlar kullanıcının **sesini** içeriyor — uygulamanın geri kalanının
 * bilinçli olarak yapmadığı bir şey. Arayüzde görünür olmaları şart: kullanıcı
 * neyin saklandığını bilmeli ve silebilmeli.
 */
export interface QueuedClip {
  id: string
  mode: ModeId
  /** Unix zamanı, saniye. */
  createdAt: number
  durationSeconds: number
  /** Kuyruğa girmesine sebep olan hata. */
  error: string
  attempts: number
}

export interface QueueList {
  directory: string
  items: QueuedClip[]
  count: number
}

/** Yeniden gönderme denemesinin sonucu. */
export interface QueueFlushResult extends QueueList {
  sent: number
  failed: number
  dropped: number
}

// ── Snippet kütüphanesi ─────────────────────────────────────────────────

export interface Snippet {
  name: string
  body: string
  /** Ada ek olarak eşleşen anahtar kelimeler. */
  triggers: string[]
  used: number
}

export interface SnippetList {
  path: string
  snippets: Snippet[]
}

/** HUD'un çizdiği tüm durum. */
export interface DictationState {
  status: DictationStatus
  /** Anlık ses seviyesi 0–1; yalnız `listening` sırasında anlamlı. */
  level: number
  /** Kayıt süresi, saniye. */
  seconds: number
  /** Ön bellekten alınan pre-roll süresi. */
  preRollSeconds: number
  /** İşleme sırasında hangi adımda olunduğu. */
  step: 'stt' | 'llm' | null
  /** İşleme sırasında elde edilen ham metin — kullanıcı ilerlemeyi görsün. */
  rawText: string | null
  fillersRemoved: number
  /** Dikte başladığında odakta olan uygulama. */
  appName: string | null
  windowTitle: string | null
  /** Hangi modda dikte edildiği. */
  mode: ModeId
  /** Aktif uygulamanın çıktı profili. */
  profile: OutputProfile
  /** Okunan seçili metnin uzunluğu. */
  selectionChars: number
  result: DictationResult | null
  error: string | null
  /** LLM atlandı gibi ölümcül olmayan uyarılar. */
  warning: string | null
  /**
   * `silent` durumunda mikrofonun tamamen ölü olup olmadığı.
   * Kısık ses ile hiç sinyal olmaması farklı sorunlar, farklı çözümler.
   */
  deadMicrophone: boolean
  /** `clipboard` durumunda panoda bekleyen karakter sayısı. */
  clipboardChars: number
  /**
   * Kayıt duraklatıldı mı (Faz 7.4).
   *
   * Ayrı bir `status` değil, `listening` içinde bir bayrak: HUD yerinde
   * kalmalı ve kullanıcı oturumun sürdüğünü görmeli. Ayrı bir durum yapmak
   * bitmiş bir kayıtla karıştırılırdı.
   */
  paused: boolean
}

export const INITIAL_DICTATION_STATE: DictationState = {
  status: 'idle',
  level: 0,
  seconds: 0,
  preRollSeconds: 0,
  step: null,
  rawText: null,
  fillersRemoved: 0,
  appName: null,
  windowTitle: null,
  mode: 'quick',
  profile: 'plain',
  selectionChars: 0,
  result: null,
  error: null,
  warning: null,
  deadMicrophone: false,
  clipboardChars: 0,
  paused: false,
}

// ── Mikrofon ────────────────────────────────────────────────────────────

export interface AudioDevice {
  index: number
  name: string
  hostApi: string
  channels: number
  sampleRate: number
  isSystemDefault: boolean
}

export interface AudioDeviceList {
  devices: AudioDevice[]
  /** Seçili aygıt; `null` ise sistem varsayılanı kullanılıyor. */
  current: number | null
  streaming: boolean
  /**
   * Aygıt değiştirilemediyse sebebi.
   *
   * Bunu arayüze taşımak şart: bir mikrofon başka bir uygulama tarafından
   * tutuluyor olabilir (örn. NVIDIA Broadcast fiziksel mikrofonu sahiplenir).
   * Hatayı yutarsak kullanıcı tıklar, hiçbir şey olmaz ve sebebini bilemez.
   */
  error?: string | null
}

// ── İstatistik ve harcama ───────────────────────────────────────────────

export interface TodayStats {
  dictations: number
  /** Bugün kaydedilen toplantı sayısı. */
  meetings: number
  apps: number
  fillers: number
  audio_seconds: number
  avg_ms: number
}

export interface SpendStats {
  todayUsd: number
  monthUsd: number
  totalUsd: number
  callCount: number
  budgetUsd: number
}

export interface EngineStats {
  today: TodayStats
  spend: SpendStats
}

// ── Kasa ────────────────────────────────────────────────────────────────

export interface VaultEntry {
  provider: string
  configured: boolean
  masked: string | null
}
