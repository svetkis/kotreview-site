// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  site: 'https://kotreview.ru',
  // base is '/' by default; keep it unset for custom domain root
  build: {
    format: 'directory'
  }
});
