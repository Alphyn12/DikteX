import { BrowserWindow } from 'electron'
import type { EngineSupervisor } from './engine'
import { selectRegion } from './windows/regionWindow'
import {
  INITIAL_DICTATION_STATE,
  type DictationResult,
  type DictationState,
  type DictationStatus,
} from '@shared/ipc'

/**
 * Dikte durumunun main process tarafındaki tek kaynağı.
 *
 * Motordan gelen parçalı olayları (durum, seviye, ilerleme) tek bir duruma
 * birleştirir ve arayüze yayar. HUD ile ana pencere aynı durumu görür.
 */
export class DictationController {
  private state: DictationState = { ...INITIAL_DICTATION_STATE }

  constructor(
    private readonly engine: EngineSupervisor,
    private readonly onChange: (state: DictationState) => void,
  ) {
    engine.on('message', (message: unknown) => this.handleEngineMessage(message))

    // Motor bağlantısı koparsa arayüzde donmuş bir "dinliyor" kalmasın.
    engine.on('state', (engineState: { status: string }) => {
      if (engineState.status !== 'connected' && this.state.status !== 'idle') {
        this.reset()
      }
    })
  }

  getState(): DictationState {
    return { ...this.state }
  }

  private patch(changes: Partial<DictationState>): void {
    this.state = { ...this.state, ...changes }
    this.onChange(this.getState())
  }

  private reset(): void {
    this.patch({ ...INITIAL_DICTATION_STATE })
  }

  private handleEngineMessage(message: unknown): void {
    if (typeof message !== 'object' || message === null || !('type' in message)) return
    const event = message as Record<string, unknown>

    switch (event['type']) {
      case 'dictation:state':
        this.applyStatus(event)
        break

      case 'dictation:refine-listening':
        this.patch({ refine: event['listening'] ? 'listening' : 'idle' })
        break

      case 'dictation:refining':
        this.patch({ refine: 'working' })
        break

      case 'history:query':
        // Sesli arama sonucu (Faz 7.13). Yapıştırılmıyor; ana pencereye
        // gidiyor ve orada geçmiş ekranı açılıyor.
        broadcastHistoryQuery(String(event['query'] ?? ''))
        break

      case 'dictation:level':
        // Yalnız dinlerken anlamlı; geç gelen bir kare durumu bozmasın.
        if (this.state.status === 'listening') {
          this.patch({
            level: Number(event['level'] ?? 0),
            seconds: Number(event['seconds'] ?? 0),
            paused: Boolean(event['paused']),
          })
        }
        break

      case 'dictation:progress':
        this.patch({
          step: (event['step'] as DictationState['step']) ?? null,
          rawText: event['rawText'] ? String(event['rawText']) : this.state.rawText,
          fillersRemoved: Number(event['fillersRemoved'] ?? this.state.fillersRemoved),
          selectionChars: Number(event['selectionChars'] ?? this.state.selectionChars),
        })
        break

      case 'dictation:warning':
        this.patch({ warning: String(event['message'] ?? '') })
        break

      default:
        break
    }
  }

  private applyStatus(event: Record<string, unknown>): void {
    const status = String(event['status'] ?? event['state']) as DictationStatus

    switch (status) {
      case 'listening':
        // Duraklat/devam da `listening` durumu yayıyor. Oturumu sıfırlamamak
        // için ayırt ediyoruz: aksi hâlde duraklatmak süreyi ve uygulama
        // adını siler, kullanıcı kaydın baştan başladığını sanır.
        if (event['paused'] !== undefined && this.state.status === 'listening') {
          this.patch({ paused: Boolean(event['paused']) })
          break
        }
        this.patch({
          ...INITIAL_DICTATION_STATE,
          status,
          preRollSeconds: Number(event['preRollSeconds'] ?? 0),
          appName: event['appName'] ? String(event['appName']) : null,
          windowTitle: event['windowTitle'] ? String(event['windowTitle']) : null,
          mode: (event['mode'] as DictationState['mode']) ?? 'quick',
          profile: (event['profile'] as DictationState['profile']) ?? 'plain',
        })
        break

      case 'processing':
        this.patch({
          status,
          step: (event['step'] as DictationState['step']) ?? 'stt',
          level: 0,
        })
        break

      case 'preflight':
        this.patch({
          status,
          step: null,
          result: (event['result'] as DictationResult | undefined) ?? null,
          // Düzeltme bitti; göstergeyi sıfırlıyoruz. Kalırsa kullanıcı
          // hâlâ çalışıyor sanır.
          refine: 'idle',
        })
        break

      case 'silent':
        this.patch({
          status,
          level: 0,
          deadMicrophone: Boolean(event['deadMicrophone']),
          seconds: Number(event['seconds'] ?? this.state.seconds),
        })
        break

      case 'clipboard':
        this.patch({
          status,
          level: 0,
          // `message` burada hata değil, SEBEP: neden doğrudan
          // yapıştırılamadığını kullanıcıya anlatıyor.
          warning: event['message'] ? String(event['message']) : null,
          clipboardChars: Number(event['chars'] ?? 0),
        })
        break

      case 'error':
        this.patch({ status, error: String(event['message'] ?? 'Bilinmeyen hata') })
        break

      case 'idle':
        this.reset()
        break

      default:
        break
    }
  }

