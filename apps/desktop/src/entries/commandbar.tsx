import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/jetbrains-mono'
import '../design/tokens.css'
import '../design/base.css'

/**
 * Floating Command Bar — imlecin yanında beliren komut çubuğu (mockup 1b).
 * Faz 3.14'te doldurulacak.
 */
const container = document.getElementById('root')
if (!container) throw new Error('#root bulunamadı')

createRoot(container).render(
  <StrictMode>
    <div />
  </StrictMode>,
)
