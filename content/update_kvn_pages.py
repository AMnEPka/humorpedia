"""
Update KVN pages in MongoDB via the backend API.
Preserves system modules (poster, facts, rating, tags, social_links),
replaces text_block modules with new rich content.

Usage:
    python content/update_kvn_pages.py                  # Dry-run
    python content/update_kvn_pages.py --apply           # Apply changes
    python content/update_kvn_pages.py --apply --only kvn   # Only root page
    python content/update_kvn_pages.py --apply --only league  # Only league overview
    python content/update_kvn_pages.py --apply --only leagues  # Only individual leagues
"""

import argparse
import json
import os
import sys
import uuid
import requests
from pathlib import Path

try:
    import markdown
except ImportError:
    os.system(f"{sys.executable} -m pip install markdown")
    import markdown

API_BASE = "http://127.0.0.1:8001/api"
SYSTEM_MODULE_TYPES = {"poster_photo", "facts_table", "rating_widget", "tags_cloud", "social_links"}


def md_to_html(md_text):
    return markdown.markdown(md_text, extensions=["tables", "toc", "attr_list"])


def parse_frontmatter(content):
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_lines = parts[1].strip().split("\n")
    meta = {}
    for line in fm_lines:
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip().strip('"')] = val.strip().strip('"')
    return meta, parts[2].strip()


def md_file_to_text_modules(md_path, start_order=5):
    """Convert markdown file to text_block modules, split by H2."""
    content = md_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    import re
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    modules = []
    order = start_order

    for section in sections:
        section = section.strip()
        if not section:
            continue

        title_match = re.match(r"^## (.+?)(?:\s*\{#[\w-]+\})?\s*$", section, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            content_md = section[title_match.end():].strip()
        else:
            title = ""
            content_md = section

        if not content_md:
            continue

        html = md_to_html(content_md)

        modules.append({
            "id": str(uuid.uuid4()),
            "type": "text_block",
            "order": order,
            "title": title,
            "visible": True,
            "data": {"title": title, "content": html},
        })
        order += 1

    return modules, meta


def get_page(full_path):
    r = requests.get(f"{API_BASE}/content/kvn/by-path/{full_path}", timeout=10)
    if r.status_code == 200:
        return r.json()
    return None


def update_page(page_id, update_data):
    r = requests.put(f"{API_BASE}/content/kvn/{page_id}", json=update_data, timeout=30)
    r.raise_for_status()
    return r.json()


def create_page(create_data):
    r = requests.post(f"{API_BASE}/content/kvn", json=create_data, timeout=30)
    r.raise_for_status()
    return r.json()


def update_existing_page(full_path, md_path, dry_run=True):
    """Update an existing page: keep system modules, replace text_blocks."""
    page = get_page(full_path)
    if not page:
        print(f"  ERROR: Page not found at {full_path}")
        return None

    page_id = page.get("id", page.get("_id"))
    old_modules = page.get("modules", [])
    system_modules = [m for m in old_modules if m.get("type") in SYSTEM_MODULE_TYPES]

    max_sys_order = max((m.get("order", 0) for m in system_modules), default=-1)
    new_text_modules, meta = md_file_to_text_modules(md_path, start_order=max_sys_order + 1)

    final_modules = system_modules + new_text_modules

    update_data = {"modules": final_modules}

    desc = meta.get("meta_description", "")
    if desc:
        update_data["description"] = desc

    print(f"\n  UPDATE: {full_path}")
    print(f"    Page ID: {page_id}")
    print(f"    Keeping {len(system_modules)} system modules")
    print(f"    Adding {len(new_text_modules)} text_block modules")
    print(f"    Total: {len(final_modules)} modules")
    for m in new_text_modules:
        t = m.get("title", "(no title)")
        clen = len(m.get("data", {}).get("content", ""))
        print(f"      - \"{t}\" ({clen} chars)")

    if dry_run:
        print("    [DRY RUN] Not applying.")
        return None

    result = update_page(page_id, update_data)
    print(f"    DONE. Updated successfully.")
    return result


def create_league_page(slug, md_path, parent_id, dry_run=True):
    """Create a new league page or update if it exists."""
    full_path = f"kvn/league/{slug}"
    existing = get_page(full_path)

    text_modules, meta = md_file_to_text_modules(md_path, start_order=0)
    desc = meta.get("meta_description", "")
    title = meta.get("title", slug)

    if existing:
        page_id = existing.get("id", existing.get("_id"))
        old_modules = existing.get("modules", [])
        system_modules = [m for m in old_modules if m.get("type") in SYSTEM_MODULE_TYPES]

        for i, m in enumerate(text_modules):
            m["order"] = len(system_modules) + i

        final_modules = system_modules + text_modules

        print(f"\n  UPDATE: {full_path}")
        print(f"    Keeping {len(system_modules)} system modules, adding {len(text_modules)} text modules")

        if dry_run:
            print("    [DRY RUN]")
            return None

        update_data = {"modules": final_modules}
        if desc:
            update_data["description"] = desc
        result = update_page(page_id, update_data)
        print(f"    DONE.")
        return result
    else:
        print(f"\n  CREATE: {full_path}")
        print(f"    Title: {title}")
        print(f"    Parent ID: {parent_id}")
        print(f"    Modules: {len(text_modules)}")

        if dry_run:
            print("    [DRY RUN]")
            return None

        create_data = {
            "title": title,
            "slug": slug,
            "name": title,
            "description": desc,
            "parent_id": parent_id,
            "modules": text_modules,
            "tags": ["КВН"],
            "status": "published",
        }
        result = create_page(create_data)
        new_id = result.get("id", result.get("_id", "?"))
        print(f"    DONE. Created with id={new_id}")
        return result


def main():
    parser = argparse.ArgumentParser(description="Update KVN pages in database")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", type=str, choices=["kvn", "league", "leagues", "all"], default="all")
    args = parser.parse_args()

    dry_run = not args.apply
    content_dir = Path(__file__).parent

    if dry_run:
        print("\n=== DRY RUN MODE ===\n")
    else:
        print("\n=== APPLYING CHANGES ===\n")

    # 1. Update root KVN page
    if args.only in ("all", "kvn"):
        print("=" * 60)
        print("1. ROOT KVN PAGE (kvn)")
        print("=" * 60)
        update_existing_page("kvn", content_dir / "kvn-main.md", dry_run=dry_run)

    # 2. Update league overview page
    if args.only in ("all", "league"):
        print("\n" + "=" * 60)
        print("2. LEAGUE OVERVIEW PAGE (kvn/league)")
        print("=" * 60)
        update_existing_page("kvn/league", content_dir / "kvn-central-leagues.md", dry_run=dry_run)

    # 3. Create/update individual league pages
    if args.only in ("all", "leagues"):
        print("\n" + "=" * 60)
        print("3. INDIVIDUAL LEAGUE PAGES (kvn/league/*)")
        print("=" * 60)

        league_page = get_page("kvn/league")
        if not league_page:
            print("  ERROR: League parent page not found!")
            return
        league_parent_id = league_page.get("id", league_page.get("_id"))
        print(f"  League parent ID: {league_parent_id}")

        leagues_dir = content_dir / "leagues"
        for md_file in sorted(leagues_dir.glob("*.md")):
            slug = md_file.stem
            create_league_page(slug, md_file, league_parent_id, dry_run=dry_run)

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
