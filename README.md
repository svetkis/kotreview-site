# KotReview — личный сайт

Лендинг-визитка и медиа-хаб для [kotreview.ru](https://kotreview.ru).

Сделан на [Astro](https://astro.build) со статической генерацией. Хостится бесплатно на GitHub Pages. VPS не нужен.

## Структура

- `src/content/posts/` — заметки и мысли (Markdown + frontmatter).
- `src/content/talks/` — доклады с YouTube и слайдами.
- `src/content/projects/` — проекты и боты.
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

Аналогично для докладов (`src/content/talks/`) и проектов (`src/content/projects/`).

## Деплой

При пуше в ветку `main` GitHub Actions автоматически собирает сайт и публикует его на GitHub Pages.

### Подключить свой домен

1. В настройках репозитория включи GitHub Pages (Source: GitHub Actions).
2. В разделе Pages добавь кастомный домен `kotreview.ru`.
3. У регистратора домена укажи DNS-записи для GitHub Pages:
   - A-записи: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - или CNAME на `<username>.github.io` (если домен через www).

Файл `public/CNAME` уже содержит `kotreview.ru`.
