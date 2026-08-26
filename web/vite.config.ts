import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    // The backend binds 127.0.0.1 only; the proxy keeps the frontend
    // free of any hardcoded host or port.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', ws: true, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
  },
});
