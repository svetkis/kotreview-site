// Генерирует og-обложки 1200x630 для карточек ссылок (VK, Telegram, Twitter).
// Обложка = кроп первой картинки поста (cover, авто-фокус на важном).
// Имя обложки = имя исходной картинки (ASCII): кириллические URL VK не переваривает.
// Запуск: node scripts/make-og-images.mjs  (после каждого импорта постов)

import { readdir, readFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import sharp from 'sharp';

const POSTS = 'src/content/posts';
const OG = 'public/images/og';

await mkdir(OG, { recursive: true });

let made = 0;
let skipped = 0;
for (const f of (await readdir(POSTS)).filter((f) => f.endsWith('.md')).sort()) {
  const stem = f.replace(/\.md$/, '');
  const md = await readFile(`${POSTS}/${f}`, 'utf8');
  // первый локальный путь /images/... в markdown-картинке
  // (регэксп по src, потому что alt-текст может содержать вложенные markdown-ссылки)
  const m = md.match(/\]\((\/images\/[^)]+)\)/);
  if (!m) {
    console.log(`- ${stem}: нет картинки`);
    skipped++;
    continue;
  }
  const src = `public${m[1]}`;
  if (!existsSync(src)) {
    console.log(`! ${stem}: файл не найден ${src}`);
    skipped++;
    continue;
  }
  const out = `${OG}/${m[1].split('/').pop()}`;
  if (existsSync(out)) {
    skipped++;
    continue;
  }
  try {
    await sharp(src)
      .resize(1200, 630, { fit: 'cover', position: 'attention' })
      .jpeg({ quality: 82 })
      .toFile(out);
    made++;
  } catch (e) {
    console.log(`! ${stem}: ${e.message}`);
    skipped++;
  }
}
console.log(`Готово: создано ${made}, пропущено ${skipped}`);
