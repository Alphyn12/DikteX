import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { Locale } from '@shared/ipc'
import { tr, type MessageKey, type Messages } from './tr'
import { en } from './en'

const DICTIONARIES: Record<Locale, Messages> = { tr, en }

interface I18nValue {
  locale: Locale
  t: (key: MessageKey) => string
  setLocale: (locale: Locale) => void
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
    return {
      locale,
      setLocale,
      t: (key) => dictionary[key],
    }
  }, [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n, I18nProvider içinde çağrılmalı')
  return value
}
