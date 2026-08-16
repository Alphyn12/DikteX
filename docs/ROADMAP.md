# OmniVoice — Geliştirme Yol Haritası

**Strateji: dikey dilim.** Her faz, kullanılabilir bir uygulama bırakır. Bir fazdaki
her madde **%100 bitmeden** bir sonraki faza geçilmez.

**Durum işaretleri:** ⬜ başlanmadı · 🟨 devam ediyor · ✅ bitti

---

## Faz 0 — Temel altyapı

Anahtar gerektirmez. Amaç: iki süreçli iskeletin ayakta olması ve `npm run dev`
ile boş ama çalışan bir pencerenin açılması.

| # | Madde | Durum |
|---|---|---|
| 0.1 | Git deposu, `.gitignore`, gizli bilgi hijyeni | ✅ |
| 0.2 | Monorepo yapısı (`apps/desktop`, `engine`) | ✅ |
| 0.3 | Electron + Vite + React + TypeScript iskeleti | ✅ |
| 0.4 | Python motor iskeleti (FastAPI + WebSocket) | ✅ |
| 0.5 | Electron ↔ Python süreç yönetimi ve IPC köprüsü | ✅ |
| 0.6 | Tasarım token'ları (mockup'tan çıkarılan renk/tipografi/ölçü sistemi) | ✅ |
| 0.7 | i18n altyapısı (TR + EN) | ✅ |
| 0.8 | GitHub'a ilk push (`Alphyn12/omnivoice`, private) | ✅ |

**Çıktı:** ✅ Pencere Mica malzemesiyle açılıyor, kendi başlık çubuğunu çiziyor,
Python motoru arkada çalışıyor ve WebSocket el sıkışması tamamlanıyor. Motor
çökerse süpervizör üstel geri çekilmeyle yeniden bağlanıyor. Dil TR/EN arasında
değişiyor. Tip denetimi ve motor testleri (5/5) geçiyor.

**Faz 0'da alınan kararlar:**
- Vite 8 değil **Vite 7** — `electron-vite@5` henüz 8'i desteklemiyor.
- Mica gerçek anlamda kullanılıyor: mockup'ın pencere gövdesi %94–96 opak bir
  gradyandı ve Mica'yı örterdi. Properties IV.1 native Mica istediği için
  gradyan yerine gerçek Mica tercih edildi; bu sapma bilinçlidir.

---

## Faz 1 — Arayüz kabuğu

Mockup 1a'nın birebir hayata geçirilmesi. Sahte veriyle, motor bağlı değil.

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 1.1 | Mica malzemeli pencere, 8 px yarıçap, özel başlık çubuğu (40 px, 46×40 düğmeler) | IV | ✅ |
| 1.2 | Sol gezinme (248 px, 40 px öğeler, 3×16 px seçim pili, modül renkleri) | IV | ✅ |
| 1.3 | Panel ekranı — istatistik kartları, sparkline, motor durum şeridi, dikte akışı | IV | ✅ |
| 1.4 | Sağ sütun — Action items, Sesli not defteri, Sözlük önerileri, uyarı kartı | IV | ✅ |
| 1.5 | Ayarlar ekranı — mod/model tablosu, anahtarlar, kasa kartı | IV | ✅ |
| 1.6 | Sistem tepsisi (tray) ikonu ve menüsü | IV | ✅ |
| 1.7 | TR/EN dil değiştirme çalışır durumda | — | ✅ |

**Çıktı:** ✅ Mockup'a birebir benzeyen, gezilebilen ama henüz konuşmayan uygulama.
Kapatma düğmesi uygulamayı sonlandırmaz, tepsiye çeker — global kısayolun her an
çalışması gerektiği için.

