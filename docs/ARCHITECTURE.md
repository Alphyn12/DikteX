# OmniVoice — Mimari

## Genel bakış

İki süreçli bir masaüstü uygulaması. Kabuk ve arayüz Electron'da, sesle ve
yapay zekayla ilgili her şey ayrı bir Python sürecinde çalışır.

```
┌─────────────────────────────────────────────────────────────┐
│  OmniVoice.exe   (Electron · Node.js)                       │
│                                                             │
│  ┌───────────────────┐      ┌────────────────────────────┐  │
│  │  main process     │      │  renderer  (React + TS)    │  │
│  │  ─────────────    │ IPC  │  ──────────────────────    │  │
│  │  · pencere/Mica   │◄────►│  · Ana pencere (Panel)     │  │
│  │  · global kısayol │      │  · Ayarlar                 │  │
│  │  · tray           │      │  · HUD  (ayrı pencere)     │  │
│  │  · yapıştırma     │      │  · Command Bar (ayrı pnc.) │  │
│  │  · aktif pencere  │      │                            │  │
│  └─────────┬─────────┘      └────────────────────────────┘  │
└────────────┼────────────────────────────────────────────────┘
             │  spawn + WebSocket (ws://127.0.0.1:8756)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  omnivoice-engine   (Python · FastAPI)                      │
│                                                             │
│  audio/     mikrofon · dairesel ön bellek · WASAPI loopback │
│  stt/       sağlayıcı arayüzü → Groq · OpenRouter           │
│  llm/       sağlayıcı arayüzü → OpenRouter yönlendirici     │
│  pipeline/  dolgu temizleme · bağlam · prompt kurma         │
│  storage/   SQLite (geçmiş, maliyet, sözlük, snippet)       │
│  server/    REST + WebSocket  ← dış betikler de tetikler    │
└─────────────────────────────────────────────────────────────┘
```

## Neden iki süreç

| Sorumluluk | Nerede | Gerekçe |
|---|---|---|
| Piksel-mükemmel arayüz | Electron | Mockup HTML/CSS; birebir çıkarmanın en kısa yolu |
| Mica/Acrylic, tray, global kısayol, çok pencere | Electron | Windows 11 desteği birinci sınıf |
| Ses yakalama, STT, diarization, OCR | Python | Bu alanın kütüphane ekosistemi Python'da |
| Yerel REST/Webhook sunucusu | Python | Zaten çalışan sunucu; Properties VI.5 bedavaya gelir |

Python sürecinin ayrı olması ek bir kazanç sağlar: motor çökerse arayüz ayakta
kalır ve süreci yeniden başlatır.

## Dizin yapısı

```
omnivoice/
├─ apps/desktop/          Electron + React + TypeScript
│  ├─ electron/           main process + preload
│  └─ src/                renderer (React)
│     ├─ design/          tasarım token'ları (tek gerçek kaynak)
│     ├─ windows/         main · hud · commandbar
│     ├─ components/
│     └─ i18n/            TR + EN
├─ engine/                Python motoru
│  └─ omnivoice_engine/
│     ├─ audio/  stt/  llm/  pipeline/  storage/  server/
├─ design/                Claude Design mockup (referans, değiştirilmez)
├─ docs/                  ROADMAP · ARCHITECTURE · DESIGN-TOKENS · PROPERTIES
└─ assets/                logo
```

## Sağlayıcı soyutlaması

STT ve LLM katmanları arayüz üzerinden konuşur; hiçbir yerde sağlayıcı adı
sabit kodlanmaz.

```python
class SttProvider(Protocol):
    async def transcribe(self, audio: AudioClip, *, language: str | None) -> Transcript: ...

class LlmProvider(Protocol):
    async def complete(self, prompt: Prompt, *, model: str) -> Completion: ...
```

Bugünkü uygulamalar: `GroqStt`, `OpenRouterStt`, `OpenRouterLlm`.
Yarın yerel bir motor istenirse `LocalWhisperStt` eklenir, çağıran taraf değişmez.

Her `Transcript` ve `Completion` **ölçülen gecikmeyi ve gerçek maliyeti** taşır;
bu değerler SQLite'a yazılır ve panelde gösterilir. Arayüzde sahte performans
sayısı bulunmaz.

## Gizli bilgi yönetimi

- Geliştirme sırasında: `.env.local` (git tarafından yok sayılır)
- Ürün sürümünde: **Windows Credential Manager** (Faz 2.1 — API Kasası)
- Anahtarlar renderer sürecine **hiçbir zaman** gönderilmez; yalnız Python motoru görür.
- Buluta giden her istek önce PII maskeleme katmanından geçer (Faz 6.1).
