import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api is proxied to FastAPI so the app (and the SSE stream) use one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8010', changeOrigin: true } },
  },
})