  // ── Komutlar ──────────────────────────────────────────────────────────

  /**
   * Dikteyi başlatır veya bitirir.
   *
   * Ekran modu iki adımlı: önce bölge seçilir, sonra kayıt başlar. Bölge
   * seçimi kayıttan **önce** yapılmalı — kullanıcı konuşurken ekranda
   * dikdörtgen çizemez.
   */
  async toggle(mode = 'quick'): Promise<void> {
    // Kayıt sürüyorsa mod ne olursa olsun bitirme komutu gider.
    if (this.state.status === 'listening') {
      this.engine.send({ type: 'dictation:toggle', mode })
      return
    }

    if (mode === 'screen') {
      const region = await selectRegion()
      if (!region) return // kullanıcı iptal etti
      this.engine.send({ type: 'dictation:toggle', mode, region })
      return
    }

    this.engine.send({ type: 'dictation:toggle', mode })
  }

  /**
   * Kaydı duraklatır veya sürdürür (Faz 7.4).
   *
   * `cancel`in aksine iyimser güncelleme YOK: duraklamanın gerçekten olup
   * olmadığını yalnız motor bilir (kayıt bu arada bitmiş olabilir) ve yanlış
   * bir "duraklatıldı" göstergesi kullanıcıyı konuşmayı kesmeye iter.
   */
  togglePause(): void {
    if (this.state.status !== 'listening') return
    this.engine.send({ type: 'dictation:pause' })
  }

  /** Pre-flight'taki güncel metni motora bildirir (Faz 7.15). */
  setDraft(text: string): void {
    if (this.state.status !== 'preflight') return
    this.engine.send({ type: 'dictation:draft', text })
  }

  cancel(): void {
    // Arayüzü hemen serbest bırakıyoruz; motorun onayını beklemek iptali
    // yavaş hissettiriyor ve Esc'in anlık olması gerekiyor.
    this.engine.send({ type: 'dictation:cancel' })
    this.reset()
  }

  paste(text: string): void {
    this.engine.send({ type: 'dictation:paste', text })
  }
}

/** Durumu tüm pencerelere yayar. */
export function broadcastDictation(state: DictationState): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) window.webContents.send('dictation:changed', state)
  }
}

/**
 * Ana pencereyi getiren fonksiyon.
 *
 * `index.ts` kendi kapanışında tutuyor; buradan erişmek için enjekte
 * ediliyor. Pencereyi `getAllWindows()` içinde tahmin etmek yanlıştı —
 * HUD ve bölge kaplaması da birer `BrowserWindow` ve ayırt edici bir
 * özellikleri yok.
 */
let resolveMainWindow: (() => BrowserWindow) | null = null

export function setMainWindowResolver(resolver: () => BrowserWindow): void {
  resolveMainWindow = resolver
}

/**
 * Sesli arama sorgusunu ana pencereye taşır ve pencereyi öne getirir.
 *
 * Pencereyi göstermek şart: kullanıcı kısayola başka bir uygulamadayken
 * bastı ve sonucu görmek için OmniVoice'un önde olması gerekiyor. Diğer
 * modlarda bu yok — orada metin kullanıcının bulunduğu yere gidiyor.
 */
function broadcastHistoryQuery(query: string): void {
  if (!query.trim()) return

  const main = resolveMainWindow?.()
  if (main && !main.isDestroyed()) {
    main.webContents.send('history:query', query)
    if (!main.isVisible()) main.show()
    if (main.isMinimized()) main.restore()
    main.focus()
  }
}
