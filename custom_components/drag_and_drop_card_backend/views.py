from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN, STORAGE_VERSION, STORAGE_FILENAME,
    PATH_LEGACY_BASE, PATH_ALIAS_BASE
)

class _Storage:
    """Simple key->JSON store wrapped around Home Assistant's ``Store``.

    This class lazily loads data from the underlying store on first use,
    caches it in memory, and writes back to disk on mutation.  It
    provides basic CRUD operations (``keys``, ``get``, ``set``,
    ``delete``) over the key/value pairs.  The original version of this
    backend lacked a delete method, which caused HTTP DELETE requests to
    return ``405 Method Not Allowed``.  Adding the delete method here
    enables proper removal of keys.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_FILENAME)
        self._data: dict[str, dict] | None = None

    async def ensure_loaded(self) -> None:
        """Load data from the store into memory if not already loaded."""
        if self._data is None:
            self._data = await self._store.async_load() or {}

    async def keys(self) -> list[str]:
        """Return a list of all keys in the store."""
        await self.ensure_loaded()
        # Return a copy to prevent accidental mutation
        return list(self._data.keys())

    async def get(self, key: str) -> dict | None:
        """Return the value for a key, or ``None`` if it doesn't exist."""
        await self.ensure_loaded()
        return self._data.get(key)

    async def set(self, key: str, value: dict) -> None:
        """Persist a value for a given key to the store."""
        await self.ensure_loaded()
        self._data[key] = value
        await self._store.async_save(self._data)

    async def delete(self, key: str) -> bool:
        """Remove a key from the store.  Returns ``True`` if removed.

        This method mirrors the semantics of ``_KVStore.delete`` from
        ``__init__.py``.  It deletes the key from the in‑memory dict and
        writes the updated data back to disk.  If the key was not
        present, it returns ``False``.
        """
        await self.ensure_loaded()
        if key in self._data:
            # Delete the key and persist the change
            del self._data[key]
            await self._store.async_save(self._data)
            return True
        return False


class KeysView(HomeAssistantView):
    name = f"{DOMAIN}:keys"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        self.url = url
        self.hass = hass

    async def get(self, request):
        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        return self.json(await store.keys())


class ItemView(HomeAssistantView):
    name = f"{DOMAIN}:item"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        self.url = f"{url}" + "/{key}"
        self.hass = hass

    async def get(self, request, key: str):
        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        data = await store.get(key)
        return self.json(data or {})

    async def post(self, request, key: str):
        body = await request.json()
        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        await store.set(key, body)
        return self.json({"ok": True})

    async def delete(self, request, key: str):
        """
        Remove the given key from storage.

        This handler implements HTTP DELETE for the ItemView.  It calls
        ``store.delete(key)`` to remove the entry.  If the key does not
        exist, a 404 is returned; otherwise, it responds with
        ``{"ok": True}``.
        """
        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        removed = await store.delete(key)
        if not removed:
            # Raise HTTPNotFound to return a 404 to the client
            raise web.HTTPNotFound(text="Key not found")
        return self.json({"ok": True})


def register_http(hass: HomeAssistant) -> None:
    """Register both legacy and aliased routes once."""
    if hass.data.setdefault(DOMAIN, {}).get("http_registered"):
        return

    hass.data[DOMAIN]["store"] = _Storage(hass)

    # Legacy endpoints (what your card already calls)
    hass.http.register_view(KeysView(hass, PATH_LEGACY_BASE))
    hass.http.register_view(ItemView(hass, PATH_LEGACY_BASE))

    # Aliased endpoints (new, nice to have)
    hass.http.register_view(KeysView(hass, PATH_ALIAS_BASE))
    hass.http.register_view(ItemView(hass, PATH_ALIAS_BASE))

    hass.data[DOMAIN]["http_registered"] = True
