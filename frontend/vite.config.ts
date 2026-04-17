import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      // Proxy uniquement les routes API du backend (pas les routes frontend /ocr/waiting, /ocr/toolbox)
      '^/ocr/(upload|status|result)': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
    // Vite gère le fallback SPA via le mode History nativement — pas besoin d'option manuelle
    // historyApiFallback est une option webpack-dev-server, pas vite
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
