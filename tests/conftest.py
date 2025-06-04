import dotenv
import pytest
import pytest_asyncio

from pynspd import AsyncNspd, Nspd

dotenv.load_dotenv()


@pytest.fixture(scope="session")
def api():
    with Nspd() as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_api():
    async with AsyncNspd() as client:
        yield client
