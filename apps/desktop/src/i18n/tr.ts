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
  'nav.history': 'Geçmiş',
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
  'panel.stopDictation': 'Dikteyi bitir',
  'stat.dictations': 'DİKTE',
  'stat.dictations.unit': 'bugün',
  'stat.audio': 'KAYDEDİLEN SES',
  'stat.audio.unit': 'saniye',
  'engineStrip.ready': 'Hazır · kısayolu bekliyor',
  'engineStrip.detail': 'groq whisper-large-v3-turbo · pre-roll 1000 ms · gemini-3.5-flash-lite',
  'feed.empty': 'Henüz dikte yok. Ctrl+Alt+Space ile başla.',
  'feed.pasted': 'yapıştırıldı',

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

  'style.title': 'KİŞİSEL STİL',
  'style.on': 'açık',
  'style.off': 'kapalı',
  'style.desc':
    'Pre-flight’ta yaptığınız düzeltmeler saklanır ve sonraki istemlere örnek olarak eklenir; model zamanla sizin gibi yazar.',
  'style.privacy':
    'Bu kip geçmiş dikte içeriğinizi yeni isteklere taşır — dün yazdığınız bir not, ' +
    'bugünkü diktenizin isteminde yer alabilir. Bu yüzden varsayılan olarak kapalı. ' +
    'Açıkken saklanan her örnek aşağıda görünür, hassas veriler maskelenir ve tek düğmeyle silinir.',
  'style.count': '{count} örnek saklı',
  'style.clear': 'hepsini sil',
  'style.empty': 'Henüz örnek yok — pre-flight’ta bir metni düzenleyin',
  'style.hint': 'İsteme en yeni {count} örnek ekleniyor.',

  'replace.title': 'OTOMATİK DÜZELTME',
  'replace.count': '{count} kural',
  'replace.find': 'Aranan',
  'replace.findPlaceholder': 'omni voice',
  'replace.replace': 'Yerine',
  'replace.replacePlaceholder': 'DikteX',
  'replace.wholeWord': 'Tam kelime ara (ekler korunur)',
  'replace.duplicate': 'Bu kural zaten var ya da aranan ile yerine aynı',
  'replace.empty': 'Henüz kural yok',
  'replace.remove': 'Kuralı sil',
  'replace.used': '{count}×',
  'replace.try': 'Dene',
  'replace.tryPlaceholder': 'bir cümle yaz, sonucu gör',
  'replace.hint':
    'Sözlükten farklı: sözlük konuşma tanımaya ipucu verir, buradaki kurallar ' +
    'kesin olarak uygulanır. Whisper bazı özel adları hep aynı biçimde yanlış ' +
    'yazıyorsa burada bir kez düzeltin.',

  'appModes.title': 'UYGULAMA BAŞINA MOD',
  'appModes.refresh': 'yenile',
  'appModes.empty': 'Henüz kural yok',
  'appModes.remove': 'Kuralı kaldır',
  'appModes.addFocused': 'Şu an açık: {app}',
  'appModes.pickMode': 'mod seç…',
  'appModes.hint':
    'Kural yalnız genel kısayolda (Ctrl+Alt+Space) uygulanır. Bir mod kısayoluna ' +
    'doğrudan bastığınızda seçiminiz korunur — kural onu ezmez.',

  'models.title': 'MODELLER',
  'models.provider': 'Sağlayıcı',
  'models.provider.openrouter': 'OpenRouter (ücretli · eğitime kapalı)',
  'models.provider.gemini': 'Gemini — doğrudan (ücretsiz · eğitime açık)',
  'models.provider.trainsWarning':
    'Gemini’nin ücretsiz katmanı gönderdiğiniz metni model eğitiminde kullanır. ' +
    'Aynı model OpenRouter üzerinden eğitime kapalıdır. Hassas içerik dikte ' +
    'ediyorsanız OpenRouter’ı tercih edin.',
  'models.provider.noKey': 'Bu sağlayıcının anahtarı yok — API KASASI’ndan ekleyin.',
  'models.role.llm': 'Metin işleme',
  'models.role.vision': 'Görsel (ekran gözü)',
  'models.source.user': 'seçildi',
  'models.source.default': 'varsayılan',
  'models.source.llm': 'metin modelinden',
  'models.useDefault': '— varsayılanı kullan —',
  'models.refresh': 'listeyi yenile',
  'models.loading': 'yükleniyor…',
  'models.price': '${input} / ${output} · 1M jeton (girdi / çıktı)',
  'models.priceUnknown': 'fiyat bilinmiyor',
  'models.batchWarning':
    'Bu bir toplu işleme (batch) modeli — istek kuyruğa alınır ve yanıt saatler sonra gelebilir. Dikte için uygun değil.',
  'models.hint':
    '{count} model listeleniyor. Liste OpenRouter’dan canlı çekiliyor; toplu işleme (batch) modelleri anlık dikteye uygun olmadığı için gizlendi.',
  'models.hintEmpty': 'Modelleri görmek için “listeyi yenile” deyin.',

  'queue.title': 'GÖNDERİLEMEYEN KAYITLAR',
  'queue.count': '{count} bekliyor',
  'queue.attempts': '{count} deneme',
  'queue.retry': 'Yeniden gönder',
  'queue.sending': 'Gönderiliyor…',
  'queue.clear': 'Hepsini sil',
  'queue.remove': 'Bu kaydı sil',
  'queue.flushResult': '{sent} gönderildi · {failed} bekliyor · {dropped} düşürüldü',
  'queue.privacyNote':
    'Bu kayıtların sesi geçici olarak diskte tutuluyor — uygulamanın normalde ' +
    'yapmadığı bir şey. Gönderilen kayıt hemen siliniyor; 7 günü geçen kendiliğinden ' +
    'düşüyor. Metin yapıştırılmaz, geçmişe yazılır.',

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
  'history.eyebrow': 'GEÇMİŞ',
  'history.title': 'Dikte Arama',
  'history.subtitle': 'Arama tamamen yerel — SQLite tam metin dizini, hiçbir şey buluta gitmez',
  'history.search': 'Geçmişte ara',
  'history.placeholder': 'kelime ara… (Türkçe karakter şart değil)',
  'history.clear': 'Aramayı temizle',
  'history.searching': 'aranıyor…',
  'history.results': '{count} kayıt',
  'history.empty': 'Henüz dikte yok',
  'history.noMatch': 'Eşleşen kayıt bulunamadı',
  'history.export': 'Dışa aktar',
  'history.exportMd': 'Markdown',
  'history.exportJson': 'JSON',
  'history.exported': '{count} kayıt kaydedildi',
  'history.exportNote':
    'Dışa aktarılan dosya ham metni içerir — maskeleme uygulanmaz. Dosyayı başka bir yere taşırsanız içinde ne olduğunu bilin.',
  'history.copy': 'Panoya kopyala',
  'history.copied': 'Kopyalandı — Ctrl+V',
  'history.delete': 'Sil',
  'history.deleteConfirm': 'Silinsin mi?',
  'history.cancel': 'Vazgeç',
  'history.deleteAll': 'Tümünü sil',
  'history.deleteAllConfirm': 'Tüm geçmiş silinsin mi?',
  'history.deletedAll': '{count} kayıt silindi',
  'history.copyFailed': 'Pano kilitli — başka bir uygulama kullanıyor olabilir',

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


  'provider.groq': 'Groq',
  'provider.openrouter': 'OpenRouter',
  'provider.gemini': 'Gemini',
  'provider.hybrid': 'Hibrit',

  'toggle.preflight': 'Pre-flight önizleme',
  'toggle.preflight.desc': 'Çıktı yapıştırılmadan önce düzenleme penceresi açılır',
  'toggle.preflight.meta': 'mega-prompt’ta zorunlu',
  'toggle.autoStop': 'Sessizlikte otomatik bitir',
  'toggle.autoStop.desc':
    'Konuştuktan sonra sessizlik sürerse kayıt kendiliğinden biter — klavyeye dönmeye gerek kalmaz',
  'toggle.autoStop.meta': 'eşik {seconds} sn',
  'toggle.autostart': 'Windows açılışında başlat',
  'toggle.autostart.desc':
    'Uygulama tepsiye inmiş olarak açılır; pencere açılmaz, kısayollar hazır olur.',
  'toggle.autostart.meta': 'tepsiye iner',
  'toggle.autostart.dev': 'yalnız kurulu sürümde',
  'toggle.numbers': 'Sayıları rakama çevir',
  'toggle.numbers.desc':
    '“on beş dakika” → “15 dakika”. Yerel ve belirlenimci; sıra sayıları (“birinci”) değişmez.',
  'toggle.numbers.meta': 'yerel',
  'toggle.ptt': 'Basılı tut (bas-konuş)',
  'toggle.ptt.desc':
    'Ctrl+Alt+Space basılı tutulduğu sürece kaydeder, bırakınca biter. Kapalıyken aç/kapa çalışır.',
  'toggle.ptt.meta': 'klavye kancası kurar',
  'toggle.ptt.failed': 'Kanca kurulamadı — bir güvenlik yazılımı engelliyor olabilir.',
  'toggle.ptt.privacy':
    'Bu kip düşük seviyeli bir klavye kancası kurar ve o kanca sistemdeki tüm tuşları görür. ' +
    'DikteX yalnız Ctrl, Alt ve Boşluk tuşlarının basılı olup olmadığını izler; başka hiçbir ' +
    'tuş saklanmaz, günlüğe yazılmaz ve hiçbir tuş yutulmaz. Kip kapalıyken kanca hiç kurulmaz.',
  'toggle.pii': 'PII maskeleme',
  'toggle.pii.desc':
    'TC kimlik, kart no, IBAN ve API anahtarı metin işlemeye gitmeden sansürlenir',
  'toggle.pii.limit':
    'Ses kaydı konuşma tanımaya maskelenmeden gider — maskelenecek metin oradan geliyor. Bir parolayı sesli okursan o ses sağlayıcıya ulaşır.',
  'toggle.pii.badge': 'YEREL',

  'aside.chorded': 'CHORDED SHORTCUT',
  'aside.chorded.desc': 'Basılı tut → mod seç.',
  'aside.chorded.legend': '{k} kod, {e} İngilizce, {m} mega-prompt.',
  'aside.chorded.status': 'çakışma yok · {count} mod bağlı',
  'aside.apiVault': 'API KASASI',
  'aside.addKey': 'ekle',
  'aside.noKey': 'anahtar yok',
  'aside.vaultLoading': 'kasa okunuyor…',
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
  'tray.show': 'DikteX’i göster',
  'tray.startDictation': 'Dikte başlat',
  'tray.quit': 'Çıkış',

  // ── HUD ──────────────────────────────────────────────────────────────────
  'hud.listening': 'Dinliyor',
  'hud.preRoll': 'ön bellekten {seconds} sn alındı',
  'hud.quickDictation': 'HIZLI DİKTE',
  'hud.escCancel': 'Esc iptal',
  'hud.stopHint': 'Bitir: aynı kısayol · Duraklat: Ctrl+Alt+P · İptal: Ctrl+Alt+Esc',
  'hud.paused': 'Duraklatıldı',
  'hud.paused.hint': 'kayıt bekliyor — duraklamada geçen süre kayda girmez',
  'hud.resumeHint': 'Devam et: Ctrl+Alt+P · Bitir: Ctrl+Alt+Space',
  'hud.processing': 'İşleniyor',
  'hud.step.stt': 'konuşma metne çevriliyor',
  'hud.step.llm': 'metin temizleniyor',
  'hud.step.transcribe': 'Konuşma tanıma',
  'hud.step.fillers': 'Dolgu ayıklama · {count} ses',
  'hud.step.polish': 'Noktalama ve bağlam',
  'hud.readyToPaste': 'Yapıştırmaya hazır',
  'hud.refine.hint': 'Sesle düzelt: Ctrl+Alt+Space → “daha kısa yaz”',
  'hud.refine.listening': 'Düzeltmeyi dinliyor',
  'hud.refine.working': 'Yeniden yazılıyor…',
  'hud.paste': 'Yapıştır',
  'hud.cancel': 'İptal',
  'hud.fillersRemoved': '{count} dolgu ayıklandı',
  'hud.localOnly': 'yalnız yerel',
  'hud.error': 'Dikte tamamlanamadı',
  'hud.dismiss': 'Kapat',
  'hud.noSignal': 'Mikrofondan ses gelmiyor',
  'hud.silent': 'Konuşma algılanmadı',
  'hud.silent.hint': 'Kayıtta konuşma çıkmadı, bu yüzden hiçbir şey gönderilmedi. Daha yüksek sesle veya mikrofona daha yakın konuşmayı deneyin.',
  'hud.clipboard': 'Metin panoda — Ctrl+V ile yapıştırın',
  'hud.clipboard.hint':
    '{count} karakter panoya kopyalandı ama hedef pencereye gönderilemedi. Konuşmanız kaybolmadı; imlecinizi istediğiniz yere koyup Ctrl+V yapın.',
  'hud.clipboard.retryHint':
    'Metni yapıştırmak istediğiniz pencereye tıklayın, sonra Ctrl+Alt+V yapın. ' +
    'Buradaki düzenlemeleriniz korunur.',
  'hud.deadMic': 'Mikrofon ses üretmiyor',
  'hud.deadMic.hint': 'Seçili mikrofon hiç sinyal göndermiyor. Ayarlar → MİKROFON bölümünden çalışan bir aygıt seçin. (NVIDIA Broadcast gibi sanal mikrofonlar, kendi uygulamaları kapalıyken sessizlik üretir.)',

  'meeting.recording': 'Toplantı kaydediliyor',
  'meeting.recording.hint': 'mikrofon + sistem sesi birlikte',
  'meeting.channel.mine': 'Ben',
  'meeting.channel.theirs': 'Diğer katılımcılar',
  'meeting.channel.silent': 'ses gelmiyor',
  'meeting.stopHint': 'Bitir: Toplantı kaydı düğmesi · İptal: Esc',
  'meeting.transcribing': 'Döküm çıkarılıyor',
  'meeting.summarizing': 'Özet hazırlanıyor',
  'meeting.working.hint': 'bu birkaç dakika sürebilir',
  'meeting.chunkProgress': 'parça {done}/{total}',
  'meeting.done': 'Toplantı özeti hazır',
  'meeting.noSummary': 'Özet üretilemedi, ama tam döküm kayıtlı.',
  'meeting.copySummary': 'Özeti kopyala',
  'meeting.copyTranscript': 'Dökümü kopyala',
  'meeting.error': 'Toplantı işlenemedi',
  'meeting.start': 'Toplantı kaydı',
  'meeting.stop': 'Kaydı bitir',
  'meeting.blockedByDictation': 'Dikte sürerken toplantı kaydı başlatılamaz',

  // ── Mikrofon ─────────────────────────────────────────────────────────────
  'mic.title': 'MİKROFON',
  'mic.systemDefault': 'Sistem varsayılanı',
  'mic.systemDefaultHint': 'Windows’ta seçili aygıt kullanılır',
  'mic.refresh': 'Yenile',
  'mic.streaming': 'akış açık',
  'mic.stopped': 'akış kapalı',
  'mic.noDevices': 'Mikrofon bulunamadı',
  'mic.alwaysListening': 'Sıfır gecikme için mikrofon sürekli dinlenir',
  'mic.alwaysListeningHint':
    'Son 1 saniye yalnız bellekte tutulur, diske yazılmaz ve kısayola basılmadıkça hiçbir yere gönderilmez.',

  // ── Harcama ──────────────────────────────────────────────────────────────
  'spend.title': 'HARCAMA',
  'spend.today': 'bugün',
  'spend.month': 'bu ay',
  'spend.budget': 'bütçe',
  'spend.calls': '{count} çağrı',

  'mode.quick': 'Hızlı dikte',
  'mode.code': 'Kod & refactor',
  'mode.translate_en': 'İngilizce çeviri',
  'mode.mega_prompt': 'Mega-prompt',
  'mode.image_prompt': 'Görsel istem',
  'mode.sql': 'SQL',
  'mode.commit': 'Commit mesajı',
  'mode.quick.desc': 'Konuşmayı temizler ve ortama uygun biçimde yapıştırır',
  'mode.code.desc': 'Seçili kodu okur, istenen değişikliği uygular',
  'mode.translate_en.desc': 'Türkçe konuş, İngilizce yapıştır',
  'mode.mega_prompt.desc': 'Dağınık fikri yapılandırılmış bir isteme çevirir',
  'mode.image_prompt.desc': 'Görsel üretim modelleri için istem üretir',
  'mode.sql.desc': 'Anlatılan sorguyu SQL’e çevirir',
  'mode.commit.desc': 'Conventional commit mesajı üretir',
  'region.hint': 'Sormak istediğin alanı fareyle seç',
  'region.cancel': 'iptal',
  'mode.screen': 'Ekran gözü',
  'mode.screen.desc': 'Ekrandan bölge seç, sesle sor',
  'hud.screenRegion': 'ekran {width}×{height}',
  'hud.step.selection': 'Seçili metin · {count} karakter',
  'hud.selectionUsed': 'seçim {count} karakter',
  'profile.code': 'kod',
  'profile.chat': 'sohbet',
  'profile.document': 'belge',
  'profile.terminal': 'terminal',
  'profile.spreadsheet': 'hesap tablosu',
  'profile.email': 'e-posta',
  'profile.browser': 'tarayıcı',
  'profile.plain': 'düz metin',
  'table.shortcutConflict': 'çakışma',
  'table.shortcutMoved': '{from} alınmış → taşındı',
  'hud.format.plain': 'düz',
  'hud.format.markdown': 'Markdown',
  'hud.format.plain_from_markdown': 'düz metne indir',
  'hud.format.json_string': 'JSON dizesi',
  'hud.format.html': 'HTML',
  'hud.format.code_block': 'kod bloğu',

  'hud.piiMasked': '{count} hassas değer gizlendi',

  'vocab.title': 'ÖZEL SÖZLÜK',
  'vocab.add': 'Terim ekle',
  'vocab.placeholder': 'yeni terim',
  'vocab.empty': 'Henüz terim yok',
  'vocab.count': '{count} terim',
  'vocab.hint': 'Bu terimler hem konuşma tanımaya hem de metin işlemeye iletilir',

  'snippets.title': 'ŞABLON KÜTÜPHANESİ',
  'snippets.count': '{count} şablon',
  'snippets.name': 'Şablon adı',
  'snippets.namePlaceholder': 'şablon adı — konuşurken bunu söyle',
  'snippets.body': 'Şablon metni',
  'snippets.bodyPlaceholder': 'Şu kodu incele ve iyileştirme öner:',
  'snippets.triggers': 'Ek tetikleyiciler',
  'snippets.triggersPlaceholder': 'ek tetikleyiciler, virgülle ayır (isteğe bağlı)',
  'snippets.duplicate': 'Bu adda bir şablon zaten var',
  'snippets.empty': 'Henüz şablon yok',
  'snippets.used': '{count}×',
  'snippets.try': 'Dene',
  'snippets.tryPlaceholder': 'bir cümle yaz, hangi şablonun tutacağını gör',
  'snippets.tryHit': '“{name}” tetiklenir',
  'snippets.tryMiss': 'Hiçbir şablon tetiklenmez',
  'snippets.hint':
    'Şablon adı konuşmanda geçince kalıp isteme eklenir. Eşleşme esnektir: ' +
    '“kod inceleme” kaydı “kod incelemesi yap” ile de tutar.',

  // ── Genel ────────────────────────────────────────────────────────────────
  'lang.switch': 'Dil',
  'common.mockNotice': 'Örnek veri — motor Faz 2’de bağlanacak',
} as const

export type MessageKey = keyof typeof tr
export type Messages = Record<MessageKey, string>