import httpx2 as httpx
import pytest
from pytest_httpx2 import HTTPXMock

from pynspd import AsyncNspd


@pytest.mark.asyncio(scope="session")
async def test_handled_proxy_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    """Ошибка прокси о невозвожности ресолвить адрес"""
    assert not async_api._dns_resolve
    httpx2_mock.add_exception(httpx.ProxyError("Connection not allowed by ruleset"))
    httpx2_mock.add_response()
    with pytest.warns():
        await async_api.request("get", "/api")
        assert len(httpx2_mock.get_requests()) == 2


@pytest.mark.asyncio(scope="session")
async def test_unhandled_proxy_error(httpx2_mock: HTTPXMock, async_api: AsyncNspd):
    """Неизвестная ошибка прокси"""
    httpx2_mock.add_exception(httpx.ProxyError("Hello world"))
    with pytest.raises(httpx.ProxyError):
        await async_api.request("get", "/api")
