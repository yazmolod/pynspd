import os
import shutil
from pathlib import Path

import pytest
from hishel import InMemoryStorage, RedisStorage

from pynspd import Nspd


@pytest.fixture(scope="session")
def file_cache_api():
    with Nspd(cache_folder_path=".test.cache") as client:
        yield client
        shutil.rmtree(".test.cache")


@pytest.fixture(scope="session")
def sqlite_cache_api():
    cache_path = (Path.cwd() / ".test.cache.sqlite").resolve()
    with Nspd(cache_sqlite_url=cache_path) as client:
        yield client
    cache_path.unlink()


@pytest.fixture(scope="session")
def redis_cache_api():
    with Nspd(cache_redis_url=os.environ["REDIS_URL"], trust_env=False) as client:
        yield client
        cache: RedisStorage = client._cache_storage
        cache._client.flushdb()


@pytest.fixture(scope="session")
def custom_cache_api():
    with Nspd(cache_storage=InMemoryStorage()) as client:
        yield client


def request(api: Nspd):
    return api.request(
        "get",
        "/api/geoportal/v2/search/geoportal",
        params={
            "query": "77:02:0021001:5304",
            "thematicSearchId": 1,
        },
    )


def req_assertion(api: Nspd):
    r = request(api)
    assert not r.extensions["from_cache"]
    r = request(api)
    assert r.extensions["from_cache"]


def test_file_cache_client(file_cache_api: Nspd):
    req_assertion(file_cache_api)


def test_sqlite_cache_client(sqlite_cache_api: Nspd):
    req_assertion(sqlite_cache_api)


def test_redis_cache_client(redis_cache_api: Nspd):
    req_assertion(redis_cache_api)


def test_custom_cache_client(custom_cache_api: Nspd):
    req_assertion(custom_cache_api)


def test_multiple_cache_client():
    with pytest.raises(ValueError):
        with Nspd(cache_redis_url="foo", cache_sqlite_url="bar") as api:
            req_assertion(api)
