import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Same cap as pytest in scripts/check.sh: CHECK_WORKERS (default 4), or "auto" for one per CPU.
const checkWorkers = process.env.CHECK_WORKERS ?? '4'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The backend's routes have no /api prefix (docs/IMPLEMENTATION_PLAN.md section 6).
      '/api': { target: 'http://localhost:8000', rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    maxWorkers: checkWorkers === 'auto' ? undefined : Number(checkWorkers),
  },
})
