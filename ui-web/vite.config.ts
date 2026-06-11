import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, mkdirSync, readdirSync } from 'fs'
import { resolve } from 'path'
import type { Plugin } from 'vite'

function copyLanding(): Plugin {
  return {
    name: 'copy-landing',
    closeBundle() {
      const landing = resolve(__dirname, '../landing')
      const out = resolve(__dirname, 'dist/landing')
      mkdirSync(out, { recursive: true })
      for (const file of readdirSync(landing)) {
        copyFileSync(resolve(landing, file), resolve(out, file))
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), copyLanding()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
