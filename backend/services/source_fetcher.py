"""Bounded, robots-aware HTTP access to explicitly supported public sources."""
import asyncio
import time
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from services.source_registry import canonical_url, source_for_url, request_url

USER_AGENT = 'HumorpediaEditorialImporter/1.0'
MAX_BYTES = 2_000_000


class SourceFetcher:
    def __init__(self, *, transport=None, delay=1.0):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xml,text/plain'},
            transport=transport, trust_env=False)
        self.delay = delay
        self.last_request = {}
        self.robots = {}
        self.delays = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    async def _read(self, url: str, *, robots=False):
        source = source_for_url(url, resource=True)
        for _ in range(4):
            url = canonical_url(url, resource=True)
            if source_for_url(url, resource=True).id != source.id:
                raise ValueError('Перенаправление на другой источник запрещено')
            transport_url = request_url(url)
            if not robots and not self.robots[source.id].can_fetch(USER_AGENT, transport_url):
                raise ValueError('Получение этого адреса запрещено robots.txt источника')
            delay = self.delays.get(source.id, self.delay)
            await asyncio.sleep(max(0, delay - (time.monotonic() - self.last_request.get(source.id, 0))))
            self.last_request[source.id] = time.monotonic()
            async with self.client.stream('GET', transport_url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get('location')
                    if not location:
                        raise ValueError('Перенаправление без адреса')
                    url = canonical_url(urljoin(transport_url, location), resource=True)
                    continue
                response.raise_for_status()
                content_type = response.headers.get('content-type', '').lower()
                if not any(kind in content_type for kind in ('text/', 'application/xml', 'application/xhtml')):
                    raise ValueError('Источник вернул неожиданный тип данных')
                length = response.headers.get('content-length')
                if length and int(length) > MAX_BYTES:
                    raise ValueError('Страница превышает допустимый размер 2 МБ')
                chunks, size = [], 0
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('Страница превышает допустимый размер 2 МБ')
                    chunks.append(chunk)
                return b''.join(chunks).decode('utf-8-sig', errors='replace')
        raise ValueError('Слишком много перенаправлений')

    async def fetch(self, url: str, *, resource=False) -> str:
        url = canonical_url(url, resource=resource)
        source = source_for_url(url, resource=resource)
        if source.id not in self.robots:
            try:
                text = await self._read(f'https://{source.host}/robots.txt', robots=True)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                # A missing robots file is not a disallow rule. Other HTTP failures stay visible.
                text = 'User-agent: *\nAllow: /'
            parser = RobotFileParser()
            parser.parse(text.splitlines())
            self.robots[source.id] = parser
            self.delays[source.id] = max(self.delay, float(parser.crawl_delay(USER_AGENT) or 0))
        return await self._read(url)
