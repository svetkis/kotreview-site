#!/usr/bin/env python3
"""
Импорт постов из Telegram-канала @kot_review в Astro content collection.

Использует сессию из D:/Repos/.telegram-sessions/master
и credentials из проекта tg_scaner.

Скачивает текст, фото и создаёт Markdown-файлы в src/content/posts/.
"""

import asyncio
import io
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient

# Раскраска stdout/stderr для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API_ID = "18244066"
API_HASH = "6b2601ab6875b4c00687faab6073ea5a"
SESSION_PATH = "D:/Repos/.telegram-sessions/master"
CHANNEL = "kot_review"

# Пути относительно корня проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = PROJECT_ROOT / "src" / "content" / "posts"
IMAGES_DIR = PROJECT_ROOT / "public" / "images" / "posts"

# Пропускаем первые два сообщения канала (id 1 и 2)
SKIP_IDS = {1, 2}


def slugify(text: str) -> str:
    """Превращает строку в безопасный для файлов slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:60].strip("-")


def extract_title(text: str) -> str:
    """Вытаскивает заголовок из текста: первая жирная строка или первые слова."""
    lines = text.splitlines()
    for line in lines[:3]:
        line = line.strip()
        # Жирный markdown с эмодзи/цифрами впереди
        m = re.match(r"^(?:\d+\s*[️⃣]\s*)?\*\*(.+?)\*\*$", line)
        if m:
            return m.group(1).strip()
        # Жирный markdown
        if line.startswith("**") and line.endswith("**"):
            return line.strip("*").strip()
    # Первая непустая строка
    for line in lines:
        line = line.strip()
        if line:
            return re.sub(r"\*+", "", line).strip()
    return "Без названия"


def clean_body(text: str, title: str) -> str:
    """Убирает первый заголовок из тела, если он совпадает с title."""
    lines = text.splitlines()
    if not lines:
        return text
    first = lines[0].strip()
    # Если первая строка — жирный заголовок, совпадающий с title
    normalized_title = re.sub(r"\s+", " ", title.lower().replace("😢", "").replace("👾", "").strip())
    normalized_first = re.sub(r"\*+", "", first.lower()).strip()
    normalized_first = re.sub(r"\s+", " ", normalized_first)
    if normalized_first == normalized_title or normalized_first.startswith(normalized_title):
        body = "\n".join(lines[1:]).strip()
        return body
    return text


def extract_description(text: str, title: str = "") -> str:
    """Берёт первые ~150 символов текста без markdown и без заголовка."""
    # Убираем заголовок, если он есть
    text = clean_body(text, title)
    plain = re.sub(r"\*+", "", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= 160:
        return plain
    return plain[:157].rsplit(" ", 1)[0] + "..."


def extract_tags(text: str) -> list[str]:
    """Хэштеги из текста плюс базовые теги."""
    tags = set()
    for tag in re.findall(r"#(\w+)", text):
        tags.add(tag.lower())
    # Базовые теги по ключевым словам
    lowered = text.lower()
    if any(w in lowered for w in ["kimi", "moonshot"]):
        tags.add("kimi")
    if "claude" in lowered or "fable" in lowered:
        tags.add("claude")
    if "codex" in lowered:
        tags.add("codex")
    if "агент" in lowered or "agents" in lowered:
        tags.add("agents")
    if any(w in lowered for w in ["ai", "ии", "нейросет", "llm", "модел"]):
        tags.add("ai")
    if not tags:
        tags.add("ai")
    return sorted(tags)


def make_unique_slug(date_str: str, title: str, msg_id: int, existing: set[str]) -> str:
    """Генерирует уникальный slug."""
    base = f"{date_str}-{slugify(title)}" or f"{date_str}-post"
    slug = base
    suffix = 1
    while slug in existing:
        slug = f"{base}-{msg_id}"
        if slug in existing:
            slug = f"{base}-{msg_id}-{suffix}"
            suffix += 1
    existing.add(slug)
    return slug


async def download_photos(client, messages, image_prefix: str) -> list[str]:
    """Скачивает фото из сообщений, возвращает список относительных путей."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    idx = 1
    for msg in messages:
        if not msg.photo:
            continue
        ext = "jpg"
        filename = f"{image_prefix}-{idx}.{ext}"
        local_path = IMAGES_DIR / filename
        await client.download_media(msg.media, file=str(local_path))
        paths.append(f"/images/posts/{filename}")
        idx += 1
    return paths


def build_markdown(
    title: str,
    date: datetime,
    description: str,
    tags: list[str],
    source: str,
    image_paths: list[str],
    body: str,
) -> str:
    """Собирает итоговый Markdown-файл."""
    tags_line = ", ".join(f'"{tag}"' for tag in tags)
    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(92)+chr(34))}"',
        f"date: {date.date().isoformat()}",
        f'description: "{description.replace(chr(34), chr(92)+chr(34))}"',
        f"tags: [{tags_line}]",
        f"source: {source}",
        "---",
        "",
    ]
    for img in image_paths:
        lines.append(f"![{title}]({img})")
    if image_paths:
        lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


async def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    existing_slugs = {p.stem for p in POSTS_DIR.glob("*.md")}

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Сессия не авторизована. Проверь путь к сессии.")
        return 1

    entity = await client.get_entity(CHANNEL)
    print(f"Канал: {entity.title} (@{entity.username})")

    # Собираем сообщения
    messages = []
    async for msg in client.iter_messages(entity, min_id=2):
        if msg.id in SKIP_IDS:
            continue
        messages.append(msg)

    print(f"Найдено сообщений для импорта: {len(messages)}")

    # Группируем альбомы
    grouped = defaultdict(list)
    singles = []
    for msg in messages:
        if msg.grouped_id:
            grouped[msg.grouped_id].append(msg)
        else:
            singles.append([msg])

    # Объединяем альбомы в один пост
    posts = singles + [sorted(grp, key=lambda m: m.id) for grp in grouped.values()]
    # Сортируем по дате (новые сверху)
    posts.sort(key=lambda grp: grp[0].date, reverse=True)

    created = 0
    skipped = 0

    for grp in posts:
        first = grp[0]
        msg_id = first.id
        date = first.date.astimezone(timezone.utc)
        date_str = date.date().isoformat()

        # Текст берём из первого непустого сообщения
        body = "\n\n".join(m.text for m in grp if m.text).strip()
        if not body and not any(m.photo for m in grp):
            print(f"  Пропуск id={msg_id}: пустое сообщение")
            skipped += 1
            continue

        title = extract_title(body) or f"Пост от {date_str}"
        body = clean_body(body, title)
        description = extract_description(body, title) if body else title
        tags = extract_tags(body)
        source = f"https://t.me/{CHANNEL}/{msg_id}"

        slug = make_unique_slug(date_str, title, msg_id, existing_slugs)
        md_path = POSTS_DIR / f"{slug}.md"

        # Скачиваем фото
        image_prefix = f"{date_str}-{msg_id}"
        image_paths = await download_photos(client, grp, image_prefix)

        md_content = build_markdown(
            title=title,
            date=date,
            description=description,
            tags=tags,
            source=source,
            image_paths=image_paths,
            body=body,
        )

        md_path.write_text(md_content, encoding="utf-8")
        print(f"  Создан: {md_path.name} (id={msg_id}, фото={len(image_paths)})")
        created += 1

    await client.disconnect()
    print(f"\nГотово: создано {created}, пропущено {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
