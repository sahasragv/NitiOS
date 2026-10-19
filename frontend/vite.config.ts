import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  // Forward API calls to the FastAPI backend so the browser sees one origin in development.
  server: { proxy: { '/api': { target: process.env.SETU_API_PROXY_TARGET ?? 'http://localhost:8000', changeOrigin: true } } },
})
