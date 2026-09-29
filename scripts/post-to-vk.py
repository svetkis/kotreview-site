#!/usr/bin/env python3
"""
Кросспостинг постов из src/content/posts (импорт из Telegram) на стену VK-группы.

Что делает:
  - читает Markdown-посты (frontmatter: title, date, source; картинки в теле);
  - конвертирует Markdown в plain text для VK;
  - заливает картинки как документы на стену (docs API): прямая загрузка фото и
    вложения-ссылки ключом сообщества VK запрещены;
  - публикует wall.post от имени группы (from_group=1);
  - помечает отправленные посты в scripts/.vk-state.json (повторно не отправляет).

Настройка (scripts/.env, не коммитится):
  VK_GROUP_ID=kot_review          — числовой ID группы или короткое имя (без минуса)
  VK_COMMUNITY_TOKEN=...          — ключ доступа сообщества с правами «Стена» и «Документы»
  SITE_URL=https://kotreview.ru   (опционально)

Запуск:
  python scripts/post-to-vk.py --dry-run          # показать, что уйдёт в VK
  python scripts/post-to-vk.py                    # отправить до 3 новых постов
  python scripts/post-to-vk.py --limit 10         # отправить до 10
  python scripts/post-to-vk.py --slug питер       # один конкретный пост по части slug
  python scripts/post-to-vk.py --since 2026-09-01 # только посты с этой даты

VK ограничивает частоту wall.post, поэтому между постами пауза 3 секунды.
"""

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = PROJECT_ROOT / "src" / "content" / "posts"
PUBLIC_DIR = PROJECT_ROOT / "public"
STATE_PATH = Path(__file__).resolve().parent / ".vk-state.json"
ENV_PATH = Path(__file__).resolve().parent / ".env"

VK_API = "https://api.vk.com/method/"
VK_API_VERSION = "5.199"
PAUSE_BETWEEN_POSTS = 3.0


def load_env() -> dict[str, str]:
    env = {"SITE_URL": "https://kotreview.ru"}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


class VkError(RuntimeError):
    def __init__(self, method: str, code, msg):
        super().__init__(f"VK {method}: [{code}] {msg}")
        self.code = code


def vk_call(token: str, method: str, **params) -> dict:
    params = {k: v for k, v in params.items() if v is not None}
    params["access_token"] = token
    params["v"] = VK_API_VERSION
    resp = requests.post(VK_API + method, data=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        err = data["error"]
        raise VkError(method, err.get("error_code"), err.get("error_msg"))
    return data["response"]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w+):\s*(.*)$", line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"')
    return meta, m.group(2)


def extract_images(body: str) -> tuple[list[str], str]:
    """Вырезает markdown-картинки, возвращает (список путей, текст без них)."""
    paths: list[str] = []

    def _grab(m: re.Match) -> str:
        paths.append(m.group(1))
        return ""

    text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", _grab, body)
    return paths, text


def markdown_to_plain(text: str) -> str:
    # Код — просто убрать бэктики
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Ссылки: [текст](url) -> текст (url); если текст и url совпадают — просто url
    def _link(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        return url if label.strip() == url.strip() else f"{label} ({url})"

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, text)
    # Жирный/курсив
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    # Заголовки
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Списки: "- " -> "• "
    text = re.sub(r"^\s*[-•]\s+", "• ", text, flags=re.MULTILINE)
    # Схлопнуть 3+ перевода строк
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_message(meta: dict, body: str, slug: str, site_url: str, with_site_link: bool = True) -> str:
    title = meta.get("title", "")
    plain = markdown_to_plain(body)
    parts = []
    if title:
        parts.append(title)
    if plain and plain != title:
        parts.append(plain)
    source = meta.get("source", "")
    footer = []
    if with_site_link:
        footer.append(f"—")
        footer.append(f"Подробнее: {site_url}/posts/{slug}/")
    if source:
        footer.append(f"Оригинал: {source}" if footer else f"Оригинал: {source}")
    if footer:
        parts.append("\n".join(footer))
    return "\n\n".join(parts)


def upload_photo(token: str, group_id: int, image_path: Path, retries: int = 4) -> str:
    """Загружает фото на стену группы как документ (docs API).

    Прямая загрузка фото (photos.getWallUploadServer) недоступна ключом
    сообщества (VK error 27), а вложения-ссылки VK не принимает вовсе —
    поэтому фото едет документом. Upload-серверы VK периодически болеют
    (504, no_file_no_tmp_dir), так что берём свежий URL на каждую попытку.
    """
    last_err = "unknown"
    for attempt in range(retries):
        try:
            server = vk_call(token, "docs.getWallUploadServer", group_id=group_id)
            with open(image_path, "rb") as f:
                up = requests.post(
                    server["upload_url"],
                    files={"file": (image_path.name, f)},
                    timeout=120,
                )
            up.raise_for_status()
            data = up.json() if up.text.strip().startswith("{") else {}
            file_ref = data.get("file")
            if not file_ref:
                last_err = data.get("error_descr") or data.get("error") or up.text[:80]
                raise RuntimeError(last_err)
            saved = vk_call(token, "docs.save", file=file_ref, group_id=group_id)
            doc = saved.get("doc") or saved[0]
            return f"doc{doc['owner_id']}_{doc['id']}"
        except (requests.RequestException, RuntimeError, KeyError, IndexError, ValueError) as e:
            last_err = str(e)
        time.sleep(4)
    raise VkError("docs.upload", 0, f"не удалось загрузить {image_path.name} за {retries} попыток: {last_err}")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_posts() -> list[dict]:
    posts = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not meta or not meta.get("source"):
            continue
        image_paths, body_wo_images = extract_images(body)
        posts.append({
            "slug": path.stem,
            "meta": meta,
            "body": body_wo_images,
            "images": image_paths,
            "date": meta.get("date", ""),
        })
    posts.sort(key=lambda p: p["date"])
    return posts


