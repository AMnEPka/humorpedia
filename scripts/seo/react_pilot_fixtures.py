"""Shared synthetic React pilot records; never imported by production server."""
import json
from pathlib import Path
from routes.auth import hash_password
ROOT = Path(__file__).resolve().parents[2]
async def seed_react_records(db):
    fixtures = json.loads((ROOT / "backend/tests/fixtures/html_react_pilot.json").read_text(encoding="utf-8-sig"))
    for kind, records in fixtures.items():
        await db[kind].insert_many(records)
    await db.people.update_one({"_id": "person-alpha"}, {"$push": {"modules": {"type": "poll", "order": 50, "data": {"poll_id": "poll-demo"}}}})
    await db.polls.insert_one({"_id": "poll-demo", "question": "Как вам пилот?", "status": "published",
        "show_results_before_vote": False, "options": [
            {"id": "yes", "text": "Подходит", "historical_votes": 0},
            {"id": "no", "text": "Нужно доработать", "historical_votes": 0}]})
    await db.users.insert_one({"_id": "pilot-user", "username": "pilot-user", "email": "pilot@example.invalid",
                              "password_hash": hash_password("Pilot-only-2026"), "role": "user", "permissions": ["vote"], "profile": {}})
    await db.teams.insert_one({"_id": "team-demo", "name": "Команда пилота", "title": "Команда пилота", "slug": "pilot-team", "status": "published", "show_id": None})
    await db.memberships.insert_one({"_id": "member-demo", "person_id": "person-alpha", "team_id": "team-demo",
                                     "roles": ["Участник"], "year_from": 2020, "year_to": 2021})
    await db.shows.insert_one({"_id": "show-demo", "title": "Шоу пилота", "name": "Шоу пилота", "slug": "show-demo",
                               "full_path": "show-demo", "status": "published"})
    await db.show_appearances.insert_one({"_id": "appearance-demo", "person_id": "person-alpha", "show_id": "show-demo",
                                          "source_page_id": "show-demo", "achievement": "participant", "kind": "appearance"})
