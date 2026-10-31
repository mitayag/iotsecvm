from fastapi import Depends

from backend.helper.client import HelperClient

from .settings import Settings, get_settings


def get_helper(
    settings: Settings = Depends(get_settings),
) -> HelperClient | None:
    if settings.helper_socket is None:
        return None
    return HelperClient(settings.helper_socket, timeout=settings.helper_timeout)
