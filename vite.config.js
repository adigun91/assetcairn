import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: { deny: ['**/backend/**', '**/data/**', '**/*.py', '**/*.sqlite3'] },
    proxy: { '/api': `http://127.0.0.1:${process.env.DJANGO_PORT || 3001}` },
  },
  build: { outDir: 'dist' }
});