import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env vars so we can use VITE_API_URL when running in Docker or locally
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      host: true,
      watch: {
        usePolling: true,
      },
      proxy: {
        '/auth': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/cycles': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/predictions': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  }
})
