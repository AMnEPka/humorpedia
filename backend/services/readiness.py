"""Готовность зависимостей без раскрытия адресов, путей и ошибок драйвера."""
import asyncio
from pathlib import Path
import tempfile


def _same_constraint(actual: dict, required: dict) -> bool:
    options = required["options"]
    if list(map(tuple, actual.get("key", []))) != list(map(tuple, required["keys"])):
        return False
    for flag in ("unique", "sparse"):
        if bool(actual.get(flag, False)) != bool(options.get(flag, False)):
            return False
    return all(actual.get(key) == options.get(key) for key in ("partialFilterExpression", "collation"))


async def _indexes_available(db, requirements) -> bool:
    catalogues = {}
    for required in requirements:
        collection = required["collection"]
        if collection not in catalogues:
            catalogues[collection] = await db[collection].index_information()
        if not any(_same_constraint(index, required) for index in catalogues[collection].values()):
            return False
    return bool(requirements)


def _storage_available(package_dir, public_dirs) -> bool:
    directory = Path(package_dir).resolve()
    if not directory.is_dir() or any(directory.is_relative_to(Path(public).resolve()) for public in public_dirs):
        return False
    # Уникальный временный файл проверяет read/write/delete, не меняя содержимое пакетов.
    with tempfile.TemporaryFile(dir=directory, prefix=".readiness-") as probe:
        probe.write(b"ready")
        probe.flush()
        probe.seek(0)
        return probe.read() == b"ready"


async def check_readiness(db, *, indexes_initialized, required_indexes, package_dir, public_dirs, timeout=1.0):
    async def bounded(check):
        try:
            return bool(await asyncio.wait_for(check, timeout=timeout))
        except Exception:
            return False

    mongo_ok = await bounded(db.command("ping"))
    indexes_ok = False
    if mongo_ok and indexes_initialized:
        indexes_ok = await bounded(_indexes_available(db, required_indexes))
    storage_ok = await bounded(asyncio.to_thread(_storage_available, package_dir, public_dirs))
    checks = {"mongodb": "ok" if mongo_ok else "error",
              "indexes": "ok" if indexes_ok else "error",
              "package_storage": "ok" if storage_ok else "error"}
    return {"status": "ready" if all(value == "ok" for value in checks.values()) else "not_ready",
            "checks": checks}
