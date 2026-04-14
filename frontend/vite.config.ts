import { defineConfig } from 'vite'
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
    // Redirige toutes les routes inconnues vers index.html pour le routeur client
    historyApiFallback: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
