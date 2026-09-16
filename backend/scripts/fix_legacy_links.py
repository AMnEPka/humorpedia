#!/usr/bin/env python3
"""
Перевод ссылок старого сайта в уже перенесённом контенте на адреса нового сайта.

В текстах команд, страниц КВН и шоу ссылки остались в формате MODX: относительные (`people/x.html`,
`kvn/team/dals.html`), `[[~id]]`, абсолютные `https://humorpedia.ru/...`, картинки `images/...`.
Скрипт переписывает только значения href/src (остальной HTML не трогает) — так же, как импорт людей:
ресурс MODX → адрес перенесённой страницы (old_id) или адрес по шаблону; иначе паттерны старых URL.
Ссылки на страницы, которых ещё нет, на сайте показываются текстом (services/link_resolver.py).

Использование (внутри контейнера backend):
    python scripts/fix_legacy_links.py            # пробный прогон: сколько документов и ссылок изменится
    python scripts/fix_legacy_links.py --apply    # записать
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.competitions import sync_kvn_pages  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_content import LinkMapper, rewrite_links  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_shows import show_url_builder  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
COLLECTIONS = ("teams", "kvn", "shows", "people")
SKIP_FIELDS = {"_id", "id", "slug", "full_path", "old_urls", "logo", "photo", "image", "poster", "cover_image"}


def rewrite_value(value, mapper, counter):
    if isinstance(value, str):
        if "href" not in value and "src" not in value:
            return value
        new = rewrite_links(value, mapper)
        if new != value:
            counter[0] += 1
        return new
    if isinstance(value, dict):
        return {k: rewrite_value(v, mapper, counter) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite_value(v, mapper, counter) for v in value]
    return value


async def main(args) -> None:
    db = await get_db()
    try:
        print(f"Читаю дамп {args.dump} …")
        site = load_modx_site(args.dump, keep_content_for=lambda r: False)
        mapper = LinkMapper(site, _try_pattern_redirect, await load_old_id_urls(db), [show_url_builder(site)])
        changed_kvn = []
        for coll in COLLECTIONS:
            docs = changed_strings = 0
            async for doc in db[coll].find({}):
                counter = [0]
                updates = {}
                for field, value in doc.items():
                    if field in SKIP_FIELDS:
                        continue
                    new = rewrite_value(value, mapper, counter)
                    if new != value:
                        updates[field] = new
                if not updates:
                    continue
                docs += 1
                changed_strings += counter[0]
                if args.apply:
                    await db[coll].update_one({"_id": doc["_id"]}, {"$set": updates})
                    if coll == "kvn" and "season_data" in updates:
                        changed_kvn.append(doc["_id"])
            print(f"{coll}: документов {docs}, текстовых полей {changed_strings}")
        if args.apply:
            if changed_kvn:
                stats = await sync_kvn_pages(db, {"_id": {"$in": changed_kvn}})
                print("Синхронизация сезонов:", {k: v for k, v in stats.items() if k != "errors"}, stats["errors"][:3])
            await cache_service.invalidate_everywhere(db)
            print("Готово.")
        else:
            print("Пробный прогон. Для записи: --apply")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args()))
