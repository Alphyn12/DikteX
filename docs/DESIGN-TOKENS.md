# OmniVoice — Tasarım Sistemi

Bu belge `design/mockup.dc.html` dosyasından **birebir çıkarılmıştır**. Arayüzde
sabit kodlanmış renk/ölçü kullanılmaz; her şey buradaki token'lardan gelir.

---

## 1. Temel ilke: renk anlam taşır, dekor değildir

Zemin tek koyu lacivert kalır. Renk yalnız **modül kimliğini** ve **durumu** taşır.
Taşıyıcıları üç tanedir ve bunların dışına çıkılmaz:

- **3 px kenar şeridi** (kartın sol veya üst kenarı)
- **8 px nokta** (2 px yarıçaplı kare)
- **tek satır etiket** (rozet)

Kurallar:
- Ekran başına **en fazla iki renk baskın** olur.
- Parlama (glow) efekti **yalnız** canlı ses göstergesinde ve birincil eylem düğmesinde kullanılır.
- Gölge **yalnız yüzen katmanlarda** (pencere, HUD, komut çubuğu) bulunur; kartlarda gölge yoktur.

---

## 2. Modül renkleri

| Modül | Ana renk | Açık ton (metin/vurgu) | Kullanım |
|---|---|---|---|
| Ses & STT | `#2bb3a3` | `#5fd8c8` | dalga formu, gecikme değeri, hızlı dikte |
| Prompt Stüdyosu / Zeka | `#7c5cff` | `#a493ff` | kod modu, mega-prompt, CoT |
| Toplantılar | `#e0559b` | — | loopback, diarization, action items |
| Arayüz / Sistem | `#3d7ff5` | — | pre-flight, OCR + Vision |
| Otomasyon | `#e59a2b` | `#f0b558` | git commit, uyarı kartları, dolgu sayacı |
| Kasa & Gizlilik | `#6fc25f` | `#96d989` | anahtar durumu, PII maskeleme, "YEREL" rozeti |

**Birincil eylem gradyanı:** `linear-gradient(135deg, #7c5cff, #3d7ff5)`
**Pre-flight yapıştır gradyanı:** `linear-gradient(135deg, #3d7ff5, #7c5cff)`
**Kapatma düğmesi hover:** `#c42b1c`

---

## 3. Zemin ve yüzeyler

```
--bg-app          #080a11      uygulama arkası (en dip)
--bg-canvas       #0a0c14      tuval
--bg-window       linear-gradient(180deg, rgba(24,27,43,.94), rgba(15,17,28,.96))
--bg-content      rgba(255,255,255,.028)   sağdaki içerik alanı
```

**Ortam ışığı** (pencere arkası, mockup 1a/1c):
```css
radial-gradient(78% 62% at 22%  4%, #22264a 0%, rgba(12,14,26,0) 62%),
radial-gradient(52% 48% at 88% 86%, rgba(43,179,163,.16), rgba(0,0,0,0) 70%),
radial-gradient(46% 44% at 12% 92%, rgba(124,92,255,.16), rgba(0,0,0,0) 72%)
```

---

## 4. Malzeme katmanları

Aşağıdan yukarı üç katman vardır:

| Katman | Tanım | Değerler |
|---|---|---|
| **Mica** | Pencere gövdesi. Duvar kağıdı süzülür. | Electron `backgroundMaterial: 'mica'` |
| **Kart** | İçerik kutuları | zemin `rgba(255,255,255,.05)` · kenar `1px solid rgba(255,255,255,.07)` |
| **Acrylic** | HUD ve komut çubuğu. Güçlü bulanıklık, koyu tint. | zemin `rgba(22,25,38,.86)` · `backdrop-filter: blur(42px) saturate(150%)` |

**Kart varyantları:**
- Sönük kart: `rgba(255,255,255,.045)` / kenar `rgba(255,255,255,.07)`
- Akış öğesi: `rgba(255,255,255,.042)` / kenar `rgba(255,255,255,.06)` / sol `3px solid <modül>`
- Hover: `rgba(255,255,255,.075)`
- Tablo başlığı: `rgba(255,255,255,.035)`
- Ayırıcı çizgi: `rgba(255,255,255,.055)` – `rgba(255,255,255,.08)`

