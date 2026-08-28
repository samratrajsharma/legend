import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// Multi-page: the marketing landing page (index.html) + the documentation page (docs.html).
export default defineConfig({
  base: './',                      // relative asset paths so it works on any GitHub Pages subpath
  plugins: [react()],
  server: { port: 5300, host: true },
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        docs: fileURLToPath(new URL('./docs.html', import.meta.url)),
      },
    },
  },
})
