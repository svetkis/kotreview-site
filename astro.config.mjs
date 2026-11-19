// @ts-check
import { defineConfig } from 'astro/config';
import remarkGfm from 'remark-gfm';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  site: 'https://kotreview.ru',
  // GFM: зачёркивания ~~...~~, таблицы, автолинки — форматировка из Телеграма
  markdown: {
    remarkPlugins: [remarkGfm]
  },
  // base is '/' by default; keep it unset for custom domain root
  build: {
    format: 'directory'
  }
});
