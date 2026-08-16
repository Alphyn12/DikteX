import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { app } from 'electron'

/**
 * Geliştirmede depo kökündeki `.env.local` dosyasını okur.
 *
 * Bilerek bağımlılıksız: main process'in ihtiyacı yalnız birkaç ayar değeri.
 * API anahtarları buradan **okunmaz ve kullanılmaz** — onları yalnız Python
 * motoru görür (bkz. ARCHITECTURE.md § Gizli bilgi yönetimi). Anahtarların
 * renderer'a sızmaması için main process onları hiç eline almaz.
 */
export function loadEnv(): Record<string, string> {
  if (app.isPackaged) return {}

  const repoRoot = join(app.getAppPath(), '..', '..')
  const file = join(repoRoot, '.env.local')
  if (!existsSync(file)) return {}

  const allowed = new Set(['OMNIVOICE_ENGINE_PORT'])
  const result: Record<string, string> = {}

  for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    const separator = trimmed.indexOf('=')
    if (separator === -1) continue

    const key = trimmed.slice(0, separator).trim()
    if (!allowed.has(key)) continue

    result[key] = trimmed.slice(separator + 1).trim()
  }

  return result
}
