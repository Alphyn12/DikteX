/**
 * Türkçe metinler — referans dil.
 *
 * Bu dosya sözlüğün şeklini belirler; diğer diller bundan tip alır, böylece
 * eksik veya fazla anahtar derleme zamanında hata verir.
 *
 * Burada yalnız **arayüz metinleri** bulunur. Örnek dikte içerikleri gerçek
 * kullanıcı verisini temsil eder ve `mock/data.ts` içinde durur.
 */
export const tr = {
  // ── Başlık çubuğu ────────────────────────────────────────────────────────
  'titlebar.minimize': 'Simge durumuna küçült',
  'titlebar.maximize': 'Ekranı kapla',
  'titlebar.restore': 'Önceki boyut',
  'titlebar.close': 'Kapat',

  // ── Gezinme ──────────────────────────────────────────────────────────────
  'nav.panel': 'Panel',
  'nav.settings': 'Ayarlar',
  'nav.modules': 'MODÜLLER',
  'nav.label': 'Ana gezinme',

  'module.audio': 'Ses & STT',
  'module.prompt': 'Prompt Stüdyosu',
  'module.meeting': 'Toplantılar',
  'module.automation': 'Otomasyon',
  'module.vault': 'Kasa & Gizlilik',

  'vault.unlocked': 'Kasa kilitli değil',
  'vault.locked': 'Kasa kilitli',
  'vault.summary': '{count} anahtar Credential Manager’da · PII maskeleme açık',

  // ── Panel ────────────────────────────────────────────────────────────────
  'panel.title': 'Bugün',
  'panel.subtitle': '{dictations} dikte · {apps} uygulama · {meetings} toplantı',
  'panel.startDictation': 'Dikte başlat',
  'panel.recordMeeting': 'Toplantı kaydı',

  'stat.words': 'DİKTE EDİLEN',
  'stat.words.unit': 'kelime',
  'stat.timeSaved': 'KAZANILAN SÜRE',
  'stat.timeSaved.unit': 'dakika',
  'stat.fillers': 'DOLGU TEMİZLENEN',
  'stat.fillers.unit': '“eee / ımm”',
  'stat.latency': 'ORT. GECİKME',
  'stat.latency.unit': 'ms',

  'engineStrip.title': 'Hibrit işleme · bulut',
  'engineStrip.note': 'ilk hece kaybı yok',

  'feed.title': 'Son dikteler',
  'feed.viewAll': 'Tümü · yerel SQLite arama',

  'aside.actionItems': 'ACTION ITEMS',
  'aside.scratchpad': 'SESLİ NOT DEFTERİ',
  'aside.vocabulary': 'SÖZLÜK ÖNERİLERİ',
  'aside.rawIdeas': '{count} ham fikir',
  'aside.compile': 'Gün sonu derle',
  'aside.vocabNote': 'Bu hafta {count} kez hatalı yazıldı.',
  'aside.batteryNotice':
    'Pil moduna geçildi — dinamik seçici {model}’a düştü.',
  'aside.undo': 'Geri al',

  // ── Ayarlar ──────────────────────────────────────────────────────────────
  'settings.eyebrow': 'AYARLAR',
  'settings.title': 'Modeller & Kısayollar',
  'settings.subtitle': 'Her mod kendi modelini, sağlayıcısını ve global kısayolunu taşır',

  'table.mode': 'MOD',
  'table.model': 'MODEL',
  'table.provider': 'SAĞLAYICI',
  'table.latency': 'GECİKME',
  'unit.seconds': 'sn',
  'latency.stream': 'akış',
  'table.shortcut': 'KISAYOL',
  'table.active': 'AKTİF',

  'mode.quickDictation': 'Hızlı dikte',
  'mode.megaPrompt': 'Mega-prompt · CoT',
  'mode.code': 'Kod & refactor',
  'mode.translate': 'EN çeviri',
  'mode.abCompare': 'A/B karşılaştırma',
  'mode.meetingSummary': 'Toplantı özeti',

  'provider.groq': 'Groq',
  'provider.openrouter': 'OpenRouter',
  'provider.gemini': 'Gemini',
  'provider.hybrid': 'Hibrit',

  'toggle.dynamicModel': 'Dinamik model seçici',
  'toggle.dynamicModel.desc': 'Pil / ağ durumuna göre model boyutları arasında anlık geçiş',
  'toggle.dynamicModel.meta': 'eşik %35 pil',
  'toggle.preflight': 'Pre-flight önizleme',
  'toggle.preflight.desc': 'Çıktı yapıştırılmadan önce düzenleme penceresi açılır',
  'toggle.preflight.meta': 'mega-prompt’ta zorunlu',
  'toggle.pii': 'PII maskeleme',
  'toggle.pii.desc': 'TC kimlik, kart no ve API anahtarı buluta gitmeden sansürlenir',
  'toggle.pii.badge': 'YEREL',

  'aside.chorded': 'CHORDED SHORTCUT',
  'aside.chorded.desc': 'Basılı tut → mod seç.',
  'aside.chorded.legend': '{k} kod, {e} İngilizce, {m} mega-prompt.',
  'aside.chorded.status': 'çakışma yok · {count} mod bağlı',
  'aside.apiVault': 'API KASASI',
  'aside.addKey': 'ekle',
  'aside.localServer': 'YEREL SUNUCU',
  'aside.localServer.desc': 'REST + webhook açık — dış betikler motoru tetikleyebilir.',

  'training.badge': 'eğitime açık',
  'training.tooltip':
    'Bu sağlayıcının ücretsiz katmanı gönderilen veriyi model eğitiminde kullanır. Hassas içerik yönlendirmeyin.',

  // ── Motor durumu ─────────────────────────────────────────────────────────
  'engine.starting': 'Motor başlatılıyor',
  'engine.connected': 'Motor bağlı',
  'engine.disconnected': 'Motor bağlantısı koptu',
  'engine.failed': 'Motor başlatılamadı',
  'engine.retry': 'Yeniden dene',
  'engine.retrying': 'Yeniden bağlanılıyor',
  'engine.port': 'port',

  // ── Tepsi menüsü ─────────────────────────────────────────────────────────
  'tray.show': 'OmniVoice’u göster',
  'tray.startDictation': 'Dikte başlat',
  'tray.quit': 'Çıkış',

  // ── Genel ────────────────────────────────────────────────────────────────
  'lang.switch': 'Dil',
  'common.mockNotice': 'Örnek veri — motor Faz 2’de bağlanacak',
} as const

export type MessageKey = keyof typeof tr
export type Messages = Record<MessageKey, string>
