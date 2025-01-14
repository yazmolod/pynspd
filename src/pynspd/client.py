import ssl
from typing import Optional

import httpx
from httpx._types import ProxyTypes

# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def _get_client_args(retries, proxy):
    return (
        dict(
            base_url="https://nspd.gov.ru",
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Referer": "https://nspd.gov.ru",
            },
        ),
        dict(verify=SSL_CONTEXT, retries=retries, proxy=proxy),
    )


def get_async_client(
    retries: int = 0, proxy: Optional[ProxyTypes] = None
) -> httpx.AsyncClient:
    client_args, transport_args = _get_client_args(retries, proxy)
    transport = httpx.AsyncHTTPTransport(**transport_args)
    return httpx.AsyncClient(**client_args, transport=transport)


def get_client(retries: int = 0, proxy: Optional[ProxyTypes] = None) -> httpx.Client:
    client_args, transport_args = _get_client_args(retries, proxy)
    transport = httpx.HTTPTransport(**transport_args)
    return httpx.Client(**client_args, transport=transport)
