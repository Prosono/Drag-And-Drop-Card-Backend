from __future__ import annotations

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN, STORAGE_VERSION, STORAGE_FILENAME,
    PATH_LEGACY_BASE, PATH_ALIAS_BASE
)

class _Storage:
    """Simple key->json store wrapped around HA Store."""
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_FILENAME)
        self._data: dict[str, dict] | None = None

    async def ensure_loaded(self) -> None:
        if self._data is None:
            self._data = await self._store.async_load() or {}

    async def keys(self) -> list[str]:
        await self.ensure_loaded()
        return list(self._data.keys())

    async def get(self, key: str) -> dict | None:
        await self.ensure_loaded()
        return self._data.get(key)

    async def set(self, key: str, value: dict) -> None:
        await self.ensure_loaded()
        self._data[key] = value
        await self._store.async_save(self._data)


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
