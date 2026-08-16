import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { app } from 'electron'
import type { EngineState, EngineStatus } from '@shared/ipc'

/**
 * Python motorunun süreç süpervizörü.
 *
 * Motor ayrı bir süreçte çalışır; çökerse arayüz ayakta kalır ve süpervizör
 * onu geri getirir. Arayüz motora doğrudan değil, hep bu sınıf üzerinden bakar.
 */

const MAX_RETRIES = 5
const BASE_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 8_000
const HANDSHAKE_TIMEOUT_MS = 15_000
/** İstek/yanıt zaman aşımı. STT + LLM zinciri birkaç saniye sürebilir. */
const REQUEST_TIMEOUT_MS = 30_000

interface PendingRequest {
  resolve: (value: unknown) => void
  timer: NodeJS.Timeout
}

export interface EngineOptions {
  port: number
}

export class EngineSupervisor extends EventEmitter {
  private child: ChildProcess | null = null
  private socket: WebSocket | null = null
  private retryTimer: NodeJS.Timeout | null = null
  private handshakeTimer: NodeJS.Timeout | null = null
  private readonly pending = new Map<string, PendingRequest>()
  private requestCounter = 0
  /** Uygulama kapanırken yeniden başlatmayı bastırır. */
  private shuttingDown = false

  private state: EngineState

  constructor(private readonly options: EngineOptions) {
    super()
    this.state = {
      status: 'starting',
      version: null,
      port: options.port,
      error: null,
      retries: 0,
    }
  }

  getState(): EngineState {
    return { ...this.state }
  }

  private setState(patch: Partial<EngineState>): void {
    const next = { ...this.state, ...patch }
    // Aynı durumu iki kez yaymanın anlamı yok.
    if (
      next.status === this.state.status &&
      next.version === this.state.version &&
      next.error === this.state.error &&
      next.retries === this.state.retries
    ) {
      return
    }
    this.state = next
    this.emit('state', this.getState())
  }

  /**
   * Geliştirmede depodaki sanal ortamı, ürün sürümünde paketlenmiş motoru
   * çalıştırır. Sanal ortam yoksa bunu net bir hata olarak bildirir — sessizce
   * sistem Python'una düşmek, yanlış bağımlılıklarla çalışıp anlaşılmaz
   * hatalar üretmekten kötüdür.
   */
  private resolveCommand(): { command: string; args: string[]; cwd: string } | { error: string } {
    if (app.isPackaged) {
      const exe = join(process.resourcesPath, 'engine', 'omnivoice-engine.exe')
      if (!existsSync(exe)) {
        return { error: `Paketlenmiş motor bulunamadı: ${exe}` }
      }
      return { command: exe, args: [], cwd: join(process.resourcesPath, 'engine') }
    }

    // apps/desktop/out/main → depo kökü
    const repoRoot = join(app.getAppPath(), '..', '..')
    const engineDir = join(repoRoot, 'engine')
    const venvPython = join(engineDir, '.venv', 'Scripts', 'python.exe')

    if (!existsSync(venvPython)) {
      return {
        error:
          'Motorun sanal ortamı kurulu değil. Depo kökünde şunu çalıştırın:\n' +
          '  npm run engine:install',
      }
    }
    return { command: venvPython, args: ['-m', 'omnivoice_engine'], cwd: engineDir }
  }

  start(): void {
    if (this.child) return
    this.shuttingDown = false

    const resolved = this.resolveCommand()
    if ('error' in resolved) {
      this.setState({ status: 'failed', error: resolved.error })
      return
    }

    this.setState({ status: 'starting', error: null })

    const child = spawn(resolved.command, resolved.args, {
      cwd: resolved.cwd,
      env: {
        ...process.env,
        OMNIVOICE_ENGINE_PORT: String(this.options.port),
        // Python'un stdout'u tamponlaması, günlüklerin geç görünmesine yol açar.
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1',
      },
      windowsHide: true,
    })
    this.child = child

    child.stdout?.on('data', (d: Buffer) => forwardLog('motor', d))
    child.stderr?.on('data', (d: Buffer) => forwardLog('motor!', d))

    child.on('error', (err) => {
      this.setState({ status: 'failed', error: `Motor başlatılamadı: ${err.message}` })
    })

    child.on('exit', (code, signal) => {
      this.child = null
      this.closeSocket()
      if (this.shuttingDown) return
      const reason = signal ? `sinyal ${signal}` : `çıkış kodu ${code}`
      this.scheduleRetry(`Motor süreci sonlandı (${reason})`)
    })

    this.connect()
  }

