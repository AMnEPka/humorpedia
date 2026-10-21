"""Ручное восстановление зависшего page-package или редакционного claim."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


def _collection(db, kind):
    if kind == "page-package":
        return db.page_package_imports
    if kind == "editorial":
        return db.editorial_proposals
    raise ValueError("Неизвестный тип claim")


def _token(document, kind):
    if kind == "page-package":
        return document.get("lease_token")
    return (document.get("decision_claim") or {}).get("token")


def _revision(document, kind):
    if kind != "editorial":
        return None
    value = document.get("revision", 0)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("У предложения некорректная revision; автоматическое восстановление невозможно")
    return value


def _summary(kind, document, applied=False):
    return {
        "kind": kind,
        "id": document["_id"],
        "status": document.get("status"),
        "token": _token(document, kind),
        "revision": _revision(document, kind),
        "applied": applied,
    }


async def recover_claim(
    db, kind, document_id, *, expected_token=None, actor="", reason="", apply=False, worker_stopped=False,
):
    """Показать claim или снять его условным обновлением после остановки worker."""
    collection = _collection(db, kind)
    document = await collection.find_one({"_id": document_id})
    if not document:
        raise ValueError("Запись workflow не найдена")
    if not apply:
        return _summary(kind, document)

    if not expected_token:
        raise ValueError("Для применения укажите точный --expected-token")
    if not worker_stopped:
        raise ValueError("Перед применением подтвердите остановку прежнего worker")
    actor = actor.strip() if isinstance(actor, str) else ""
    reason = reason.strip() if isinstance(reason, str) else ""
    if not actor:
        raise ValueError("Укажите непустое имя оператора")
    if not reason:
        raise ValueError("Укажите причину восстановления")

    current_token = _token(document, kind)
    if current_token != expected_token:
        raise ValueError("Claim уже изменился; повторите dry-run и проверьте владельца")

    now = datetime.now(timezone.utc).isoformat()
    audit = {"previous_token": current_token, "actor": actor, "reason": reason, "at": now}
    if kind == "page-package":
        if document.get("status") != "applying":
            raise ValueError("ZIP claim можно восстановить только в состоянии applying")
        query = {"_id": document_id, "status": "applying", "lease_token": expected_token}
        update = {
            "$set": {"status": "error", "error": f"Импорт прерван оператором: {reason}"},
            "$unset": {"lease_token": "", "lease_until": ""},
            "$push": {"claim_recovery_audit": audit},
        }
        resulting_status = "error"
        resulting_revision = None
    else:
        revision = _revision(document, kind)
        claim = document.get("decision_claim") or {}
        if not claim or not current_token:
            raise ValueError("У предложения нет активного decision claim")
        if "revision" in document and document["revision"] is None:
            raise ValueError("У proposal revision равна null; безопасный CAS невозможен")
        revision_filter = {"revision": document["revision"]} if "revision" in document else {
            "revision": {"$exists": False},
        }
        query = {"_id": document_id, "decision_claim.token": expected_token, **revision_filter}
        update = {
            "$unset": {"decision_claim": ""},
            "$inc": {"revision": 1},
            "$push": {"claim_recovery_audit": audit},
        }
        resulting_status = document.get("status")
        resulting_revision = revision + 1

    result = await collection.update_one(query, update)
    if not result.matched_count:
        raise ValueError("Claim или revision изменились до восстановления; запись не снята")
    return {
        "kind": kind,
        "id": document_id,
        "status": resulting_status,
        "token": None,
        "revision": resulting_revision,
        "applied": True,
    }


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-name", required=True, help="Явное имя базы данных")
    parser.add_argument("--kind", required=True, choices=("page-package", "editorial"))
    parser.add_argument("--id", required=True, dest="document_id", help="ID записи workflow")
    parser.add_argument("--apply", action="store_true", help="Применить восстановление; по умолчанию только просмотр")
    parser.add_argument("--expected-token", help="Точный token из dry-run")
    parser.add_argument("--confirm-worker-stopped", action="store_true", help="Подтвердить остановку прежнего worker")
    parser.add_argument("--actor", default="", help="Оператор, выполняющий восстановление")
    parser.add_argument("--reason", default="", help="Причина ручного снятия claim")
    return parser


async def _run_cli(args):
    from utils.database import close_db, get_db

    previous_db_name = os.environ.get("DB_NAME")
    os.environ["DB_NAME"] = args.db_name
    try:
        db = await get_db()
        if getattr(db, "name", None) != args.db_name:
            raise ValueError("Подключённая база не совпадает с --db-name")
        return await recover_claim(
            db, args.kind, args.document_id, expected_token=args.expected_token,
            actor=args.actor, reason=args.reason, apply=args.apply,
            worker_stopped=args.confirm_worker_stopped,
        )
    finally:
        await close_db()
        if previous_db_name is None:
            os.environ.pop("DB_NAME", None)
        else:
            os.environ["DB_NAME"] = previous_db_name


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not (os.environ.get("MONGO_URL") or os.environ.get("MONGO_HOST")):
        parser.error("Задайте подключение через MONGO_URL или MONGO_HOST в окружении")
    if args.apply and not (args.expected_token and args.confirm_worker_stopped and args.actor.strip() and args.reason.strip()):
        parser.error("Для --apply нужны --expected-token, --confirm-worker-stopped, --actor и --reason")
    try:
        result = asyncio.run(_run_cli(args))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
