<div align="center">
  <img src="assets/logo-omnivoice.png" width="96" alt="OmniVoice">
  <h1>OmniVoice</h1>
  <p><b>Windows 11 için sesle çalışan yapay zeka asistanı.</b><br>
  Kısayola bas, konuş, bırak — temizlenmiş ve bağlama uygun metin imlecinin olduğu yere yapışsın.</p>
</div>

---

## Ne yapar

OmniVoice bir dikte aracı değil, sesle çalışan bir **prompt motorudur**. Konuştuğunuz
dağınık cümleyi alır; dolgu kelimeleri ayıklar, hangi uygulamada olduğunuzu anlar
ve çıktıyı o ortama uygun biçimde üretir — VS Code'da kod, Slack'te profesyonel
mesaj, terminalde conventional commit mesajı.

- **Bağlam farkındalığı** — aktif pencereye göre çıktı biçimi değişir
- **Sıfır gecikmeli ön bellek** — kısayola basmadan 1 saniye öncesini yakalar, ilk hece yutulmaz
- **Pre-flight önizleme** — hiçbir şey onayınız olmadan yapıştırılmaz
- **Toplantı zekası** — sistem sesini de kaydeder, konuşmacıları ayırır, eylem maddesi çıkarır
- **Gizlilik** — hassas veriler buluta gitmeden önce yerelde maskelenir; anahtarlar Windows Credential Manager'da

Tüm özellik listesi: [`docs/PROPERTIES.md`](docs/PROPERTIES.md)

## Durum

🚧 **Geliştirme aşamasında — Faz 0.**

İlerleme ve faz planı: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Teknoloji

| Katman | Teknoloji |
|---|---|
| Kabuk & arayüz | Electron · React · TypeScript · Vite |
| Motor | Python · FastAPI |
| Konuşma → metin | Groq `whisper-large-v3-turbo` (yedek: OpenRouter) |
| Zeka katmanı | OpenRouter (çoklu model yönlendirme) |
| Depolama | SQLite (yerel) |

Ayrıntılı mimari: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Kurulum (geliştirme)

```bash
git clone https://github.com/Alphyn12/omnivoice.git
cd omnivoice

# API anahtarlarını gir
cp .env.example .env.local
#  → GROQ_API_KEY       console.groq.com/keys
#  → OPENROUTER_API_KEY openrouter.ai/settings/keys

# Bağımlılıklar
npm install
npm run engine:install   # Python sanal ortamı + motor bağımlılıkları

# Çalıştır
npm run dev
```

**Kontroller**

```bash
npm run typecheck     # TypeScript
npm run engine:test   # motor testleri
npm run build         # üretim derlemesi
```

> **Uyarı:** `.env.local` dosyasını asla commit etmeyin. `.gitignore` bunu
> engeller, ama `git add -f` ile zorlamayın.

### Sorun giderme

**`Error: Electron uninstall`** — npm workspace kurulumunda Electron'un
postinstall betiği bazen atlanıyor ve ikili dosya indirilmemiş oluyor.
Çözümü:

```bash
node node_modules/electron/install.js
```

## Tasarım

Arayüz, Claude Design ile hazırlanan mockup'tan birebir çıkarılmıştır. Kaynak
dosya `design/` altında referans olarak durur ve değiştirilmez. Renk, tipografi
ve ölçü sistemi: [`docs/DESIGN-TOKENS.md`](docs/DESIGN-TOKENS.md)

## Lisans

Özel — tüm hakları saklıdır.
