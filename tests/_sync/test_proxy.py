import httpx2 as httpx
import pytest
from pytest_httpx2 import HTTPXMock

from pynspd import Nspd


def test_handled_proxy_error(httpx2_mock: HTTPXMock, api: Nspd):
    """Ошибка прокси о невозвожности ресолвить адрес"""
    assert not api._dns_resolve
    httpx2_mock.add_exception(httpx.ProxyError("Connection not allowed by ruleset"))
    httpx2_mock.add_response()
    with pytest.warns():
        api.request("get", "/api")
        assert len(httpx2_mock.get_requests()) == 2


def test_unhandled_proxy_error(httpx2_mock: HTTPXMock, api: Nspd):
    """Неизвестная ошибка прокси"""
    httpx2_mock.add_exception(httpx.ProxyError("Hello world"))
    with pytest.raises(httpx.ProxyError):
        api.request("get", "/api")
