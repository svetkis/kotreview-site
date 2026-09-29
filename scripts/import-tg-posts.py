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

# Сессия может лежать рядом с репозиторием на любом из дисков
SESSION_CANDIDATES = [
    Path("D:/Repos/.telegram-sessions/master"),
    Path("C:/Repos/.telegram-sessions/master"),
]
SESSION_PATH = next((p for p in SESSION_CANDIDATES if p.with_suffix(".session").exists()), SESSION_CANDIDATES[0])
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


def collect_existing_sources(posts_dir: Path) -> set[str]:
    """Собирает source URL из уже импортированных постов."""
    sources = set()
    for path in posts_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^source:\s*(.+)$", text, re.MULTILINE)
        if m:
            sources.add(m.group(1).strip())
    return sources


def sniff_kind(path: Path) -> str:
    """Определяет тип скачанного файла по magic bytes."""
    b = path.read_bytes()[:16]
    if b[4:8] == b"ftyp":
        return "video"
    if b.startswith(b"\xff\xd8") or b[8:12] == b"WEBP" or b.startswith(b"\x89PNG") or b.startswith(b"GIF8"):
        return "image"
    return "image"


async def download_photos(client, messages, image_prefix: str) -> list[tuple[str, str]]:
    """Скачивает фото из сообщений. Видео не хостим на сайте — оно живёт на YouTube."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    media = []
    idx = 1
    for msg in messages:
        if msg.video or msg.video_note:
            continue
        if not msg.photo:
            continue
        filename = f"{image_prefix}-{idx}.jpg"
        local_path = IMAGES_DIR / filename
        await client.download_media(msg.media, file=str(local_path))
        if sniff_kind(local_path) != "image":
            local_path.unlink()
            print(f"  ! Пропуск id={msg.id}: скачался не-фото файл")
            continue
        media.append((f"/images/posts/{local_path.name}", "image"))
        idx += 1
    return media


def build_markdown(
    title: str,
    date: datetime,
    description: str,
    tags: list[str],
    source: str,
    media: list[tuple[str, str]],
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
    for path, kind in media:
        if kind == "video":
            lines.append(
                f'<video controls preload="none" src="{path}" '
                f'style="max-width:100%;border-radius:12px;display:block;margin:1rem 0;"></video>'
            )
        else:
            lines.append(f"![{title}]({path})")
    if media:
        lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


async def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    existing_slugs = {p.stem for p in POSTS_DIR.glob("*.md")}
    existing_sources = collect_existing_sources(POSTS_DIR)

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

        if source in existing_sources:
            print(f"  Пропуск id={msg_id}: уже импортировано")
            skipped += 1
            continue

        slug = make_unique_slug(date_str, title, msg_id, existing_slugs)
        md_path = POSTS_DIR / f"{slug}.md"

        # Скачиваем медиа (фото и видео)
        image_prefix = f"{date_str}-{msg_id}"
        media = await download_photos(client, grp, image_prefix)

        md_content = build_markdown(
            title=title,
            date=date,
            description=description,
            tags=tags,
            source=source,
            media=media,
            body=body,
        )

        md_path.write_text(md_content, encoding="utf-8")
        print(f"  Создан: {md_path.name} (id={msg_id}, медиа={len(media)})")
        created += 1

    await client.disconnect()
    print(f"\nГотово: создано {created}, пропущено {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
