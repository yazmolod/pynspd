import ssl

import httpx

# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def get_async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://nspd.gov.ru",
        verify=SSL_CONTEXT,
        timeout=5,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        },
    )
