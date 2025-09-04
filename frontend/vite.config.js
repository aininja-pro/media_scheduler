import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // 0.0.0.0 inside Docker
    port: 5173,
    strictPort: true,
    hmr: {
      // Browser connects on the published port (3001)
      clientPort: 3001,
    },
    watch: {
      // Help file change detection on some Docker/macOS setups
      usePolling: true,
      interval: 100,
    },
  },
})
