from __future__ import annotations

import asyncio
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.storage import Store


from .const import DOMAIN
from .views import register_http

DOMAIN = "drag_and_drop_card_backend"
STORAGE_VERSION = 1
STORAGE_FILENAME = DOMAIN  # results in .storage/drag_and_drop_card_backend

class _KVStore:
    """Tiny JSON key/value store persisted via .storage."""
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_FILENAME)
        self._lock = asyncio.Lock()
        self._data: dict[str, object] | None = None

    async def _ensure_loaded(self) -> None:
        if self._data is None:
            self._data = await self._store.async_load() or {}

    async def keys(self) -> list[str]:
        await self._ensure_loaded()
        return list(self._data.keys())  # type: ignore[union-attr]

    async def get(self, key: str) -> object | None:
        await self._ensure_loaded()
        return self._data.get(key)  # type: ignore[union-attr]

    async def set(self, key: str, value: object) -> None:
        await self._ensure_loaded()
        async with self._lock:
            self._data[key] = value  # type: ignore[union-attr]
            await self._store.async_save(self._data)  # type: ignore[arg-type]

    async def delete(self, key: str) -> bool:
        await self._ensure_loaded()
        async with self._lock:
            if key in self._data:  # type: ignore[operator]
                del self._data[key]  # type: ignore[index]
                await self._store.async_save(self._data)  # type: ignore[arg-type]
                return True
        return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Support YAML (optional): import into config entries if present."""
    if DOMAIN in config:
        # Create/refresh a config entry from YAML, then you can delete the YAML line
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={}
            )
        )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up when added via the UI."""
    register_http(hass)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nothing to unload; views stay registered for the lifetime of HA."""
    return True

class KeysView(HomeAssistantView):
    """GET /api/drag_and_drop_card_backend → {"keys": [...]}"""

    url = "/api/dragdrop_storage"
    name = "api:dragdrop_storage:keys"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        store: _KVStore = self.hass.data[DOMAIN]
        keys = await store.keys()
        return self.json({"keys": keys})


class ItemView(HomeAssistantView):
    """GET/POST/DELETE /api/drag_and_drop_card_backend/<key>"""

    url = "/api/dragdrop_storage/{key}"
    name = "api:dragdrop_storage:item"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request, key: str):
        store: _KVStore = self.hass.data[DOMAIN]
        val = await store.get(key)
        if val is None:
            raise web.HTTPNotFound(text="Key not found")
        return self.json(val)

    async def post(self, request, key: str):
        # Expect JSON body; we just store it verbatim.
        try:
            payload = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="Invalid JSON")
        store: _KVStore = self.hass.data[DOMAIN]
        await store.set(key, payload)
        return self.json({"ok": True})

    async def delete(self, request, key: str):
        store: _KVStore = self.hass.data[DOMAIN]
        existed = await store.delete(key)
        if not existed:
            raise web.HTTPNotFound(text="Key not found")
        return self.json({"ok": True})
