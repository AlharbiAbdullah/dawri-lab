import httpx
import pytest
from pytest_socket import SocketBlockedError

from dawri.config import BASE_URL


@pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")
def test_network_is_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        httpx.get(BASE_URL)
