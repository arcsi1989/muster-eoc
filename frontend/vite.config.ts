import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The backend's routes have no /api prefix (docs/IMPLEMENTATION_PLAN.md section 6).
      '/api': { target: 'http://localhost:8000', rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
