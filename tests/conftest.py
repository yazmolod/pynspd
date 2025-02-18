import pytest
import pytest_asyncio

from pynspd import AsyncNspd, Nspd


@pytest.fixture(scope="session")
def api():
    with Nspd(timeout=None) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_api():
    async with AsyncNspd(timeout=None) as client:
        yield client
