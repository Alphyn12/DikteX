import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/jetbrains-mono'
import '../design/tokens.css'
import '../design/base.css'

/**
 * Canlı dikte HUD'u — dinliyor · işliyor · pre-flight (mockup 1c).
 * Faz 2.8'de doldurulacak. Giriş noktası şimdiden var ki pencere yönetimi ve
 * paketleme yapılandırması tek seferde oturmuş olsun.
 */
const container = document.getElementById('root')
if (!container) throw new Error('#root bulunamadı')

createRoot(container).render(
  <StrictMode>
    <div />
  </StrictMode>,
)
