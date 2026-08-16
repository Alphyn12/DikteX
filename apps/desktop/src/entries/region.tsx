import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/jetbrains-mono'
import '../design/tokens.css'
import '../design/base.css'
import { I18nProvider } from '../i18n/useI18n'
import { RegionSelector } from '../screens/RegionSelector'

/** Ekran bölgesi seçim kaplaması — tüm sanal masaüstünü kaplayan pencere. */
const container = document.getElementById('root')
if (!container) throw new Error('#root bulunamadı')

createRoot(container).render(
  <StrictMode>
    <I18nProvider>
      <RegionSelector />
    </I18nProvider>
  </StrictMode>,
)