  /**
   * Motora WebSocket ile bağlanır. Süreç henüz dinlemeye başlamamış olabilir;
   * bu yüzden bağlantı hatası ölümcül değil, yeniden denenir.
   */
  private connect(): void {
    this.closeSocket()

    const url = `ws://127.0.0.1:${this.options.port}/ws`
    let socket: WebSocket
    try {
      socket = new WebSocket(url)
    } catch (err) {
      this.scheduleRetry(`Bağlantı kurulamadı: ${String(err)}`)
      return
    }
    this.socket = socket

    this.handshakeTimer = setTimeout(() => {
      if (this.state.status !== 'connected') {
        socket.close()
        this.scheduleRetry('Motor el sıkışma süresinde yanıt vermedi')
      }
    }, HANDSHAKE_TIMEOUT_MS)

    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'hello', client: 'desktop', version: app.getVersion() }))
    })

    socket.addEventListener('message', (event) => {
      let msg: unknown
      try {
        msg = JSON.parse(String(event.data))
      } catch {
        return // Bozuk kare — yok say, bağlantıyı düşürme.
      }
      this.handleMessage(msg)
    })

    socket.addEventListener('close', () => {
      this.clearHandshakeTimer()
      if (this.shuttingDown || this.socket !== socket) return
      // Süreç hâlâ ayaktaysa yalnız soket düştü; yeniden bağlan.
      if (this.child) this.scheduleRetry('Motor bağlantısı koptu')
    })

    socket.addEventListener('error', () => {
      // 'close' zaten arkasından gelir; burada yeniden deneme kurmuyoruz ki
      // aynı olay için iki zamanlayıcı kurulmasın.
    })
  }

  private handleMessage(msg: unknown): void {
    if (typeof msg !== 'object' || msg === null || !('type' in msg)) return
    const message = msg as { type: unknown; id?: unknown }

    if (message.type === 'ready') {
      const version = 'version' in msg ? String((msg as { version: unknown }).version) : null
      this.clearHandshakeTimer()
      this.setState({ status: 'connected', version, error: null, retries: 0 })
      return
    }

    // İstek/yanıt: `id` taşıyan bir kare bekleyen çağrıyı çözer.
    if (typeof message.id === 'string') {
      const pending = this.pending.get(message.id)
      if (pending) {
        this.pending.delete(message.id)
        clearTimeout(pending.timer)
        pending.resolve(msg)
        return
      }
    }

    this.emit('message', msg)
  }

  /**
   * Motora tek yönlü komut gönderir.
   *
   * Bağlantı yoksa sessizce düşer: kısayola motor kapalıyken basmak hata
   * penceresi açmamalı, arayüzdeki durum çubuğu zaten sorunu gösteriyor.
   */
  send(message: Record<string, unknown>): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      log(`komut gönderilemedi (motor bağlı değil): ${String(message['type'])}`)
      return false
    }
    this.socket.send(JSON.stringify(message))
    return true
  }

  /**
   * Motora istek gönderir ve yanıtını bekler.
   *
   * Her istek benzersiz bir `id` taşır; motor yanıtta aynı `id`'yi geri
   * yansıtır. Zaman aşımına uğrayan istekler reddedilir ki arayüz sonsuza
   * kadar beklemesin.
   */
  request<T = unknown>(
    message: Record<string, unknown>,
    { timeoutMs = REQUEST_TIMEOUT_MS }: { timeoutMs?: number } = {},
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        reject(new Error('Motor bağlı değil'))
        return
      }

      const id = `r${++this.requestCounter}`
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Motor yanıt vermedi: ${String(message['type'])}`))
      }, timeoutMs)

      this.pending.set(id, { resolve: resolve as (value: unknown) => void, timer })
      this.socket.send(JSON.stringify({ ...message, id }))
    })
  }

  private scheduleRetry(reason: string): void {
    if (this.shuttingDown || this.retryTimer) return

    const retries = this.state.retries + 1
    if (retries > MAX_RETRIES) {
      this.setState({
        status: 'failed',
        error: `${reason}. ${MAX_RETRIES} denemeden sonra vazgeçildi.`,
        retries,
      })
      return
    }

    // Üstel geri çekilme — çöküp duran bir süreci saniyede onlarca kez
    // başlatmaya çalışmak makineyi kilitler.
    const delay = Math.min(BASE_BACKOFF_MS * 2 ** (retries - 1), MAX_BACKOFF_MS)
    this.setState({ status: 'disconnected', error: reason, retries })

    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      if (this.shuttingDown) return
      if (this.child) this.connect()
      else this.start()
    }, delay)
  }

  /** Kullanıcının elle yeniden başlatması — deneme sayacını sıfırlar. */
  restart(): EngineState {
    this.stop()
    this.setState({ retries: 0, error: null })
    this.start()
    return this.getState()
  }

  stop(): void {
    this.shuttingDown = true
    this.clearRetryTimer()
    this.clearHandshakeTimer()
    this.closeSocket()
    if (this.child) {
      this.child.kill()
      this.child = null
    }
  }

  private closeSocket(): void {
    // Bekleyen istekler bağlantıyla birlikte düşer; yoksa çağıranlar
    // zaman aşımına kadar asılı kalır.
    for (const [, pending] of this.pending) {
      clearTimeout(pending.timer)
    }
    this.pending.clear()

    if (!this.socket) return
    const socket = this.socket
    this.socket = null
    try {
      socket.close()
    } catch {
      // Zaten kapalı olabilir; önemli değil.
    }
  }

  private clearRetryTimer(): void {
    if (this.retryTimer) {
      clearTimeout(this.retryTimer)
      this.retryTimer = null
    }
  }

  private clearHandshakeTimer(): void {
    if (this.handshakeTimer) {
      clearTimeout(this.handshakeTimer)
      this.handshakeTimer = null
    }
  }
}

function forwardLog(tag: string, data: Buffer): void {
  const text = data.toString('utf8').trimEnd()
  if (text) console.log(`[${tag}] ${text}`)
}

function log(message: string): void {
  console.log(`[motor] ${message}`)
}
