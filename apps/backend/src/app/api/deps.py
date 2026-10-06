"""Request-scoped helpers shared by API routers."""

from __future__ import annotations

from fastapi import Request

from geo_common.config import Settings
from geo_common.storage import LocalStorage, StorageBackend


def get_storage(request: Request) -> StorageBackend:
    """The local storage backend (ADR-0006), created on first use so tests never touch ./data by accident."""
    if getattr(request.app.state, "storage", None) is None:
        s: Settings = request.app.state.settings
        request.app.state.storage = LocalStorage(s.STORAGE_LOCAL_PATH)
    storage: StorageBackend = request.app.state.storage
    return storage
