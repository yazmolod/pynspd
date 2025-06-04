import httpx
import pytest
from pytest_httpx import HTTPXMock

from pynspd import Nspd
from pynspd.errors import BlockedIP


def test_429_error(httpx_mock: HTTPXMock, api: Nspd):
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200)
    r = api.safe_request("get", "/api")
    assert r.status_code == 200
    assert len(httpx_mock.get_requests()) == 2


def test_400_error(httpx_mock: HTTPXMock, api: Nspd):
    httpx_mock.add_response(status_code=400)
    with pytest.raises(httpx.HTTPStatusError) as e:
        api.safe_request("get", "/api")
    assert e.value.response.status_code == 400


def test_500_error(httpx_mock: HTTPXMock, api: Nspd):
    api._retries = 1
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(status_code=500)
    with pytest.raises(httpx.HTTPStatusError) as e:
        api.safe_request("get", "/api")
    assert e.value.response.status_code == 500
    assert len(httpx_mock.get_requests()) > api._retries


def test_remote_disconnect_error(httpx_mock: HTTPXMock, api: Nspd):
    httpx_mock.add_exception(httpx.RemoteProtocolError("Unexpected disconnect"))
    httpx_mock.add_response(status_code=200)
    r = api.safe_request("get", "/api")
    assert r.status_code == 200


def test_handled_403_error(httpx_mock: HTTPXMock, api: Nspd):
    api._retry_on_blocked_ip = True
    httpx_mock.add_response(status_code=403)
    httpx_mock.add_response()
    api.safe_request("get", "/api")
    assert len(httpx_mock.get_requests()) == 2


def test_unhandled_403_error(httpx_mock: HTTPXMock, api: Nspd):
    api._retry_on_blocked_ip = False
    httpx_mock.add_response(status_code=403)
    with pytest.raises(BlockedIP):
        api.safe_request("get", "/api")
