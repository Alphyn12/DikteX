import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/jetbrains-mono'
import '../design/tokens.css'
import '../design/base.css'
import { I18nProvider } from '../i18n/useI18n'
import { Hud } from '../screens/Hud'

/** Canlı dikte HUD'u — mockup 1c. Ayrı, saydam, her zaman üstte bir pencere. */
const container = document.getElementById('root')
if (!container) throw new Error('#root bulunamadı')

createRoot(container).render(
  <StrictMode>
    <I18nProvider>
      <Hud />
    </I18nProvider>
  </StrictMode>,
)