**Faz 1'de yakalanan hatalar:**
- **Ses dalgası hiç animasyon yapmıyordu.** `@keyframes om-bar` global `tokens.css`
  içindeydi, ona `primitives.module.css` içinden atıf yapılıyordu. CSS Modules
  modüldeki animasyon adını kapsamlandırıp yeniden adlandırıyor; global tanıma
  yapılan atıf var olmayan bir ada dönüşüp **sessizce** düşüyordu. Kare tanımı
  onu kullanan modüle taşındı.
- **Sayı ve birimler yerelleşmiyordu.** Gecikme değerleri (`1.1 sn`, `akış`) ve
  istatistikler (`4.812`) veriye metin olarak yazılmıştı; İngilizce arayüzde
  Türkçe birim ve Türkçe binlik ayırıcı görünüyordu. Sayılar ham sayıya çevrildi,
  biçimlendirme `Intl` üzerinden arayüze taşındı.
- **Sağ sütun taşıyordu.** Mockup 812 px yüksekliğe göre çizilmişti; daha kısa
  pencerede pil uyarısı ekran dışına düşüyordu. Kartlar kaydırılabilir bölgeye
  alındı, uyarı alta sabitlendi.
- **Sınıf adı birleştirme riskliydi.** CSS modül anahtarları tip düzeyinde
  `string | undefined`; şablonla birleştirmek yanlış yazılmış bir sınıfı
  `"undefined"` diye basardı. `cx()` yardımcısı eklendi.

---

## Faz 2 — Dikte zinciri, uçtan uca ⭐

