import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { Locale } from '@shared/ipc'
import { tr, type MessageKey, type Messages } from './tr'
import { en } from './en'

const DICTIONARIES: Record<Locale, Messages> = { tr, en }

/** `{ad}` biçimindeki yer tutucular için değerler. */
export type TranslateParams = Record<string, string | number>

/** Intl için tam dil etiketleri. */
const INTL_LOCALE: Record<Locale, string> = { tr: 'tr-TR', en: 'en-US' }

interface I18nValue {
  locale: Locale
  t: (key: MessageKey, params?: TranslateParams) => string
  setLocale: (locale: Locale) => void
  /**
   * Sayıyı dile göre biçimler. Binlik ve ondalık ayırıcılar dilden dile
   * değişir (tr: 4.812 / 1,1 · en: 4,812 / 1.1); sayıları veride metin olarak
   * saklamak bu farkı gizler.
   */
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string
  /** Tarihi dile göre biçimler. */
  formatDate: (value: Date, options: Intl.DateTimeFormatOptions) => string
}

/**
 * `{ad}` yer tutucularını doldurur.
 *
 * Karşılığı verilmeyen yer tutucu olduğu gibi bırakılır — sessizce boş
 * bırakmak, eksikliği fark edilmeyen bozuk bir cümle üretir.
 */
function interpolate(template: string, params?: TranslateParams): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name]
    return value === undefined ? match : String(value)
  })
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const [locale, setLocaleState] = useState<Locale>('tr')

  useEffect(() => {
    void window.omnivoice.invoke('app:get-locale').then(setLocaleState)
    return window.omnivoice.on('app:locale-changed', setLocaleState)
  }, [])

  // Dil, ekran okuyucuların ve tarayıcı tipografisinin doğru davranması için
  // belge kökünde de bildirilir.
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    // İyimser güncelleme: main process onaylamadan da arayüz anında dönsün.
    setLocaleState(next)
    void window.omnivoice.invoke('app:set-locale', next)
  }, [])

  const value = useMemo<I18nValue>(() => {
    const dictionary = DICTIONARIES[locale]
    const intlLocale = INTL_LOCALE[locale]
    return {
      locale,
      setLocale,
      t: (key, params) => interpolate(dictionary[key], params),
      formatNumber: (value, options) => new Intl.NumberFormat(intlLocale, options).format(value),
      formatDate: (value, options) => new Intl.DateTimeFormat(intlLocale, options).format(value),
    }
  }, [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n, I18nProvider içinde çağrılmalı')
  return value
}
