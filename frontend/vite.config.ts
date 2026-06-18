import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Local dev: proxy /api to FastAPI on :8000 (see frontend/.env.example).
// Cloud: set VITE_API_BASE_URL to Railway host, or use vercel.cloud.json rewrites.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
