# KotReview — личный сайт

Лендинг-визитка и медиа-хаб для [kotreview.ru](https://kotreview.ru).

Сделан на [Astro](https://astro.build) со статической генерацией. Хостится бесплатно на GitHub Pages. VPS не нужен.

## Структура

- `src/content/posts/` — заметки и мысли (Markdown + frontmatter).
- `src/content/talks/` — доклады с YouTube и слайдами.
- `src/content/projects/` — проекты и боты.
- `src/content/links/` — каталог ссылок для страницы `/links` (QR на стикерпаке).
- `src/pages/` — страницы сайта.
- `src/components/` — переиспользуемые компоненты.
- `src/layouts/` — шаблоны страниц.
- `public/CNAME` — кастомный домен `kotreview.ru`.

## Локальная разработка

```bash
npm install
npm run dev
```

Сайт будет доступен на `http://localhost:4321`.

## Добавить пост

Создай файл `src/content/posts/YYYY-MM-DD-slug.md`:

```md
---
title: "Заголовок"
date: 2026-06-25
description: "Краткое описание"
tags: [ai, agents]
source: https://t.me/kot_review/...
---

Текст поста в Markdown.
```

Аналогично для докладов (`src/content/talks/`), проектов (`src/content/projects/`) и ссылок (`src/content/links/`).

## Каталог ссылок `/links`

Мобильный каталог для QR-кода с бумажного стикерпака: `https://kotreview.ru/links`.

Ссылка — это md-файл в `src/content/links/`:

```md
---
title: "Telegram-канал «Кот Review»"
url: https://t.me/kot_review
description: "необязательно"
emoji: "📢"
section: "Канал и соцсети"
order: 10
---
```

`order` — позиция внутри секции. Порядок секций задан списком `SECTION_ORDER` в `src/pages/links.astro`.

## Скрипты

### Импорт постов из Telegram

```bash
pip install telethon
python scripts/import-tg-posts.py
```

Скачивает посты из канала `@kot_review` (сессия в `C:/Repos/.telegram-sessions/master`), создаёт md-файлы, картинки и видео. Уже импортированные посты пропускаются по `source`-ссылке.

После импорта сгенерируй og-обложки для карточек ссылок (VK/Telegram):

```bash
node scripts/make-og-images.mjs
```

### Кросспостинг в VK-группу

```bash
cp scripts/.env.example scripts/.env   # заполнить VK_GROUP_ID и VK_COMMUNITY_TOKEN
python scripts/post-to-vk.py --dry-run # посмотреть, что уйдёт
python scripts/post-to-vk.py           # отправить до 3 новых постов
```

Токен: Управление сообществом → Работа с API → Ключи доступа, права «Фото» и «Стена». Отправленные посты помечаются в `scripts/.vk-state.json` (не коммитится) и повторно не отправляются. Полезные флаги: `--limit N`, `--all`, `--since YYYY-MM-DD`, `--slug подстрока`.

## Деплой

При пуше в ветку `main` GitHub Actions автоматически собирает сайт и публикует его на GitHub Pages.

### Подключить свой домен

1. В настройках репозитория включи GitHub Pages (Source: GitHub Actions).
2. В разделе Pages добавь кастомный домен `kotreview.ru`.
3. У регистратора домена укажи DNS-записи для GitHub Pages:
   - A-записи: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - или CNAME на `<username>.github.io` (если домен через www).

Файл `public/CNAME` уже содержит `kotreview.ru`.
