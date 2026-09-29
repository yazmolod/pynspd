import httpx2 as httpx
import pytest
from pytest_httpx2 import HTTPXMock

from pynspd import Nspd
from pynspd.errors import BlockedIP, PynspdResponseError, PynspdServerError


def test_429_error(httpx2_mock: HTTPXMock, api: Nspd):
    httpx2_mock.add_response(status_code=429)
    httpx2_mock.add_response(status_code=200)
    r = api.safe_request("get", "/api")
    assert r.status_code == 200
    assert len(httpx2_mock.get_requests()) == 2


def test_400_error(httpx2_mock: HTTPXMock, api: Nspd):
    httpx2_mock.add_response(status_code=400)
    with pytest.raises(PynspdResponseError) as e:
        api.safe_request("get", "/api")
    assert e.value.response.status_code == 400


def test_500_error(httpx2_mock: HTTPXMock, api: Nspd):
    api._retries = 1
    httpx2_mock.add_response(status_code=500)
    httpx2_mock.add_response(status_code=500)
    with pytest.raises(PynspdServerError) as e:
        api.safe_request("get", "/api")
    assert e.value.response.status_code == 500
    assert len(httpx2_mock.get_requests()) > api._retries


def test_remote_disconnect_error(httpx2_mock: HTTPXMock, api: Nspd):
    httpx2_mock.add_exception(httpx.RemoteProtocolError("Unexpected disconnect"))
    httpx2_mock.add_response(status_code=200)
    r = api.safe_request("get", "/api")
    assert r.status_code == 200


def test_handled_403_error(httpx2_mock: HTTPXMock, api: Nspd):
    api._retry_on_blocked_ip = True
    httpx2_mock.add_response(status_code=403)
    httpx2_mock.add_response()
    api.safe_request("get", "/api")
    assert len(httpx2_mock.get_requests()) == 2


def test_unhandled_403_error(httpx2_mock: HTTPXMock, api: Nspd):
    api._retry_on_blocked_ip = False
    httpx2_mock.add_response(status_code=403)
    with pytest.raises(BlockedIP):
        api.safe_request("get", "/api")
