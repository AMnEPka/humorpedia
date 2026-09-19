"""Create or remove ten clearly labelled local demo news items.

Dry-run by default. Use --apply to upsert demo items and --cleanup to remove them.
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.database import close_db, get_db  # noqa: E402


DEMO_MARKER = "related_news_demo"
DEMO_COUNT = 10
DEMO_SEED = 20260919


async def select_people(db) -> list[dict]:
    people = await db.people.find(
        {"status": {"$ne": "archived"}},
        {"_id": 1, "title": 1, "full_name": 1, "slug": 1},
    ).sort("_id", 1).to_list(None)
    if len(people) < DEMO_COUNT:
        raise RuntimeError(f"Для демоданных нужно минимум {DEMO_COUNT} людей")
    return random.Random(DEMO_SEED).sample(people, DEMO_COUNT)


def demo_document(person: dict, index: int, now: datetime) -> dict:
    person_name = person.get("full_name") or person.get("title") or person["_id"]
    published_at = now - timedelta(days=index * 3)
    image = f"/media/imported/images/pattern/{index % 4 + 1}.jpg"
    return {
        "_id": f"demo-related-news-{index + 1:02d}",
        "content_type": "news",
        "title": f"Демонстрационная новость: {person_name}",
        "slug": f"demo-related-news-{index + 1:02d}",
        "excerpt": "Тестовая запись для проверки компактного блока свежих новостей. Не является редакционной публикацией.",
        "cover_image": {"url": image, "thumbnail": image, "alt": "Демонстрационная обложка", "caption": ""},
        "content": "<p>Локальная демонстрационная запись для проверки нового блока связанных новостей.</p>",
        "important": False,
        "modules": [{
            "id": f"demo-related-news-module-{index + 1:02d}",
            "type": "text_block",
            "order": 0,
            "title": "",
            "visible": True,
            "data": {"title": "", "content": "<p>Локальная демонстрационная запись для проверки нового блока связанных новостей.</p>"},
        }],
        "tags": ["Демоданные"],
        "seo": {"meta_title": "", "meta_description": "", "keywords": []},
        "status": "published",
        "related_person_ids": [person["_id"]],
        "related_team_ids": [],
        "related_show_ids": [],
        "related_article_ids": [],
        "published_at": published_at.isoformat(),
        "created_at": published_at.isoformat(),
        "updated_at": now.isoformat(),
        "demo_marker": DEMO_MARKER,
    }


async def main(*, apply: bool, cleanup: bool) -> None:
    db = await get_db()
    try:
        if cleanup:
            count = await db.news.count_documents({"demo_marker": DEMO_MARKER})
            if apply:
                result = await db.news.delete_many({"demo_marker": DEMO_MARKER})
                count = result.deleted_count
            print(json.dumps({"mode": "cleanup", "documents": count, "applied": apply}, ensure_ascii=False))
            return

        people = await select_people(db)
        now = datetime.now(timezone.utc)
        documents = [demo_document(person, index, now) for index, person in enumerate(people)]
        if apply:
            for document in documents:
                await db.news.replace_one({"_id": document["_id"]}, document, upsert=True)
        print(json.dumps({
            "mode": "seed",
            "documents": len(documents),
            "people": [{"id": person["_id"], "title": person.get("title")} for person in people],
            "applied": apply,
        }, ensure_ascii=False, indent=2))
        if not apply:
            print("Пробный прогон: ничего не записано (добавьте --apply).")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="записать изменения")
    parser.add_argument("--cleanup", action="store_true", help="удалить только созданные этим скриптом демоданные")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, cleanup=args.cleanup))
