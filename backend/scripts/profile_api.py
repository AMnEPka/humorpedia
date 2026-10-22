"""Read-only in-process профилировщик выбранных GET API-маршрутов."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import statistics
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

import httpx
from pymongo.monitoring import CommandListener, register


DB_NAME_PATTERN = re.compile(r"^humorpedia_perf_[0-9a-fA-F]{32}$")
READ_COMMANDS = {"find", "aggregate", "count", "distinct"}
WIRE_READ_COMMANDS = READ_COMMANDS | {"getMore"}
VOLATILE_COMMAND_FIELDS = {
    "$db", "lsid", "$clusterTime", "operationTime", "$readPreference", "comment",
    "maxTimeMS", "apiVersion", "txnNumber", "autocommit",
}
ROUTE_PATTERNS = (
    ("search", re.compile(r"^/api/content/search$")),
    ("people", re.compile(r"^/api/content/people$")),
    ("person-card", re.compile(r"^/api/content/people/[^/]+$")),
    ("teams", re.compile(r"^/api/content/teams$")),
    ("team-card", re.compile(r"^/api/content/teams/[^/]+$")),
    ("kvn-by-path", re.compile(r"^/api/content/kvn/by-path/.+$")),
    ("competition-season", re.compile(r"^/api/competitions/seasons/(?:by-page/)?[^/]+$")),
    ("recommendations", re.compile(r"^/api/recommendations/?$")),
)


def validate_db_name(value: str) -> str:
    if not isinstance(value, str) or not DB_NAME_PATTERN.fullmatch(value):
        raise ValueError("--db-name должен быть humorpedia_perf_<32 hex символа>")
    return value


def _validate_read_roles(roles, db_name: str) -> None:
    expected = [{"role": "read", "db": db_name}]
    normalized = sorted(
        ({"role": item.get("role"), "db": item.get("db")} for item in roles or []),
        key=lambda item: (str(item["db"]), str(item["role"])),
    )
    if normalized != expected:
        raise ValueError("MongoDB-пользователь должен иметь ровно роль read для указанной базы")


def validate_plan(plan) -> list[dict[str, str]]:
    if not isinstance(plan, list) or not plan:
        raise ValueError("План должен быть непустым JSON-массивом")
    normalized = []
    names = set()
    for item in plan:
        if not isinstance(item, dict) or set(item) != {"name", "path"}:
            raise ValueError("Каждый пункт плана должен содержать только name и path")
        name, path = item["name"], item["path"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) or name in names:
            raise ValueError("Имена пунктов плана должны быть уникальными безопасными метками")
        if not isinstance(path, str):
            raise ValueError(f"Некорректный путь в пункте {name}")
        parsed = urlsplit(path)
        decoded_path = unquote(parsed.path)
        if parsed.scheme or parsed.netloc or parsed.fragment or not decoded_path.startswith("/api/"):
            raise ValueError(f"Разрешены только относительные пути API: {name}")
        if any(part in {".", ".."} for part in decoded_path.split("/")):
            raise ValueError(f"Путь вне разрешённого API-маршрута: {name}")
        if not any(pattern.fullmatch(decoded_path) for _route_name, pattern in ROUTE_PATTERNS):
            raise ValueError(f"Маршрут не входит в список разрешённых GET-путей: {name}")
        names.add(name)
        normalized.append({"name": name, "path": path})
    return normalized


def _p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _plan_percentiles(values):
    if not values:
        return {"min": None, "p50": None, "p95": None, "max": None, "mean": None}
    ordered = sorted(values)
    p50 = ordered[max(0, math.ceil(0.50 * len(ordered)) - 1)]
    return {
        "min": ordered[0], "p50": p50, "p95": _p95(ordered),
        "max": ordered[-1], "mean": statistics.fmean(ordered),
    }


def _explainable_command(command):
    if not isinstance(command, dict):
        return None
    kinds = [key for key in READ_COMMANDS if key in command]
    if len(kinds) != 1:
        return None

    return {key: deepcopy(value) for key, value in command.items() if key not in VOLATILE_COMMAND_FIELDS}


def _command_hash(command) -> str:
    try:
        from bson import json_util
        serialized = json_util.dumps(command, sort_keys=True, separators=(",", ":"))
    except ImportError:
        serialized = json.dumps(command, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _content_hash(path: str, payload) -> str:
    if isinstance(payload, bytes):
        payload = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        payload = json.loads(payload)
    content = deepcopy(payload)
    if (urlsplit(path).path.startswith("/api/content/kvn/by-path/")
            and isinstance(content, dict)):
        content.pop("team_data_version", None)
    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _content_hash_normalization(path: str) -> dict:
    excluded = []
    if urlsplit(path).path.startswith("/api/content/kvn/by-path/"):
        excluded.append("/team_data_version")
    return {"excluded_json_pointers": excluded}


@contextmanager
def _rate_limit_override(limiter, disabled: bool):
    original_enabled = limiter.enabled
    if disabled:
        limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = original_enabled


def _explain_summary(explain: dict) -> dict:
    stats = {}
    planner = {}
    statistics_scope = "query"
    for stage in explain.get("stages") or []:
        cursor = stage.get("$cursor") if isinstance(stage, dict) else None
        if isinstance(cursor, dict) and (cursor.get("executionStats") or cursor.get("queryPlanner")):
            stats = cursor.get("executionStats") or {}
            planner = cursor.get("queryPlanner") or {}
            statistics_scope = "aggregate_cursor"
            break
    if statistics_scope == "query":
        stats = explain.get("executionStats") or {}
        planner = explain.get("queryPlanner") or {}
    plan = planner.get("winningPlan") or {}
    index_names = set()

    def walk_plan(value):
        if isinstance(value, dict):
            if value.get("indexName"):
                index_names.add(str(value["indexName"]))
            for child in value.values():
                walk_plan(child)
        elif isinstance(value, list):
            for child in value:
                walk_plan(child)

    walk_plan(plan)
    return {
        "n_returned": stats.get("nReturned"),
        "docs_examined": stats.get("totalDocsExamined"),
        "keys_examined": stats.get("totalKeysExamined"),
        "execution_time_ms": stats.get("executionTimeMillis"),
        "index_names": sorted(index_names),
        "statistics_scope": statistics_scope,
    }


def _safe_query_shape(command: dict) -> dict:
    kind = next((key for key in READ_COMMANDS if key in command), "unknown")
    collection = command.get(kind)
    fields = set()
    operators = set()

    def inspect(value, prefix=""):
        if isinstance(value, dict):
            for key, nested in value.items():
                if isinstance(key, str) and key.startswith("$"):
                    operators.add(key)
                    inspect(nested, prefix)
                else:
                    path = f"{prefix}.{key}" if prefix else str(key)
                    fields.add(path)
                    inspect(nested, path)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                inspect(nested, prefix)

    for field in ("filter", "query", "pipeline"):
        if field in command:
            inspect(command[field])
    return {
        "command": kind,
        "collection": collection if isinstance(collection, str) else None,
        "fields": sorted(fields),
        "operators": sorted(operators),
        "options": sorted(
            key for key in command
            if key not in {kind, *VOLATILE_COMMAND_FIELDS}
        ),
    }


def _reply_documents(reply: dict, command_name: str) -> int:
    cursor = reply.get("cursor")
    if isinstance(cursor, dict):
        return sum(len(cursor.get(batch) or []) for batch in ("firstBatch", "nextBatch"))
    if command_name == "count":
        return int(reply.get("n") or 0)
    if command_name == "distinct":
        return len(reply.get("values") or [])
    return 0


class _ReadCommandListener(CommandListener):
    """Потокобезопасно собирает только успешные команды чтения в памяти."""

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._active = True
        self._pending = {}
        self._events = []

    def started(self, event):
        if event.command_name not in WIRE_READ_COMMANDS:
            return
        with self._lock:
            if self._active:
                self._pending[event.request_id] = (event.command_name, deepcopy(event.command))

    def succeeded(self, event):
        with self._lock:
            pending = self._pending.pop(event.request_id, None)
            if pending is None or not self._active:
                return
            name, command = pending
            self._events.append({
                "name": name, "command": command,
                "duration_ms": event.duration_micros / 1000,
                "docs_returned": _reply_documents(event.reply, name),
            })

    def failed(self, event):
        with self._lock:
            self._pending.pop(event.request_id, None)

    def reset(self):
        with self._lock:
            self._pending.clear()
            self._events.clear()

    def snapshot(self):
        with self._lock:
            return deepcopy(self._events)

    def pause(self):
        with self._lock:
            self._active = False
            self._pending.clear()


def _make_listener(timing_only):
    if timing_only:
        return None
    listener = _ReadCommandListener()
    register(listener)
    return listener


def _command_metrics(events):
    logical = Counter(event["name"] for event in events if event["name"] in READ_COMMANDS)
    wire = Counter(event["name"] for event in events if event["name"] in WIRE_READ_COMMANDS)
    explainable = {}
    for event in events:
        command = _explainable_command(event["command"])
        if command is None:
            continue
        digest = _command_hash(command)
        explainable.setdefault(digest, {
            "hash": digest, "command": command,
            "name": next(k for k in READ_COMMANDS if k in command),
            "query_shape": _safe_query_shape(command),
        })
    return {
        "logical_commands": dict(sorted(logical.items())),
        "wire_commands": dict(sorted(wire.items())),
        "mongo_docs_returned": sum(event["docs_returned"] for event in events),
        "mongo_duration_ms": sum(event["duration_ms"] for event in events),
        "query_hashes": sorted(explainable),
        "explainable_commands": list(explainable.values()),
    }


def _memory_bytes() -> dict:
    if not sys.platform.startswith("linux"):
        return {"current_bytes": None, "peak_bytes": None}
    current = None
    try:
        pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
        current = pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        pass
    peak = None
    try:
        import resource
        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except (ImportError, AttributeError, OSError, ValueError):
        pass
    return {"current_bytes": current, "peak_bytes": peak}


def _sample_summary(samples):
    instrumented = all(item["logical_commands"] is not None for item in samples)
    return {
        "latency_ms": _plan_percentiles([item["duration_ms"] for item in samples]),
        "cpu_ms": _plan_percentiles([item["cpu_ms"] for item in samples]),
        "logical_command_count": _plan_percentiles([sum(item["logical_commands"].values()) for item in samples]) if instrumented else None,
        "wire_command_count": _plan_percentiles([sum(item["wire_commands"].values()) for item in samples]) if instrumented else None,
        "mongo_duration_ms": _plan_percentiles([item["mongo_duration_ms"] for item in samples]) if instrumented else None,
        "mongo_docs_returned": _plan_percentiles([item["mongo_docs_returned"] for item in samples]) if instrumented else None,
        "payload_bytes": _plan_percentiles([item["payload_bytes"] for item in samples]),
        "response_hashes": sorted({item["response_sha256"] for item in samples}),
        "response_hash_stable": len({item["response_sha256"] for item in samples}) <= 1,
        "content_hashes": sorted({item["content_sha256"] for item in samples}),
        "content_hash_stable": len({item["content_sha256"] for item in samples}) <= 1,
        "memory_current_bytes": [item["memory"]["current_bytes"] for item in samples],
        "memory_peak_bytes": [item["memory"]["peak_bytes"] for item in samples],
    }


async def _profile_request(client, listener, item, *, clear_cache, cache_service, views_counter):
    if clear_cache:
        cache_service.flush_all()
    if listener is not None:
        listener.reset()
    views_counter._buffer.clear()
    started_at_unix_ns = time.time_ns()
    cpu_start = time.process_time()
    started = time.perf_counter()
    try:
        response = await client.get(item["path"])
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        cpu_ms = (time.process_time() - cpu_start) * 1000
        views_counter._buffer.clear()
    if response.status_code != 200:
        raise RuntimeError(f"GET {item['name']} вернул HTTP {response.status_code}")
    metrics = _command_metrics(listener.snapshot()) if listener is not None else {
        "logical_commands": None, "wire_commands": None,
        "mongo_docs_returned": None, "mongo_duration_ms": None,
        "query_hashes": [], "explainable_commands": [],
    }
    return {
        "started_at_unix_ns": started_at_unix_ns,
        "duration_ms": elapsed,
        "cpu_ms": cpu_ms,
        "logical_commands": metrics["logical_commands"],
        "wire_commands": metrics["wire_commands"],
        "mongo_docs_returned": metrics["mongo_docs_returned"],
        "mongo_duration_ms": metrics["mongo_duration_ms"],
        "query_hashes": metrics["query_hashes"],
        "payload_bytes": len(response.content),
        "response_sha256": hashlib.sha256(response.content).hexdigest(),
        "content_sha256": _content_hash(item["path"], response.content),
        "memory": _memory_bytes(),
        "explainable_commands": metrics["explainable_commands"],
    }


async def _run_profile(db_name, plan, samples, label, output_path, *, without_rate_limit=False, timing_only=False):
    listener = _make_listener(timing_only)
    httpx_logger = logging.getLogger("httpx")
    original_httpx_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)
    original_db_name = os.environ.get("DB_NAME")
    os.environ["DB_NAME"] = db_name
    database_module = None
    rate_limit_context = None
    try:
        # Импорт app не запускает lifespan; ASGITransport его также не включает.
        import importlib
        app_module = importlib.import_module("server")
        rate_limit_context = _rate_limit_override(app_module.limiter, without_rate_limit)
        rate_limit_context.__enter__()
        database_module = importlib.import_module("utils.database")
        db = await database_module.get_db()
        from services.cache import cache_service
        from services.views_counter import views_counter

        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            reports = []
            explain_commands = {}
            for item in plan:
                cold, warm = [], []
                for _ in range(samples):
                    sample = await _profile_request(
                        client, listener, item, clear_cache=True,
                        cache_service=cache_service, views_counter=views_counter,
                    )
                    cold.append(sample)
                    for command in sample.pop("explainable_commands"):
                        saved = explain_commands.setdefault(command["hash"], {**command, "scenarios": set()})
                        saved["scenarios"].add(item["name"])

                # Один прогрев не входит в измерение warm.
                warmup = await _profile_request(
                    client, listener, item, clear_cache=False,
                    cache_service=cache_service, views_counter=views_counter,
                )
                for command in warmup.pop("explainable_commands"):
                    saved = explain_commands.setdefault(command["hash"], {**command, "scenarios": set()})
                    saved["scenarios"].add(item["name"])
                for _ in range(samples):
                    sample = await _profile_request(
                        client, listener, item, clear_cache=False,
                        cache_service=cache_service, views_counter=views_counter,
                    )
                    warm.append(sample)
                    for command in sample.pop("explainable_commands"):
                        saved = explain_commands.setdefault(command["hash"], {**command, "scenarios": set()})
                        saved["scenarios"].add(item["name"])
                reports.append({
                    "name": item["name"], "path": item["path"],
                    "content_hash_normalization": _content_hash_normalization(item["path"]),
                    "cold": {"summary": _sample_summary(cold), "samples": cold},
                    "warm": {"summary": _sample_summary(warm), "samples": warm},
                    "cold_warm_response_hashes_equal": set(_sample_summary(cold)["response_hashes"])
                    == set(_sample_summary(warm)["response_hashes"]),
                    "cold_warm_content_hashes_equal": set(_sample_summary(cold)["content_hashes"])
                    == set(_sample_summary(warm)["content_hashes"]),
                })

        if listener is not None:
            listener.pause()
        explain_results = []
        for command in explain_commands.values():
            digest, raw, kind = command["hash"], command["command"], command["name"]
            collection_name = raw.get(kind)
            try:
                explained = await db.command({"explain": raw, "verbosity": "executionStats"})
                summary = _explain_summary(explained)
                if summary["statistics_scope"] == "aggregate_cursor":
                    execution_scope = (
                        "aggregate_cursor: статистика относится к входному cursor, "
                        "а не к итоговому числу документов после pipeline."
                    )
                else:
                    execution_scope = "query: полный запрос MongoDB; лимит длины cursor клиентом не применяется."
                explain_results.append({
                    "hash": digest, "command": kind, "collection": collection_name,
                    "scenarios": sorted(command["scenarios"]),
                    "query_shape": command["query_shape"],
                    "execution_scope": execution_scope,
                    **summary,
                })
            except Exception as exc:
                explain_results.append({
                    "hash": digest, "command": kind, "collection": collection_name,
                    "scenarios": sorted(command["scenarios"]),
                    "query_shape": command["query_shape"],
                    "execution_scope": (
                        "aggregate_cursor: для staged aggregate это статистика входного cursor, "
                        "не итогового pipeline."
                        if kind == "aggregate" else
                        "query: полный запрос MongoDB; лимит длины cursor клиентом не применяется."
                    ),
                    "error_type": type(exc).__name__,
                })

        result = {
            "schema_version": 2,
            "measurement_mode": "timing_only" if timing_only else "instrumented",
            "query_metrics_collected": not timing_only,
            "httpx_request_logging": False,
            "label": label,
            "database": db_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "samples_per_mode": samples,
            "rate_limit_disabled": bool(without_rate_limit),
            "cpu_scope": "Дельта process_time процесса профилировщика вокруг HTTP-запроса; не CPU MongoDB или хоста.",
            "memory_scope": {
                "current": "RSS всего процесса после получения ответа и вычисления его хешей.",
                "peak": "ru_maxrss — максимум всего процесса с момента запуска, включая предыдущие сценарии и прогрев; не per-request peak.",
            },
            "explain_count": len(explain_results),
            "explain": explain_results,
            "scenarios": reports,
        }
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if listener is not None:
            listener.pause()
        httpx_logger.setLevel(original_httpx_level)
        try:
            if database_module is not None:
                await database_module.close_db()
        finally:
            try:
                if rate_limit_context is not None:
                    rate_limit_context.__exit__(*sys.exc_info())
            finally:
                if original_db_name is None:
                    os.environ.pop("DB_NAME", None)
                else:
                    os.environ["DB_NAME"] = original_db_name


def _check_read_only_mongo(db_name: str, mongo_url: str) -> None:
    from pymongo import MongoClient

    client = None
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        response = client[db_name].command("connectionStatus")
        roles = ((response.get("authInfo") or {}).get("authenticatedUserRoles") or [])
        _validate_read_roles(roles, db_name)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Не удалось проверить read-only роль MongoDB") from exc
    finally:
        if client is not None:
            client.close()


def _load_plan(path: str):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Не удалось прочитать JSON-план") from exc
    return validate_plan(raw)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Измерить выбранные read-only GET API-маршруты")
    parser.add_argument("--db-name", required=True)
    parser.add_argument("--plan", required=True, help="Путь к JSON-массиву [{name,path}]")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--timing-only", action="store_true", help="Задержки без Mongo listener; query metrics=null, explain отдельно")
    parser.add_argument("--without-rate-limit", action="store_true", help="Временно отключить лимит только для in-process benchmark")
    parser.add_argument("--label", default="local")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        db_name = validate_db_name(args.db_name)
        if not 1 <= args.samples <= 100:
            raise ValueError("--samples должен быть от 1 до 100")
        plan = _load_plan(args.plan)
        mongo_url = os.environ.get("MONGO_URL")
        if not mongo_url:
            raise ValueError("Требуется MONGO_URL; URI не выводится")
        _check_read_only_mongo(db_name, mongo_url)
        backend_path = str(Path(__file__).resolve().parents[1])
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        asyncio.run(_run_profile(
            db_name, plan, args.samples, args.label, args.output,
            without_rate_limit=args.without_rate_limit, timing_only=args.timing_only,
        ))
        return 0
    except ValueError as exc:
        parser.error(str(exc))
    except Exception as exc:
        print(f"Ошибка профилирования: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
