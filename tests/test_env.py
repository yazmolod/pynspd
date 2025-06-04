import os

import pytest

from pynspd import Nspd


def test_env_warning():
    os.environ["PYNSPD_CLIENT_TIMEOUT"] = "10"
    with pytest.warns():
        api = Nspd(client_timeout=5)
        assert api._timeout == 10
