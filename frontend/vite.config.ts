import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/upload': 'http://localhost:7860',
      '/video':  'http://localhost:7860',
      '/health': 'http://localhost:7860',
      '/ws':     { target: 'ws://localhost:7860', ws: true },
    },
  },
  build: { outDir: 'dist' },
})
