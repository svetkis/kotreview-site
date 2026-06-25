---
title: "Claude не пользуется Serena, хотя она подключена. Что делать?"
date: 2026-04-17
description: "Ставишь Serena, проверяешь /mcp — Connected, всё зелёное. Начинаешь работать. И видишь, что Claude грепает, про find_symbol вообще не вспоминает. Как будто..."
tags: ["agents", "ai", "claude"]
source: https://t.me/kot_review/21
---

Ставишь Serena, проверяешь /mcp — Connected, всё зелёное. Начинаешь работать. И видишь, что Claude грепает, про find_symbol вообще не вспоминает. Как будто Serena нет.

Окей, тыкаешь его носом: «используй Serena для навигации по коду». Он подхватывает, начинает дёргать find_symbol, get_symbols_overview, ура. Проходит полчаса, и он снова грепает.

Это вторая сторона проблемы. На GitHub её сформулировали: when you start a new session with CC Serena is a very active participant in the conversation but as the conversation grows Serena's participation is less and less to the point where it's never used again.

Причина — то, как Claude Code работает с контекстом и динамической загрузкой инструментов. Системные инструкции Serena постепенно выдавливаются из окна, и агент просто забывает, что у него есть эти инструменты. В сообществе это называют agent drift, и сама документация Serena это признаёт: the agent will often fail to make proper use of Serena's tools, either by failing to load them in the beginning or by forgetting the instructions in a long session.

Что с этим делать.

В документации Serena предлагают hooks — систему reminder-хуков, которые подкидывают агенту инструкции на старте и периодически по ходу сессии. Настраивается через .claude/settings.json. Сама я их пока не щупала, это alpha-фича, но по описанию это ровно то, что нужно. Поговаривают, что пока hooks могут жрать токены, жду какой-то стабилизации фичи.

Мой подход проще, это битье в бубен в начале сессии агента:

- жду, пока Serena запустится (10-15 секунд для нее норма)
- проверяю через /mcp, что она живая
- первой командой говорю: «используй Serena для навигации по коду»
- держу короткие сессии, это также помогает сократить расход токенов

Моя искренняя благодарность Льву @levyas, который подсказал рабочие лайфхаки.
