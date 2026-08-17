import { globalShortcut } from 'electron'
import type { DictationController } from './dictation'

/**
 * Global kısayollar (Faz 2.2 · Faz 3.5).
 *
 * ## Neden chord değil, ayrı hızlandırıcılar
 *
 * Mockup "Ctrl+Alt+Space → K" biçiminde bir chord gösteriyor: basılı tut,
 * sonra mod harfine bas. Bunu gerçekten yapmak düşük seviyeli bir klavye
 * kancası (`WH_KEYBOARD_LL`) gerektirir, çünkü Electron'un `globalShortcut`
 * API'si yalnız tuşa basmayı bildirir, bırakmayı bildirmez.
 *
 * O kanca üç bedel getiriyor: antivirüs yazılımları düşük seviyeli klavye
 * kancalarını sık sık keylogger sanıyor, ayrı bir mesaj döngüsü iş parçacığı
 * gerekiyor ve kancanın kendisi tüm sistem klavyesini yavaşlatabiliyor.
 *
 * Ayrı hızlandırıcılar (`Ctrl+Alt+K`, `Ctrl+Alt+E` …) aynı yeteneği —
 * klavyeden mod seçimi — tam olarak ve güvenilir biçimde veriyor. Bedeli daha
 * çok global kısayol kaydetmek; onu da çakışma bildirimiyle görünür kılıyoruz.
 *
 * ## Kayıt başarısız olursa
 *
 * Bir kısayol başka bir uygulama tarafından kapılmış olabilir. Bunu sessizce
 * geçmiyoruz: kullanıcı neden çalışmadığını bilmeli, yoksa uygulamayı bozuk
 * sanar.
 */

/** Modun kimliği ile kısayolu. Motor tarafındaki `ModeId` ile eşleşir. */
export interface ModeBinding {
  mode: string
  accelerator: string
  /** Kayıt başarılı oldu mu? Başarısızsa arayüzde uyarı gösterilir. */
  registered: boolean
}

/**
 * Mod → kısayol eşlemesi.
 *
 * Harfler motor tarafındaki `Mode.chord_key` değerleriyle aynı; mockup'taki
 * "K kod, E İngilizce, M mega-prompt" gösterimi böylece hâlâ doğru okunuyor.
 */
const MODE_ACCELERATORS: ReadonlyArray<{ mode: string; key: string }> = [
  { mode: 'quick', key: 'Space' },
  { mode: 'code', key: 'K' },
  { mode: 'translate_en', key: 'E' },
  { mode: 'mega_prompt', key: 'M' },
  { mode: 'image_prompt', key: 'G' },
  { mode: 'sql', key: 'S' },
  { mode: 'commit', key: 'C' },
  { mode: 'screen', key: 'R' },
]

export interface HotkeyRegistration {
  modes: ModeBinding[]
  /** Hiçbir alternatifi de tutmayan kısayollar — gerçekten kayıp olanlar. */
  conflicts: string[]
  /**
   * Çakışma yüzünden yedeğe düşen kısayollar (Faz 7.17).
   *
   * Arayüzün bunu göstermesi şart: kullanıcı Ctrl+Alt+K bekleyip
   * Ctrl+Shift+Alt+K'ya düşmüşse ve bunu bilmiyorsa, kısayolun "çalışmadığını"
   * düşünür.
   */
  reassigned: { intended: string; actual: string }[]
}

/**
 * Bir kısayolu kaydeder; tutmazsa alternatifleri dener (Faz 7.17).
 *
 * Eskiden çakışma yalnız **bildiriliyordu**: "bu kısayol alınmış". Kullanıcıya
 * düşen iş, çakışan uygulamayı bulup ayarını değiştirmekti — çoğu zaman
 * yapılmayacak bir iş. Artık çalışan bir alternatif bulunuyor.
 *
 * Sıra deterministik: aynı ortamda her açılışta aynı kısayol seçiliyor, yoksa
 * kullanıcı her gün başka bir tuşa basmak zorunda kalırdı.
 */
function registerWithFallback(
  intended: string,
  handler: () => void,
  outcome: { conflicts: string[]; reassigned: { intended: string; actual: string }[] },
): { accelerator: string; registered: boolean } {
  if (globalShortcut.register(intended, handler)) {
    return { accelerator: intended, registered: true }
  }

  // `Control+Alt+X` → `Control+Shift+Alt+X` → `Control+Alt+Shift+F<n>` yerine
  // yalnız değiştirici ekliyoruz: tuşun kendisini değiştirmek kullanıcının
  // kas hafızasını tamamen bozardı.
  const key = intended.replace(/^Control\+Alt\+/, '')
  const alternatives = [`Control+Shift+Alt+${key}`, `Super+Alt+${key}`]

  for (const candidate of alternatives) {
    if (globalShortcut.register(candidate, handler)) {
      console.warn(`[kısayol] ${intended} alınmış; ${candidate} kullanılıyor`)
      outcome.reassigned.push({ intended, actual: candidate })
      return { accelerator: candidate, registered: true }
    }
  }

  console.warn(`[kısayol] ${intended} ve alternatifleri kaydedilemedi`)
  outcome.conflicts.push(intended)
  return { accelerator: intended, registered: false }
}

export function registerHotkeys(dictation: DictationController): HotkeyRegistration {
  const modes: ModeBinding[] = []
  const outcome = {
    conflicts: [] as string[],
    reassigned: [] as { intended: string; actual: string }[],
  }

  for (const { mode, key } of MODE_ACCELERATORS) {
    const result = registerWithFallback(
      `Control+Alt+${key}`,
      () => void dictation.toggle(mode),
      outcome,
    )
    // Arayüz GERÇEKTEN bağlanan kısayolu göstermeli, istenen değil.
    modes.push({ mode, accelerator: result.accelerator, registered: result.registered })
  }

  // Sesli geçmiş araması (Faz 7.13). Kendi kısayolu var çünkü sonucu
  // yapıştırılmıyor — akışı diğer modlardan farklı.
  registerWithFallback('Control+Alt+A', () => void dictation.toggle('search'), outcome)

  // Yeniden yapıştırma (Faz 7.16). Global olmak ZORUNDA: pencere içi bir
  // düğmeye tıklamak DikteX'i öne getirir ve metin kendi penceremize
  // yapışırdı. Kullanıcı hedef pencereye tıklayıp buna basıyor.
  registerWithFallback('Control+Alt+V', () => dictation.retryPaste(), outcome)

  // İptal her modda aynı.
  registerWithFallback('Control+Alt+Escape', () => dictation.cancel(), outcome)

  // Duraklat/devam (Faz 7.4). Global olmak zorunda: kayıt sırasında HUD
  // bilinçli olarak odak almıyor, o yüzden pencere içi bir tuş buraya ulaşmaz.
  registerWithFallback('Control+Alt+P', () => void dictation.togglePause(), outcome)

  return { modes, conflicts: outcome.conflicts, reassigned: outcome.reassigned }
}

export function unregisterHotkeys(): void {
  globalShortcut.unregisterAll()
}