**Gölgeler (yalnız yüzen katmanlar):**
```
pencere : 0 40px 88px -26px rgba(0,0,0,.9), 0 0 0 1px rgba(255,255,255,.09), inset 0 1px 0 rgba(255,255,255,.08)
komut çb: 0 34px 70px -20px rgba(0,0,0,.92), 0 0 0 1px rgba(255,255,255,.11), inset 0 1px 0 rgba(255,255,255,.1)
HUD     : 0 22px 48px -18px rgba(0,0,0,.9),  0 0 0 1px <modül renk %34>, inset 0 1px 0 rgba(255,255,255,.08)
birincil: 0 6px 18px -8px rgba(124,92,255,.9)
```

> HUD'un 1 px kenar halkası **duruma göre renk değiştirir**: dinliyor `rgba(43,179,163,.34)`,
> işliyor `rgba(124,92,255,.34)`, pre-flight `rgba(61,127,245,.34)`.

---

## 5. Tipografi

**Arayüz yazı tipi:** `"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`
**Teknik yazı tipi:** `"JetBrains Mono", monospace` + `font-variant-numeric: tabular-nums`

JetBrains Mono **daima** şunlarda kullanılır: sayılar, model adları, kısayollar,
süreler, rozet etiketleri, bölüm başlıkları.

| Rol | Boyut | Ağırlık | Diğer |
|---|---|---|---|
| Title | 28 px | 600 | `letter-spacing:-.4px` · `line-height:1.15` |
| Subtitle | 20 px | 600 | |
| Strong | 14 px | 600 | |
| Body | 14 px | 400 | |
| Caption | 12 px | 400 | |
| Body-sm | 12.5 px | 400 | `line-height:1.5` · gövde metinleri |
| Mono-stat | 25 px | 600 | `letter-spacing:-.6px` · istatistik sayıları |
| Mono-value | 13 px | 600 | gecikme, süre |
| Mono-label | 10 px | 600 | `letter-spacing:.11em` · BÖLÜM BAŞLIKLARI |
| Mono-label-wide | 10 px | 600 | `letter-spacing:.14em` · HUD durum başlıkları |
| Mono-badge | 11 px | 500 | rozet / kısayol |
| Mono-tag | 10 px | 500 | `letter-spacing:.06em` · akış etiketleri |

**Metinde tek vurgu yöntemi ağırlıktır.** Renkle vurgu yapılmaz.

**Metin renkleri** (hepsi `#e7e9f2` üzerine opaklık):
```
%95 birincil · %82 başlık çubuğu · %76 liste · %72 gövde · %62 pasif gezinme
%55 açıklama · %50 alt bilgi · %45 mono etiket · %40 sönük · %34 en sönük
```

---

## 6. Ölçüler ve boşluk

**Tüm boşluklar 4 px ızgarada.**

| Öğe | Değer |
|---|---|
| Başlık çubuğu yüksekliği | 40 px |
| Pencere düğmeleri | 46 × 40 px |
| Sol gezinme genişliği | 248 px |
| Sağ sütun genişliği | 300 px |
| Gezinme öğesi yüksekliği | 40 px |
| Seçim pili | 3 × 16 px, yarıçap 2 px |
| Modül noktası | 8 × 8 px, yarıçap 2 px |
| Birincil/ikincil düğme yüksekliği | 32 px (HUD içinde 30 px) |
| Anahtar (toggle) | 40 × 20 px, tutamak 14 px |
| İçerik kenar boşluğu | 24–28 px |
| Kart iç boşluğu | 14–16 px |

**Yarıçaplar:**
```
pencere 8 px · kart 7 px · kontrol/düğme 4 px · gezinme öğesi 5 px
rozet 3 px · nokta ve pil 2 px · HUD ve komut çubuğu 9 px
```

---

## 7. Hareket

```css
@keyframes omBar  { 0%,100% { transform: scaleY(.22) } 50% { transform: scaleY(1) } }
@keyframes omRing { to { transform: rotate(360deg) } }
```

| Kullanım | Süre | Eğri |
|---|---|---|
| Ses dalgası — panel (22 çubuk) | 1.15 s | `ease-in-out infinite` |
| Ses dalgası — komut çubuğu (12 çubuk) | 1 s | `ease-in-out infinite` |
| Ses dalgası — HUD (16 çubuk) | 0.95 s | `ease-in-out infinite` |
| İşleme halkası | 1.1 s | `linear infinite` |

Çubuklar `animation-delay` ile kaydırılır (−0.5 s … +0.4 s aralığında dağıtılır).
Çubuk genişliği: panel/komut çubuğu 2 px, HUD 2.5 px; aralık 2–2.5 px.

**Erişilebilirlik:** `prefers-reduced-motion: reduce` altında tüm döngüsel
animasyonlar durur; ses seviyesi statik bir çubukla gösterilir.
