from pathlib import Path

import dotenv
import pytest
import pytest_asyncio
from hishel import AsyncFileStorage, FileStorage

from pynspd import AsyncNspd, Nspd

cache_folder = Path(__file__).parent / ".cache/hishel"
dotenv.load_dotenv("../.env")


@pytest.fixture(scope="session")
def api():
    with Nspd() as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_api():
    async with AsyncNspd() as client:
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
