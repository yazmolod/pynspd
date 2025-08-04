import httpx
import pytest
from pytest_httpx import HTTPXMock

from pynspd import AsyncNspd
from pynspd.errors import BlockedIP, PynspdServerError


@pytest.mark.asyncio(scope="session")
async def test_429_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200)
    r = await async_api.safe_request("get", "/api")
    assert r.status_code == 200
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio(scope="session")
async def test_400_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    httpx_mock.add_response(status_code=400)
    with pytest.raises(httpx.HTTPStatusError) as e:
        await async_api.safe_request("get", "/api")
    assert e.value.response.status_code == 400


@pytest.mark.asyncio(scope="session")
async def test_500_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retries = 1
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(status_code=500)
    with pytest.raises(PynspdServerError) as e:
        await async_api.safe_request("get", "/api")
    assert e.value.response.status_code == 500
    assert len(httpx_mock.get_requests()) > async_api._retries


@pytest.mark.asyncio(scope="session")
async def test_remote_disconnect_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    httpx_mock.add_exception(httpx.RemoteProtocolError("Unexpected disconnect"))
    httpx_mock.add_response(status_code=200)
    r = await async_api.safe_request("get", "/api")
    assert r.status_code == 200


@pytest.mark.asyncio(scope="session")
async def test_handled_403_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retry_on_blocked_ip = True
    httpx_mock.add_response(status_code=403)
    httpx_mock.add_response()
    await async_api.safe_request("get", "/api")
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio(scope="session")
async def test_unhandled_403_error(httpx_mock: HTTPXMock, async_api: AsyncNspd):
    async_api._retry_on_blocked_ip = False
    httpx_mock.add_response(status_code=403)
    with pytest.raises(BlockedIP):
        await async_api.safe_request("get", "/api")
