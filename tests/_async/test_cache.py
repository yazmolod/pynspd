import os
import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from hishel import AsyncInMemoryStorage, AsyncRedisStorage

from pynspd import AsyncNspd


@pytest_asyncio.fixture(scope="session")
async def file_cache_api():
    async with AsyncNspd(cache_folder_path=".test.cache") as client:
        yield client
        shutil.rmtree(".test.cache")


@pytest_asyncio.fixture(scope="session")
async def sqlite_cache_api():
    cache_path = (Path.cwd() / ".test.cache.sqlite").resolve()
    async with AsyncNspd(cache_sqlite_url=cache_path) as client:
        yield client
    cache_path.unlink()


@pytest_asyncio.fixture(scope="session")
async def redis_cache_api():
    async with AsyncNspd(
        cache_redis_url=os.environ["REDIS_URL"], trust_env=False
    ) as client:
        yield client
        cache: AsyncRedisStorage = client._cache_storage
        await cache._client.flushdb()


@pytest_asyncio.fixture(scope="session")
async def custom_cache_api():
    async with AsyncNspd(cache_storage=AsyncInMemoryStorage()) as client:
        yield client


async def request(api: AsyncNspd):
    return await api.request(
        "get",
        "/async_api/geoportal/v2/search/geoportal",
        params={
            "query": "77:02:0021001:5304",
            "thematicSearchId": 1,
        },
    )


async def req_assertion(api: AsyncNspd):
    r = await request(api)
    assert not r.extensions["from_cache"]
    r = await request(api)
    assert r.extensions["from_cache"]


@pytest.mark.asyncio(scope="session")
async def test_file_cache_client(file_cache_api: AsyncNspd):
    await req_assertion(file_cache_api)


@pytest.mark.asyncio(scope="session")
async def test_sqlite_cache_client(sqlite_cache_api: AsyncNspd):
    await req_assertion(sqlite_cache_api)


@pytest.mark.asyncio(scope="session")
async def test_redis_cache_client(redis_cache_api: AsyncNspd):
    await req_assertion(redis_cache_api)


@pytest.mark.asyncio(scope="session")
async def test_custom_cache_client(custom_cache_api: AsyncNspd):
    await req_assertion(custom_cache_api)


@pytest.mark.asyncio(scope="session")
async def test_multiple_cache_client():
    with pytest.raises(ValueError):
        async with AsyncNspd(cache_redis_url="foo", cache_sqlite_url="bar") as api:
            await req_assertion(api)
