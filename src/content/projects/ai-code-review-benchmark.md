---
title: "ai-code-review-benchmark"
description: "Open-source benchmark LLM на задаче code review: 17 моделей, repeatable методология и 4 реальных production-бага."
link: https://github.com/svetkis/ai-code-review-benchmark
tags: [open-source, ai, code-review, benchmark]
status: active
---

Репозиторий с методологией для повторяемого сравнения моделей на code review.

## Что внутри

- Скрипты для прогона diff через OpenRouter API.
- Методика дедупликации и ручной разметки находок.
- Результаты теста на 17 моделях.

Лидеры после ручной разметки:

- Claude Sonnet 4.6 — $0.09 за реальный баг, 2/4 найдено.
- DeepSeek V4 Flash — $0.01, 1/4, 0% галлюцинаций.
- GPT-OSS 120B — почти бесплатно, но 56% шума.
