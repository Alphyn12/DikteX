import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

/**
 * Takma adlar üç hedefte de tanımlı olmalı.
 *
 * `@shared` yalnız tip taşısaydı derleme sırasında silinir ve çözümlenmesi
 * gerekmezdi; içinde çalışma zamanı değerleri de (varsayılan durumlar,
 * sabitler) olduğu için main ve preload derlemeleri de bu takma adı bilmek
 * zorunda.
 */
const alias = {
  '@': resolve(__dirname, 'src'),
  '@shared': resolve(__dirname, 'shared'),
}

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    resolve: { alias },
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'electron/main/index.ts') },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    resolve: { alias },
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'electron/preload/index.ts') },
      },
    },
  },
  renderer: {
    root: resolve(__dirname, 'src'),
    resolve: { alias },
    build: {
      rollupOptions: {
        input: {
          // Her yüzen katman kendi penceresinde, kendi giriş noktasıyla çalışır.
          main: resolve(__dirname, 'src/main.html'),
          hud: resolve(__dirname, 'src/hud.html'),
          commandbar: resolve(__dirname, 'src/commandbar.html'),
          region: resolve(__dirname, 'src/region.html'),
        },
      },
    },
    plugins: [react()],
  },
})
