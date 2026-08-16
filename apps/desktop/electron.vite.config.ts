import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'electron/main/index.ts') },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'electron/preload/index.ts') },
      },
    },
  },
  renderer: {
    root: resolve(__dirname, 'src'),
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@shared': resolve(__dirname, 'shared'),
      },
    },
    build: {
      rollupOptions: {
        input: {
          // Her yüzen katman kendi penceresinde, kendi giriş noktasıyla çalışır.
          main: resolve(__dirname, 'src/main.html'),
          hud: resolve(__dirname, 'src/hud.html'),
          commandbar: resolve(__dirname, 'src/commandbar.html'),
        },
      },
    },
    plugins: [react()],
  },
})