def main() -> int:
    parser = argparse.ArgumentParser(description="Кросспостинг постов в VK-группу")
    parser.add_argument("--limit", type=int, default=3, help="сколько новых постов отправить (по умолчанию 3)")
    parser.add_argument("--all", action="store_true", help="игнорировать лимит")
    parser.add_argument("--slug", help="отправить конкретный пост (подстрока slug/файла)")
    parser.add_argument("--since", help="только посты с даты YYYY-MM-DD (включительно)")
    parser.add_argument("--dry-run", action="store_true", help="показать текст постов без отправки")
    parser.add_argument("--check", action="store_true", help="проверить токен и группу, ничего не отправляя")
    args = parser.parse_args()

    env = load_env()
    token = env.get("VK_COMMUNITY_TOKEN", "")
    group_id_raw = env.get("VK_GROUP_ID", "")
    site_url = env.get("SITE_URL", "https://kotreview.ru").rstrip("/")

    posts = collect_posts()
    state = load_state()

    if args.slug:
        candidates = [p for p in posts if args.slug.lower() in p["slug"].lower()]
        if not candidates:
            print(f"Пост со slug «{args.slug}» не найден.")
            return 1
        queue = candidates
    else:
        queue = [p for p in posts if p["meta"]["source"] not in state]
        if args.since:
            queue = [p for p in queue if p["date"] >= args.since]
        if not args.all:
            queue = queue[: max(args.limit, 0)]

    if not queue:
        print("Нет новых постов для отправки.")
        return 0

    if args.dry_run:
        for p in queue:
            msg = build_message(p["meta"], p["body"], p["slug"], site_url)
            print("=" * 60)
            print(f"[DRY] {p['slug']} ({p['date']}), фото: {len(p['images'])}")
            print("-" * 60)
            print(msg)
            print(f"Длина текста: {len(msg)} симв.")
        print("=" * 60)
        print(f"Итого к отправке: {len(queue)} (dry-run, ничего не отправлено)")
        return 0

    if not token or not group_id_raw:
        print("Нет настроек VK. Заполни scripts/.env:")
        print("  VK_GROUP_ID=<числовой id группы или короткое имя, например kot_review>")
        print("  VK_COMMUNITY_TOKEN=<ключ сообщества с правами «Стена» и «Документы»>")
        return 1

    # VK_GROUP_ID может быть числовым id или коротким именем (kot_review) — резолвим через API
    try:
        info = vk_call(token, "groups.getById", group_id=group_id_raw.lstrip("-"))
        group = info["groups"][0]
        group_id = abs(int(group["id"]))
        print(f"Группа: {group['name']} (id={group_id})")
    except (VkError, KeyError, IndexError, ValueError) as e:
        print(f"Не удалось проверить группу/токен: {e}")
        return 1

    if args.check:
        print("Токен работает, группа найдена. Можно отправлять: python scripts/post-to-vk.py --dry-run")
        return 0

    sent = 0
    failed = 0
    upload_available = True  # станет False, если ключ сообщества не может заливать фото (VK error 27)
    for i, p in enumerate(queue):
        post_url = f"{site_url}/posts/{p['slug']}/"
        try:
            attachments = []
            for img in p["images"]:
                if not upload_available:
                    break
                local = PUBLIC_DIR / img.lstrip("/")
                if not local.exists():
                    print(f"  ! Картинка не найдена, пропускаю: {local}")
                    continue
                try:
                    attachments.append(upload_photo(token, group_id, local))
                except VkError as e:
                    if e.code == 15 or e.code == 27:
                        upload_available = False
                        attachments = []
                        print(f"  ! Загрузка фото недоступна ({e}) —")
                        print("    посты пойдут текстом. Проверь раздел «Документы» в группе и право в ключе.")
                    else:
                        raise
            # Если фото не приложили — вкладываем ссылкой пост сайта: VK сделает карточку с og:image
            msg = build_message(p["meta"], p["body"], p["slug"], site_url, with_site_link=not attachments)
            final_attachments = ",".join(attachments) if attachments else post_url
            try:
                resp = vk_call(
                    token,
                    "wall.post",
                    owner_id=-group_id,
                    from_group=1,
                    message=msg,
                    attachments=final_attachments,
                )
            except VkError as e:
                if e.code == 100 and "link_photo_sizing_rule" in str(e) and final_attachments == post_url:
                    # VK не принял карточку ссылки (og-картинка не проходит по размерам) —
                    # публикуем без вложения, ссылка на сайт остаётся текстом
                    print("  ! VK не принял карточку ссылки — публикую ссылкой в тексте")
                    msg = build_message(p["meta"], p["body"], p["slug"], site_url, with_site_link=True)
                    resp = vk_call(
                        token,
                        "wall.post",
                        owner_id=-group_id,
                        from_group=1,
                        message=msg,
                        attachments=None,
                    )
                else:
                    raise
            post_id = resp.get("post_id")
            state[p["meta"]["source"]] = {"post_id": post_id, "posted_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_state(state)
            print(f"  ✓ {p['slug']} -> https://vk.com/wall-{group_id}_{post_id}")
            sent += 1
        except (VkError, requests.RequestException, OSError) as e:
            print(f"  ✗ {p['slug']}: {e}")
            failed += 1
            if sent == 0 and i == 0:
                print("Первая же отправка не удалась — останавливаюсь, проверь настройки/права токена.")
                return 1
        if i < len(queue) - 1:
            time.sleep(PAUSE_BETWEEN_POSTS)

    print(f"\nГотово: отправлено {sent}, ошибок {failed}.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
