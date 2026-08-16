/**
 * Faz 1 örnek verisi.
 *
 * Arayüzü motordan bağımsız geliştirmek için var. Faz 2'de bu modülün yerini
 * motordan gelen gerçek veri alacak; ekran bileşenleri değişmeyecek çünkü
 * hepsi aşağıdaki tiplerden okuyor.
 *
 * Örnek dikte metinleri gerçek kullanıcı içeriğini temsil eder, bu yüzden
 * arayüz sözlüğünde değil burada durur ve dile göre değişir.
 */

import type { Locale } from '@shared/ipc'
import type { MessageKey } from '../i18n/tr'

export type ModuleId = 'audio' | 'prompt' | 'meeting' | 'system' | 'automation' | 'vault'

/** Modül kimliğinin CSS değişkeni. Renk hep token'dan gelir, sabit yazılmaz. */
export const MODULE_COLOR: Record<ModuleId, string> = {
  audio: 'var(--mod-audio)',
  prompt: 'var(--mod-prompt)',
  meeting: 'var(--mod-meeting)',
  system: 'var(--mod-system)',
  automation: 'var(--mod-automation)',
  vault: 'var(--mod-vault)',
}

export interface ModuleEntry {
  id: ModuleId
  label: MessageKey
  count: string
}

export const MODULES: readonly ModuleEntry[] = [
  { id: 'audio', label: 'module.audio', count: '148' },
  { id: 'prompt', label: 'module.prompt', count: '31' },
  { id: 'meeting', label: 'module.meeting', count: '4' },
  { id: 'automation', label: 'module.automation', count: '12' },
  { id: 'vault', label: 'module.vault', count: '' },
]

// ── Panel ─────────────────────────────────────────────────────────────────

export interface Stat {
  label: MessageKey
  unit: MessageKey
  /**
   * Ham sayı. Binlik ayırıcı dile göre değiştiği için (tr: 4.812 · en: 4,812)
   * biçimlendirme arayüzde yapılır, veride değil.
   */
  value: number
  module: ModuleId
  /** Sparkline yükseklikleri, yüzde olarak. */
  spark: readonly number[]
}

export const STATS: readonly Stat[] = [
  {
    label: 'stat.words',
    unit: 'stat.words.unit',
    value: 4812,
    module: 'audio',
    spark: [38, 52, 44, 71, 60, 88, 96],
  },
  {
    label: 'stat.timeSaved',
    unit: 'stat.timeSaved.unit',
    value: 38,
    module: 'prompt',
    spark: [30, 41, 55, 48, 66, 74, 92],
  },
  {
    label: 'stat.fillers',
    unit: 'stat.fillers.unit',
    value: 214,
    module: 'automation',
    spark: [62, 48, 70, 55, 80, 66, 74],
  },
  {
    label: 'stat.latency',
    unit: 'stat.latency.unit',
    value: 1240,
    module: 'system',
    spark: [86, 78, 70, 74, 58, 52, 44],
  },
]

export interface FeedItem {
  id: string
  app: string
  tag: string
  tag2: string
  body: string
  time: string
  meta: string
  module: ModuleId
}

export interface ActionItem {
  id: string
  text: string
  owner: string
  due: string
  done: boolean
}

export interface MockContent {
  feed: readonly FeedItem[]
  actionItems: readonly ActionItem[]
  actionItemsSource: string
  scratchpad: readonly string[]
  vocabulary: readonly string[]
  vocabularyExtra: number
  engineDetail: string
  batteryModel: string
  meetingCount: number
}

