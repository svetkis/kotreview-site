---
title: "triage-and-voice"
description: "Open-source репозиторий с подходом к классификации запросов и озвучиванию ответа для безопасного использования LLM в продакшене."
link: https://github.com/svetkis/triage-and-voice
tags: [open-source, ai, llm, safety, python]
status: active
---

Проект родился после серии статей на Хабре про то, как LLM галлюцинирует под капотом продукта.

## Идея

- Один вызов LLM классифицирует запрос.
- Код решает, что можно говорить.
- Второй вызов озвучивает ответ с размеченными полями данных.

Это убирает пустоту, которую модель могла бы заполнить выдумкой. Промптом или RAG такое не решить.

## Репозитории

- [triage-and-voice](https://github.com/svetkis/triage-and-voice)
- [triage-voice-eval](https://github.com/svetkis/triage-voice-eval)
