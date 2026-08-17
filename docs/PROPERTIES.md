**DikteX** için konuştuğumuz tüm modüller, teknik kabiliyetler ve ileri düzey özelliklerin eksiksiz listesi:

---

**I. Temel Ses & STT (Speech-to-Text) Katmanı**

* **Dolgu Kelime Temizleme:** Konuşma sırasındaki "eee", "ımm", "şey", duraksama ve anlamsız kelime tekrarlarını otomatik ayıklama.
* **Hibrit İşleme Modeli:** Hızlı ve yerel işlem için GPU destekli `faster-whisper` / `whisper.cpp`; sıfır donanım yükü için bulut API (OpenRouter/Groq Whisper) desteği.
* **Sıfır Gecikmeli Ses Ön Belleği (Circular Buffer):** Kısayola basmadan 1 saniye önceki sesi yakalayarak ilk hecenin yutulmasını önleme.
* **Özel Terim & Sözlük Katmanı (Custom Vocabulary):** Mühendislik terimleri, kodlama kütüphaneleri, kısaltmalar veya Türkçe isimler için STT ve LLM katmanına enjekte edilen `.json` sözlük sistemi.
* **Dinamik Model Seçici:** Sistem durumuna veya pil/şarj moduna göre anlık olarak Whisper Tiny, Small veya Large modelleri arasında geçiş.

---

**II. Zeka, Akıl Yürütme & Prompt Mühendisliği**

* **Aktif Pencere / Uygulama Farkındalığı (Context-Aware):** Hangi yazılımın açık olduğunu (VS Code, Excel, Notion, Discord, Slack vb.) algılayıp çıktıyı o ortama uygun formatta (kod, formül, profesyonel mesaj) üretme.
* **Düşünce Zinciri (Chain-of-Thought / Reasoning) Modu:** Dağınık konuşulan fikirleri mantıksal aşamalara bölerek LLM'e derin düşünme yaptıran prompt mimarisine dönüştürme.
* **Dinamik Değişken Enjeksiyonu:** Sesli komutun içine `{SelectedText}`, `{CurrentDate}`, `{AppTitle}`, `{ClipboardContent}` gibi sistem verilerini otomatik ekleme.
* **Kritik Prompt Denetçisi (Prompt Linter):** Eksik kalan parametreleri fark edip (örneğin çıktı formatı veya rol tanımı) mini bir arayüzle kullanıcıya öneride bulunma.
* **Meta-Prompt & Çoklu Format Çevirici:** Konuşmayı doğrudan Midjourney, DALL-E, SQL veya spesifik regex/kod kalıplarına dönüştürme.
* **Öğrenen Kişisel Stil (Style Refiner):** Kullanıcının geçmiş komutlarını ve yazı dilini analiz ederek çıktıyı kullanıcının tonunda oluşturma.
* **Çoklu Model Orkestrasyonu (Multi-Model Switcher):** OpenRouter üzerinden tek tıkla Claude 3.5 Haiku/Sonnet, GPT-4o, Llama 3.3 70B veya DeepSeek modellerine yönlendirme.
* **A/B Model Karşılaştırıcı:** Tek bir sesli komutu iki farklı modele eşzamanlı gönderip sonuçları yan yana kıyaslama.
* **Negative Prompting & Yasaklı Kalıplar:** İstenmeyen yapay zeka klişelerini ve robotik dolguları filtreleme.

---

**III. Toplantı, Sistem Sesi & Medya Zekası**

* **İki Yönlü Sistem Sesi Kaydı (Loopback Audio):** Hem mikrofonu hem de hoparlör/kulaklıktan gelen toplantı seslerini (Zoom, Google Meet, Teams, Discord) eşzamanlı yakalama.
* **Konuşmacı Ayrımı (Speaker Diarization):** Konuşmadaki sesleri ayrıştırıp kişilere göre etiketleme.
* **Canlı Eylem Maddesi Çıkarıcı (Action Items):** Toplantıdan kararları, sorumluları ve görev listelerini otomatik özet çıkarma.
* **Video & Podcast Özetleyici:** Arka planda çalan YouTube veya medya akışlarını anlık metne ve madde işaretli özete dönüştürme.
* **Gerçek Zamanlı Toplantı Koçu:** Konuşma hızını, kaçırılan konuları veya süreyi sessiz HUD bildirimleriyle takip etme.

---

**IV. Kullanıcı Deneyimi, HUD & Arayüz (UI/UX)**

* **Mica/Acrylic Efektli Windows Native Arayüz:** Windows 11 tasarım diliyle uyumlu, yarı saydam ve modern HUD.
* **Floating Command Bar (Spotlight / Raycast Tarzı):** Kısayolla imlecin yanında beliren, fare gerektirmeyen şık arama/komut çubuğu.
* **Pre-flight Önizleme Penceresi:** Çıktı ekrana yapıştırılmadan önce hızlıca düzenleme, onaylama veya iptal etme alanı.
* **Görsel Prompt Akış Editörü (Node/Tree Canvas):** Uzun ve karmaşık zincirleme promptları görselleştiren blok editörü.
* **Çoklu Mod ve Hızlı Tuş Kombinasyonları (Chorded Shortcuts):** Hızlı dikte, mega-prompt, kodlama ve İngilizce çeviri için özelleştirilmiş global kısayollar.

---

**V. İş Akışı, Otomasyon & Entegrasyon**

* **Seçili Metni Referans Alma (Highlight & Transform):** Seçili bir kod/metin bloğunu pano üzerinden okuyup sesli talimatla refactor etme veya düzenleme.
* **Bölgesel Ekran Gözü (Region OCR + Vision):** Ekrandan seçilen bir hata penceresini veya görseli Vision modeline sesli soruyla iletme.
* **Snippet & Şablon Kütüphanesi:** Sık kullanılan dev prompt kalıplarını kaydetme ve sesli tetikleme.
* **Otomatik Makro & API Tetikleyici:** İşlenen metni doğrudan üçüncü parti araçlara (Notion, webhook vb.) gönderme.
* **Git Commit Mesajı Üretici:** Aktif çalışma dizinindeki `git diff` verisini okuyup conventional commit mesajı basma.
* **Sesli Dosya & Kod Oluşturucu:** Sesli komutla doğrudan yeni dosya oluşturup işlenmiş içeriği içine yazma.
* **Biçimlendirilmiş Yapıştırma Motoru:** Çıktıyı Markdown, JSON, HTML veya düz metin olarak hedef alana otomatik yapıştırma.

---

**VI. Güvenlik, Depolama & Altyapı**

* **API Kasası (Secure Vault):** OpenRouter ve diğer anahtarları Windows Credential Manager üzerinde şifreli saklama.
* **Hassas Veri Maskeleme (PII Masking):** TC kimlik, kart no, API anahtarı veya şahsi verileri buluta gitmeden önce yerelde sansürleme.
* **Prompt Geçmişi & Yerel Veritabanı:** Tüm sesli girdilerin ve çıktıların yerel SQLite üzerinde tutulduğu arama motoru.
* **Sesli Not Defteri (Daily Scratchpad):** Günlük rastgele fikirleri toplayıp gün sonunda düzenleyen yerel not paneli.
* **Yerel REST / Webhook Sunucusu:** Diğer masaüstü betiklerinin veya projelerin `localhost` üzerinden DikteX motorunu tetikleyebilmesi.