const CONTENT: Record<Locale, MockContent> = {
  tr: {
    feed: [
      {
        id: 'f1',
        app: 'VS Code · api_router.py',
        tag: 'KOD MODU',
        tag2: '{SelectedText} 42 satır',
        body: '“şu handler’ı async yap, hataları tek yerde topla” — refactor + docstring üretildi, biçim korunarak yapıştırıldı.',
        time: '14:38',
        meta: 'deepseek-v3 · 1.9 sn',
        module: 'prompt',
      },
      {
        id: 'f2',
        app: 'Teams · Sprint planlama',
        tag: 'LOOPBACK · 3 KONUŞMACI',
        tag2: 'PII 2 alan maskelendi',
        body: '6 action item çıkarıldı, sorumlular etiketlendi; özet webhook ile Notion’a gönderildi.',
        time: '13:05',
        meta: '48 dk kayıt',
        module: 'meeting',
      },
      {
        id: 'f3',
        app: 'Slack · #urun-ekibi',
        tag: 'HIZLI DİKTE',
        tag2: 'ton: profesyonel',
        body: '“yarına kadar demoyu hazırlayamayız, pazartesi diyelim” — nazik ve net mesaja çevrildi, 9 dolgu kelime ayıklandı.',
        time: '11:52',
        meta: 'whisper turbo · 1.1 sn',
        module: 'audio',
      },
      {
        id: 'f4',
        app: 'Terminal · omnivoice-core',
        tag: 'GIT COMMIT',
        tag2: 'git diff · 31 satır',
        body: 'feat(stt): add circular pre-roll buffer to capture leading syllable',
        time: '10:20',
        meta: 'haiku · 0.9 sn',
        module: 'automation',
      },
    ],
    actionItems: [
      {
        id: 'a1',
        text: 'Loopback izin akışını Deniz test edecek',
        owner: 'Deniz',
        due: 'Çar',
        done: false,
      },
      { id: 'a2', text: 'Sözlüğe 12 mühendislik terimi', owner: 'Ela', due: '', done: false },
      { id: 'a3', text: 'HUD gecikme ölçümü paylaşıldı', owner: '', due: '', done: true },
    ],
    actionItemsSource: 'Sprint planlama',
    scratchpad: [
      'Prompt linter’a rol tanımı kontrolü ekle',
      'A/B sonuçlarını CSV’ye çıkart',
      'Pil modunda model düşerken uyarı ver',
    ],
    vocabulary: ['faster-whisper', 'diarization', 'Kayseri'],
    vocabularyExtra: 9,
    engineDetail: 'groq whisper-large-v3-turbo · pre-roll 1000 ms · sözlük 148 terim · LLM claude-3.5-haiku',
    batteryModel: 'Whisper Turbo',
    meetingCount: 1,
  },

  en: {
    feed: [
      {
        id: 'f1',
        app: 'VS Code · api_router.py',
        tag: 'CODE MODE',
        tag2: '{SelectedText} 42 lines',
        body: '“make this handler async, collect errors in one place” — refactor + docstring generated, pasted with formatting preserved.',
        time: '14:38',
        meta: 'deepseek-v3 · 1.9 s',
        module: 'prompt',
      },
      {
        id: 'f2',
        app: 'Teams · Sprint planning',
        tag: 'LOOPBACK · 3 SPEAKERS',
        tag2: 'PII 2 fields masked',
        body: '6 action items extracted, owners tagged; summary sent to Notion via webhook.',
        time: '13:05',
        meta: '48 min recording',
        module: 'meeting',
      },
      {
        id: 'f3',
        app: 'Slack · #product-team',
        tag: 'QUICK DICTATION',
        tag2: 'tone: professional',
        body: '“we can’t get the demo ready by tomorrow, let’s say Monday” — turned into a polite, clear message, 9 fillers removed.',
        time: '11:52',
        meta: 'whisper turbo · 1.1 s',
        module: 'audio',
      },
      {
        id: 'f4',
        app: 'Terminal · omnivoice-core',
        tag: 'GIT COMMIT',
        tag2: 'git diff · 31 lines',
        body: 'feat(stt): add circular pre-roll buffer to capture leading syllable',
        time: '10:20',
        meta: 'haiku · 0.9 s',
        module: 'automation',
      },
    ],
    actionItems: [
      { id: 'a1', text: 'Deniz to test the loopback permission flow', owner: 'Deniz', due: 'Wed', done: false },
      { id: 'a2', text: 'Add 12 engineering terms to the vocabulary', owner: 'Ela', due: '', done: false },
      { id: 'a3', text: 'HUD latency measurement shared', owner: '', due: '', done: true },
    ],
    actionItemsSource: 'Sprint planning',
    scratchpad: [
      'Add role-definition check to the prompt linter',
      'Export A/B results to CSV',
      'Warn when the model drops in battery mode',
    ],
    vocabulary: ['faster-whisper', 'diarization', 'Kayseri'],
    vocabularyExtra: 9,
    engineDetail:
      'groq whisper-large-v3-turbo · pre-roll 1000 ms · vocabulary 148 terms · LLM claude-3.5-haiku',
    batteryModel: 'Whisper Turbo',
    meetingCount: 1,
  },
}

export function getContent(locale: Locale): MockContent {
  return CONTENT[locale]
}

// ── Ayarlar ───────────────────────────────────────────────────────────────

export type ProviderId = 'groq' | 'openrouter' | 'gemini' | 'hybrid'

/**
 * Sağlayıcının gizlilik sınıfı. `trains` olanlar arayüzde rozetle işaretlenir
 * (bkz. docs/ARCHITECTURE.md § Gizlilik sınıfı).
 */
export const PROVIDER_TRAINS_ON_DATA: Record<ProviderId, boolean> = {
  groq: false,
  openrouter: false,
  gemini: true,
  hybrid: false,
}

export interface VaultKey {
  id: string
  name: string
  masked: string | null
  /** Sağlayıcının ücretsiz katmanı veriyi eğitimde kullanıyor mu? */
  trainsOnData?: boolean
}

export const VAULT_KEYS: readonly VaultKey[] = [
  { id: 'openrouter', name: 'OpenRouter', masked: 'sk-or-•••• 0906' },
  { id: 'groq', name: 'Groq', masked: 'gsk_•••• ZUY1' },
  // Gemini hiçbir moda atanmamış olsa da kasada duruyor; uyarı burada görünmeli
  // ki kullanıcı anahtarın ne olduğunu görünce riski de görsün.
  { id: 'gemini', name: 'Gemini', masked: 'AQ.Ab•••• uJg', trainsOnData: true },
  { id: 'webhook', name: 'Webhook (Notion)', masked: null },
]
