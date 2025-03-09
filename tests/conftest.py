from pathlib import Path

import pytest
import pytest_asyncio
from hishel import AsyncFileStorage, FileStorage

from pynspd import AsyncNspd, Nspd

cache_folder = Path(__file__).parent / ".cache/hishel"


@pytest.fixture(scope="session")
def api():
    with Nspd(timeout=None) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_api():
    async with AsyncNspd(timeout=None) as client:
        yield client


@pytest.fixture(scope="session")
def cache_api():
    with Nspd(cache_storage=FileStorage(base_path=cache_folder, ttl=300)) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_cache_api():
    async with AsyncNspd(
        cache_storage=AsyncFileStorage(base_path=cache_folder, ttl=300)
    ) as client:
        yield client
