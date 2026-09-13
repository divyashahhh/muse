import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In dev, the API is same-origin via this proxy; in production set VITE_API_URL.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
