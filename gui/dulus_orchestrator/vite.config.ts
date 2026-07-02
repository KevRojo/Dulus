import path from 'path';
import fs from 'fs';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';

// After the single-file build, copy dist/index.html → dist/standalone.html
// (dulus_gui.py loads dist/standalone.html via a file:// URI).
const emitStandalone = () => ({
  name: 'emit-standalone-html',
  closeBundle() {
    const dist = path.resolve(__dirname, 'dist');
    const src = path.join(dist, 'index.html');
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(dist, 'standalone.html'));
    }
  },
});

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    return {
      base: './',
      define: {
        // This is just generic value for the GEMINI API key.
        // This is not used at all, and can be ignored!
        'process.env.API_KEY' : JSON.stringify('api-key-this-is-not-used-can-be-ignored!'),
      },
      server: {
        proxy: {
          //Target your Node.js backend
          '/api-proxy': 'http://localhost:5000',
          '/ws-proxy': {target: 'ws://localhost:5000', ws: true},
        },
      },
      plugins: [react(), viteSingleFile(), emitStandalone()],
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});

