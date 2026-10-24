import { defineConfig } from 'vitest/config'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * CSP <meta> injectée dans index.html au build, sans 'unsafe-eval' : défense en
 * profondeur contre l'exécution de code par un PDF piégé (CVE-2024-4367).
 * Pas en dev : Vite y injecte un script inline (préambule React Refresh) que la
 * politique bloquerait. L'origine de VITE_API_URL est ajoutée à connect-src.
 */
function contentSecurityPolicy(): Plugin {
  let apiOrigin = ''
  return {
    name: 'histoolbox:csp',
    apply: 'build',
    configResolved(config) {
      const apiUrl = config.env.VITE_API_URL
      if (apiUrl) apiOrigin = new URL(apiUrl).origin
    },
    transformIndexHtml: () => [
      {
        tag: 'meta',
        attrs: {
          'http-equiv': 'Content-Security-Policy',
          content: [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            `connect-src 'self' ${apiOrigin}`.trim(),
            "object-src 'none'",
            "base-uri 'self'",
          ].join('; '),
        },
        injectTo: 'head-prepend',
      },
    ],
  }
}

export default defineConfig({
  // En prod GitHub Pages : VITE_BASE_PATH=/histoolbox/
  // En dev local          : non défini → '/'
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [
    react(),
    tailwindcss(),
    contentSecurityPolicy(),
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