**Bu fazın sonunda uygulama gerçekten kullanılabilir olur.** API anahtarları burada devreye girer.

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 2.1 | API Kasası — anahtarlar Windows Credential Manager'da şifreli | VI | ✅ |
| 2.2 | Global kısayol yakalama (`Ctrl+Alt+Space`) | IV | ✅ |
| 2.3 | Mikrofon yakalama + **sıfır gecikmeli dairesel ön bellek** (1 sn pre-roll) | I | ✅ |
| 2.4 | STT sağlayıcı soyutlaması → Groq `whisper-large-v3-turbo` | I | ✅ |
| 2.5 | STT yedekleme zinciri (Groq kotası biterse OpenRouter STT) | I | ✅ |
| 2.6 | **Dolgu kelime temizleme** ("eee", "ımm", "şey", tekrarlar) | I | ✅ |
| 2.7 | LLM sağlayıcı soyutlaması → OpenRouter yönlendirici | II | ✅ |
| 2.8 | Canlı dikte HUD — 3 durum: dinliyor · işliyor · pre-flight (mockup 1c) | IV | ✅ |
| 2.9 | **Pre-flight önizleme** — düzenle / onayla / iptal | IV | ✅ |
| 2.10 | Yapıştırma motoru — hedef uygulamaya metin gönderme | V | ✅ |
| 2.11 | Yerel SQLite — dikte geçmişi ve arama (FTS5) | VI | ✅ |
| 2.12 | **Maliyet takibi** — istek başına `usage.cost`, panelde canlı harcama + bütçe | — | ✅ |
| 2.13 | Gerçek gecikme ölçümü (mockup'taki sahte "180 ms" yerine ölçülen değer) | — | ✅ |
| 2.14 | **Mikrofon kaynağı seçimi** (kullanıcı isteği) | — | ✅ |

**Çıktı:** ✅ Kısayola bas → konuş → bırak → pre-flight'ta gör → Enter → metin
imlecin olduğu yere yapışıyor. Panel gerçek veriyi gösteriyor: dikte sayısı,
kaydedilen ses, ölçülen gecikme, gerçek harcama ve SQLite'tan gelen geçmiş.

**Ölçülen gerçek değerler** (TTS ile üretilmiş Türkçe sesle):
- Groq STT: 1.0–1.7 sn · Türkçe transkripsiyon neredeyse kusursuz
- Gemini 2.5 Flash-Lite: 0.8–1.1 sn · dikte başına ~$0.00005
- Uçtan uca: ~2.2 sn · **mockup'taki 180 ms bir yerel GPU rakamıydı**
- Aylık tahmin (günde 50 dikte): **~$0.09**

**Faz 2'de yakalanan hatalar** — hepsi sessizce başarısız oluyordu:

| Hata | Nasıl bulundu | Sonucu ne olurdu |
|---|---|---|
| **Prompt'ta rol karışıklığı** | 5 modelden 4'ü, dikte edilen "şu terimleri sözlüğe ekle" cümlesini kendine talimat sanıp cevap yazdı | Kullanıcı "Ali'ye söyle" dediğinde ekrana "Tamam, söylüyorum" yapışırdı |
| **Whisper sessizlikte halüsinasyon** | Canlı testte boş kayda "Thank you." uydurdu | Kısayola yanlışlıkla basınca ekrana "Teşekkürler." yapışırdı |
| **`SendInput` yapı boyutu** | x64'te `INPUT` 40 bayt olmalıyken 32 üretiliyordu | **Yapıştırma hiç çalışmazdı**, hata da vermezdi |
| **Odak çalma koruması** | `SetForegroundWindow` reddedildi | Pre-flight'ta Enter'a basmak hiçbir şey yapmazdı |
| **Aygıt değişiminde çökme** | Geçersiz indeks `PortAudioError` → motor komple düştü | Yanlış mikrofon seçmek uygulamayı öldürürdü |
| **WASAPI biçim uyumsuzluğu** | Realtek 16 kHz mono kabul etmiyor, 44.1 kHz stereo istiyor | Mikrofon seçicideki aygıtların çoğu açılamazdı |
| **Dil çevirisi** | İngilizce girdi Türkçe'ye çevrildi (istem Türkçe olduğu için) | İngilizce dikte Türkçe çıkardı |
| **"Gecikme" yanlış ölçülüyordu** | `total_ms` konuşma süresini de içeriyordu | 30 sn konuşma "32.000 ms gecikme" görünürdü |
| **Zaman dilimi** | Kayıtlar UTC, "bugün" yerel tarih | Gece yarısı civarı yanlış sayım |

**Faz 2'de alınan kararlar:**
- **Kısayol aç-kapa çalışıyor**, bas-basılı-tut değil. Electron'un `globalShortcut`
  API'si tuş bırakmayı bildirmiyor; basılı tutma düşük seviyeli klavye kancası
  gerektiriyor. O kanca zaten Faz 3.5'teki chorded shortcut'lar için kurulacak.
- **Mikrofon sürekli dinleniyor** — pre-roll'un bedeli bu. Ayarlar'daki mikrofon
  kartında açıkça yazıyor: son 1 saniye yalnız bellekte, diske yazılmıyor,
  kısayola basılmadıkça hiçbir yere gönderilmiyor.
- **Sağ sütundaki action items / not defteri / sözlük** hâlâ örnek veri;
  kaynakları Faz 4 ve Faz 6'da bağlanacak.

**101 test geçiyor.**

---

## Faz 3 — Zeka ve prompt mühendisliği

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 3.1 | Aktif pencere / uygulama farkındalığı (VS Code, Excel, Slack, Discord…) | II | ⬜ |
| 3.2 | Bağlama göre çıktı biçimi profilleri | II | ⬜ |
| 3.3 | Seçili metni referans alma (`{SelectedText}` — Highlight & Transform) | V | ⬜ |
| 3.4 | Dinamik değişken enjeksiyonu (`{CurrentDate}`, `{AppTitle}`, `{ClipboardContent}`) | II | ⬜ |
| 3.5 | Chorded shortcuts — mod seçimi (K kod · E İngilizce · M mega-prompt) | IV | ⬜ |
| 3.6 | Chain-of-Thought / akıl yürütme modu | II | ⬜ |
| 3.7 | Özel terim & sözlük katmanı (`.json`, STT + LLM'e enjekte) | I | ⬜ |
| 3.8 | Çoklu model orkestrasyonu (mod başına model/sağlayıcı) | II | ⬜ |
| 3.9 | A/B model karşılaştırıcı (yan yana) | II | ⬜ |
| 3.10 | Negative prompting & yasaklı kalıplar | II | ⬜ |
| 3.11 | Kritik prompt denetçisi (Prompt Linter) | II | ⬜ |
| 3.12 | Meta-prompt & çoklu format çevirici (Midjourney, SQL, regex…) | II | ⬜ |
| 3.13 | Öğrenen kişisel stil (Style Refiner) | II | ⬜ |
| 3.13b | Gemini sağlayıcısı — yalnız düşük riskli arka plan işleri + STT yedeği | — | ⬜ |
| 3.14 | Floating Command Bar (mockup 1b) | IV | ⬜ |
| 3.15 | Dinamik model seçici (pil/GPU durumuna göre) | I | ⬜ |

---

## Faz 4 — Toplantı, sistem sesi ve medya

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 4.1 | İki yönlü sistem sesi kaydı (WASAPI loopback) | III | ⬜ |
| 4.2 | Uzun kayıt parçalama (25 MB / 60 sn API limitleri için) | — | ⬜ |
| 4.3 | Konuşmacı ayrımı (speaker diarization) | III | ⬜ |
| 4.4 | Canlı eylem maddesi çıkarıcı (action items + sorumlular) | III | ⬜ |
| 4.5 | Toplantı özeti ve dışa aktarma | III | ⬜ |
| 4.6 | Video & podcast özetleyici | III | ⬜ |
| 4.7 | Gerçek zamanlı toplantı koçu (sessiz HUD bildirimleri) | III | ⬜ |

---

## Faz 5 — İş akışı, otomasyon ve entegrasyon

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 5.1 | Bölgesel ekran gözü (Region OCR + Vision) | V | ⬜ |
| 5.2 | Snippet & şablon kütüphanesi | V | ⬜ |
| 5.3 | Git commit mesajı üretici (`git diff` → conventional commit) | V | ⬜ |
| 5.4 | Sesli dosya & kod oluşturucu | V | ⬜ |
| 5.5 | Biçimlendirilmiş yapıştırma motoru (Markdown / JSON / HTML / düz metin) | V | ⬜ |
| 5.6 | Otomatik makro & API tetikleyici (Notion, webhook) | V | ⬜ |
| 5.7 | Görsel prompt akış editörü (node/tree canvas) | IV | ⬜ |

---

## Faz 6 — Güvenlik, depolama ve dağıtım

| # | Madde | Kaynak | Durum |
|---|---|---|---|
| 6.1 | Hassas veri maskeleme (PII: TC kimlik, kart no, API anahtarı) | VI | ⬜ |
| 6.2 | Prompt geçmişi arama motoru (tam metin arama) | VI | ⬜ |
| 6.3 | Sesli not defteri (Daily Scratchpad) + gün sonu derleme | VI | ⬜ |
| 6.4 | Yerel REST / Webhook sunucusu (`localhost:8756`) | VI | ⬜ |
| 6.5 | Otomatik başlatma, güncelleme kontrolü | — | ⬜ |
| 6.6 | Windows kurulum paketi (installer) | — | ⬜ |

---

## Kapsam dışı bırakılan (gerekçeli)

| Konu | Gerekçe |
|---|---|
| Yerel GPU Whisper (`faster-whisper` / `whisper.cpp`) | Donanım 4 GB VRAM (RTX 3050 Ti Laptop) — büyük modeller sığmıyor. Ayrıca kullanıcı bulut tercih etti. **STT katmanı sağlayıcıdan bağımsız arayüz olarak yazılıyor**, ileride yerel motor ek maliyetsiz takılabilir. |
| Mockup'taki "180 ms" gecikme | Bu bir yerel GPU rakamı. Bulut mimarisinde gerçekçi hedef ~1.2–2.5 sn. Arayüzde **ölçülen gerçek değer** gösterilecek. |
