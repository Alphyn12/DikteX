import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/jetbrains-mono'
import '../design/tokens.css'
import '../design/base.css'
import { I18nProvider } from '../i18n/useI18n'
import { Hud } from '../screens/Hud'
import { MeetingHud } from '../screens/MeetingHud'

/**
 * Yüzen katman penceresi.
 *
 * Dikte ve toplantı HUD'ları aynı pencereyi paylaşır — ikisi aynı mikrofonu
 * kullandığı için aynı anda çalışamazlar (motor da bunu engelliyor). Her
 * bileşen kendi durumu boştayken `null` döndürüyor, bu yüzden ikisi yan yana
 * durabiliyor.
 */
const container = document.getElementById('root')
if (!container) throw new Error('#root bulunamadı')

createRoot(container).render(
  <StrictMode>
    <I18nProvider>
      <Hud />
      <MeetingHud />
    </I18nProvider>
  </StrictMode>,
)
