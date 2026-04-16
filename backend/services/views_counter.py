"""
Батчевый счётчик просмотров.

Вместо записи в MongoDB на каждый просмотр, накапливает инкременты
в памяти и сбрасывает в БД пачкой раз в FLUSH_INTERVAL секунд.

Было:  1M визитов/мес → 1M update_one → ~400 записей/час
Стало: 1M визитов/мес → ~400 bulk_write → ~0.1 запись/сек

Использование:
    from services.views_counter import views_counter
    
    views_counter.increment("kvn", doc_id)   # мгновенно, без DB
    # Фоновый flush каждые 30с
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("views_counter")

FLUSH_INTERVAL = 30  # секунд


class ViewsCounter:
    """In-memory батчевый счётчик просмотров с периодическим flush в MongoDB."""

    def __init__(self):
        # {(collection_name, doc_id_str): count}
        self._buffer: Dict[Tuple[str, str], int] = defaultdict(int)
        self._task: asyncio.Task | None = None
        self._db: AsyncIOMotorDatabase | None = None

    def increment(self, collection: str, doc_id) -> None:
        """Инкрементирует счётчик в памяти. Мгновенно, без DB."""
        key = (collection, str(doc_id))
        self._buffer[key] += 1

    async def start(self, db: AsyncIOMotorDatabase) -> None:
        """Запускает фоновый flush. Вызывается при старте приложения."""
        self._db = db
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._flush_loop())
            logger.info("Views counter background flush started (interval=%ds)", FLUSH_INTERVAL)

    async def stop(self) -> None:
        """Останавливает фоновый цикл и делает финальный flush."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Финальный flush при остановке
        await self.flush()
        logger.info("Views counter stopped, final flush done")

    async def flush(self) -> int:
        """Сбрасывает накопленные счётчики в MongoDB. Возвращает кол-во обновлений."""
        if not self._buffer or self._db is None:
            return 0

        # Атомарно забираем буфер
        buffer = dict(self._buffer)
        self._buffer.clear()

        # Группируем по коллекциям
        by_collection: Dict[str, Dict[str, int]] = defaultdict(dict)
        for (coll, doc_id), count in buffer.items():
            by_collection[coll][doc_id] = count

        total_ops = 0
        for coll_name, doc_counts in by_collection.items():
            try:
                collection = self._db[coll_name]
                from pymongo import UpdateOne
                ops = [
                    UpdateOne({"_id": doc_id}, {"$inc": {"views": count}})
                    for doc_id, count in doc_counts.items()
                ]
                if ops:
                    result = await collection.bulk_write(ops, ordered=False)
                    total_ops += result.modified_count
            except Exception as e:
                logger.error("Views flush failed for %s: %s", coll_name, e)
                # Возвращаем неуспешные обратно в буфер
                for doc_id, count in doc_counts.items():
                    self._buffer[(coll_name, doc_id)] += count

        if total_ops > 0:
            logger.debug("Views flushed: %d updates across %d collections",
                         total_ops, len(by_collection))
        return total_ops

    async def _flush_loop(self) -> None:
        """Фоновый цикл: сбрасывает буфер каждые FLUSH_INTERVAL секунд."""
        while True:
            try:
                await asyncio.sleep(FLUSH_INTERVAL)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Views flush loop error: %s", e)

    def pending_count(self) -> int:
        """Количество ожидающих записей в буфере."""
        return sum(self._buffer.values())

    def stats(self) -> dict:
        """Статистика для отладки."""
        return {
            "pending_increments": self.pending_count(),
            "unique_documents": len(self._buffer),
            "flush_interval_sec": FLUSH_INTERVAL,
        }


# Singleton
views_counter = ViewsCounter()
