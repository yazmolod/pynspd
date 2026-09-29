import httpx2 as httpx
import pytest
from pytest_httpx2 import HTTPXMock

from pynspd import AsyncNspd
from pynspd.errors import BlockedIP, PynspdResponseError, PynspdServerError


@pytest.mark.asyncio(scope="session")
async def test_429_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    httpx2_mock.add_response(status_code=429)
    httpx2_mock.add_response(status_code=200)
    r = await async_api.safe_request("get", "/api")
    assert r.status_code == 200
    assert len(httpx2_mock.get_requests()) == 2


@pytest.mark.asyncio(scope="session")
async def test_400_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    httpx2_mock.add_response(status_code=400)
    with pytest.raises(PynspdResponseError) as e:
        await async_api.safe_request("get", "/api")
    assert e.value.response.status_code == 400


@pytest.mark.asyncio(scope="session")
async def test_500_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retries = 1
    httpx2_mock.add_response(status_code=500)
    httpx2_mock.add_response(status_code=500)
    with pytest.raises(PynspdServerError) as e:
        await async_api.safe_request("get", "/api")
    assert e.value.response.status_code == 500
    assert len(httpx2_mock.get_requests()) > async_api._retries


@pytest.mark.asyncio(scope="session")
async def test_remote_disconnect_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    httpx2_mock.add_exception(httpx.RemoteProtocolError("Unexpected disconnect"))
    httpx2_mock.add_response(status_code=200)
    r = await async_api.safe_request("get", "/api")
    assert r.status_code == 200


@pytest.mark.asyncio(scope="session")
async def test_handled_403_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retry_on_blocked_ip = True
    httpx2_mock.add_response(status_code=403)
    httpx2_mock.add_response()
    await async_api.safe_request("get", "/api")
    assert len(httpx2_mock.get_requests()) == 2


@pytest.mark.asyncio(scope="session")
async def test_unhandled_403_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retry_on_blocked_ip = False
    httpx2_mock.add_response(status_code=403)
    with pytest.raises(BlockedIP):
        await async_api.safe_request("get", "/api")
