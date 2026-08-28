import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',                      // relative asset paths so it works on any GitHub Pages subpath
  plugins: [react()],
  server: { port: 5300, host: true },
})
