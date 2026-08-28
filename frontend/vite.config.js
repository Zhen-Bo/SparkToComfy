import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue({ template: { compilerOptions: { comments: true } } })],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // The backend has no CORS middleware, so the frontend always calls the relative /v1 path and the dev server forwards it.
    // The WebSocket uses the same prefix.
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
})
