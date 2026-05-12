from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN, STORAGE_VERSION, STORAGE_FILENAME,
    PATH_LEGACY_BASE, PATH_ALIAS_BASE
)

DEFAULT_PACKAGES_DIRNAME = "packages"


def _slugify_token(value: object, fallback: str = "item") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"\.ya?ml$", "", raw, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return slug or fallback


def _legacy_slugify_token(value: object, fallback: str = "item") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"\.ya?ml$", "", raw, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9_-]+", "_", raw).strip("_")
    return slug or fallback


def _package_entries(packages: object) -> list[dict]:
    if isinstance(packages, list):
        return [item for item in packages if isinstance(item, dict)]

    if isinstance(packages, dict):
        entries: list[dict] = []
        for package_id, item in packages.items():
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry.setdefault("id", package_id)
            entries.append(entry)
        return entries

    return []


def _normalize_package_entries(packages: object) -> list[dict]:
    normalized: list[dict] = []
    used_filenames: set[str] = set()

    for index, raw_pkg in enumerate(_package_entries(packages)):
        raw_id = raw_pkg.get("id") or raw_pkg.get("package_id") or f"package_{index + 1}"
        package_id = str(raw_id).strip() or f"package_{index + 1}"
        raw_name = raw_pkg.get("name") or raw_pkg.get("title") or raw_pkg.get("filename") or package_id
        name = str(raw_name).strip() or package_id

        base_filename = _slugify_token(
            raw_pkg.get("filename") or raw_pkg.get("slug") or name or package_id,
            f"package_{index + 1}",
        )
        filename = f"{base_filename}.yaml"
        suffix = 2
        while filename in used_filenames:
            filename = f"{base_filename}_{suffix}.yaml"
            suffix += 1
        used_filenames.add(filename)

        yaml_text = str(
            raw_pkg.get("yaml")
            or raw_pkg.get("content")
            or raw_pkg.get("body")
            or ""
        ).replace("\r\n", "\n")

        normalized.append(
            {
                **raw_pkg,
                "id": package_id,
                "name": name,
                "slug": base_filename,
                "filename": filename,
                "yaml": yaml_text,
                "enabled": raw_pkg.get("enabled", True) is not False,
            }
        )

    return normalized


def _package_file_name(storage_key: str, package: dict) -> str:
    key_token = _slugify_token(storage_key, "layout")
    filename = package.get("filename") or package.get("name") or package.get("id") or "package"
    pkg_token = _slugify_token(filename, "package")
    return f"ddc_{key_token}_{pkg_token}.yaml"


def _package_directory(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DEFAULT_PACKAGES_DIRNAME))


def _configuration_yaml_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path("configuration.yaml"))


def _normalize_payload(body: dict) -> dict:
    payload = dict(body)
    if "packages" in payload:
        payload["packages"] = _normalize_package_entries(payload.get("packages"))
    return payload


def _payload_packages(payload: dict | None) -> object:
    if not isinstance(payload, dict):
        return None
    return payload.get("packages")


async def _read_text_if_exists(path: Path) -> str | None:
    def _read() -> str | None:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    return await asyncio.to_thread(_read)


async def _write_text(path: Path, content: str) -> None:
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")


async def _unlink_if_exists(path: Path) -> bool:
    def _unlink() -> bool:
        if not path.exists():
            return False
        path.unlink()
        return True

    return await asyncio.to_thread(_unlink)


async def _existing_package_filenames(package_dir: Path, storage_key: str) -> set[str]:
    key_token = _slugify_token(storage_key, "layout")
    legacy_key_token = _legacy_slugify_token(storage_key, "layout")
    patterns = [
        f"ddc_{key_token}_*.yaml",
        f"ddc_{legacy_key_token}_*.yaml",
        f"ddc__{key_token}__*.yaml",
        f"ddc__{legacy_key_token}__*.yaml",
    ]

    def _collect() -> set[str]:
        if not package_dir.exists() or not package_dir.is_dir():
            return set()
        found: set[str] = set()
        for pattern in patterns:
            found.update(path.name for path in package_dir.glob(pattern) if path.is_file())
        return found

    return await asyncio.to_thread(_collect)


async def _package_sync_diagnostics(hass: HomeAssistant) -> dict:
    package_dir = _package_directory(hass)
    config_path = _configuration_yaml_path(hass)

    def _collect() -> dict:
        package_dir_exists = package_dir.exists()
        package_dir_is_dir = package_dir.is_dir()
        package_dir_writable = False
        if package_dir_exists:
            package_dir_writable = package_dir_is_dir and os.access(package_dir, os.W_OK)
        else:
            parent = package_dir.parent
            package_dir_writable = parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)

        config_exists = config_path.exists()
        config_text = config_path.read_text(encoding="utf-8") if config_exists else ""
        mentions_packages = "packages:" in config_text
        includes_dir_named = "!include_dir_named packages" in config_text
        includes_dir_merge_named = "!include_dir_merge_named packages" in config_text
        files = []
        if package_dir_exists and package_dir_is_dir:
            files = sorted(
                {
                    *[path.name for path in package_dir.glob("ddc_*.yaml") if path.is_file()],
                    *[path.name for path in package_dir.glob("ddc__*.yaml") if path.is_file()],
                }
            )

        return {
            "ok": True,
            "supported": True,
            "supports_package_sync": True,
            "directory": str(package_dir),
            "directory_exists": package_dir_exists,
            "directory_is_dir": package_dir_is_dir,
            "directory_writable": package_dir_writable,
            "configuration_yaml": str(config_path),
            "configuration_exists": config_exists,
            "configuration_yaml_exists": config_exists,
            "configuration_mentions_packages": mentions_packages,
            "packages_mentioned": mentions_packages,
            "configuration_includes_packages_dir_named": includes_dir_named,
            "configuration_includes_packages_dir_merge_named": includes_dir_merge_named,
            "include_dir_named": includes_dir_named,
            "include_dir_merge_named": includes_dir_merge_named,
            "packages_include_configured": includes_dir_named or includes_dir_merge_named,
            "files": files,
            "ddc_files": files,
            "file_count": len(files),
        }

    return await asyncio.to_thread(_collect)


async def _sync_package_files(
    hass: HomeAssistant,
    storage_key: str,
    previous_payload: dict | None,
    next_payload: dict | None,
) -> dict:
    package_dir = _package_directory(hass)
    previous_packages = _normalize_package_entries(_payload_packages(previous_payload))
    next_packages = _normalize_package_entries(_payload_packages(next_payload))

    previous_files = {
        _package_file_name(storage_key, package): package
        for package in previous_packages
        if package.get("enabled", True) and str(package.get("yaml") or "").strip()
    }
    next_files = {
        _package_file_name(storage_key, package): package
        for package in next_packages
        if package.get("enabled", True) and str(package.get("yaml") or "").strip()
    }

    deleted: list[str] = []
    written: list[str] = []

    if next_files:
        await asyncio.to_thread(package_dir.mkdir, parents=True, exist_ok=True)

    existing_files = await _existing_package_filenames(package_dir, storage_key)
    obsolete_files = (set(previous_files) | existing_files) - set(next_files)

    for filename in sorted(obsolete_files):
        path = package_dir / filename
        if await _unlink_if_exists(path):
            deleted.append(filename)

    for filename, package in next_files.items():
        path = package_dir / filename
        yaml_text = str(package.get("yaml") or "").replace("\r\n", "\n")
        if yaml_text and not yaml_text.endswith("\n"):
            yaml_text += "\n"
        existing = await _read_text_if_exists(path)
        if existing == yaml_text:
            continue
        await _write_text(path, yaml_text)
        written.append(filename)

    return {
        "ok": True,
        "directory": str(package_dir),
        "count": len(next_files),
        "written": written,
        "deleted": deleted,
    }

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


class PackageStatusView(HomeAssistantView):
    name = f"{DOMAIN}:package_status"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        self.url = url
        self.hass = hass

    async def get(self, request):
        try:
            return self.json(await _package_sync_diagnostics(self.hass))
        except Exception as err:
            return self.json(
                {
                    "ok": False,
                    "supports_package_sync": True,
                    "error": str(err),
                    "directory": str(_package_directory(self.hass)),
                    "configuration_yaml": str(_configuration_yaml_path(self.hass)),
                }
            )


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
        try:
            body = await request.json()
        except Exception as err:
            raise web.HTTPBadRequest(text="Invalid JSON") from err

        if not isinstance(body, dict):
            raise web.HTTPBadRequest(text="Expected JSON object")

        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        previous = await store.get(key)
        payload = _normalize_payload(body)
        await store.set(key, payload)

        try:
            package_sync = await _sync_package_files(self.hass, key, previous, payload)
        except Exception as err:
            package_sync = {
                "ok": False,
                "error": str(err),
                "directory": str(_package_directory(self.hass)),
            }

        return self.json({"ok": True, "package_sync": package_sync})

    async def delete(self, request, key: str):
        """
        Remove the given key from storage.

        This handler implements HTTP DELETE for the ItemView.  It calls
        ``store.delete(key)`` to remove the entry.  If the key does not
        exist, a 404 is returned; otherwise, it responds with
        ``{"ok": True}``.
        """
        store: _Storage = request.app["hass"].data[DOMAIN]["store"]
        previous = await store.get(key)
        removed = await store.delete(key)
        if not removed:
            # Raise HTTPNotFound to return a 404 to the client
            raise web.HTTPNotFound(text="Key not found")
        try:
            package_sync = await _sync_package_files(self.hass, key, previous, {})
        except Exception as err:
            package_sync = {
                "ok": False,
                "error": str(err),
                "directory": str(_package_directory(self.hass)),
            }
        return self.json({"ok": True, "package_sync": package_sync})


def register_http(hass: HomeAssistant) -> None:
    """Register both legacy and aliased routes once."""
    if hass.data.setdefault(DOMAIN, {}).get("http_registered"):
        return

    hass.data[DOMAIN]["store"] = _Storage(hass)

    # Legacy endpoints (what your card already calls)
    hass.http.register_view(KeysView(hass, PATH_LEGACY_BASE))
    hass.http.register_view(ItemView(hass, PATH_LEGACY_BASE))
    hass.http.register_view(PackageStatusView(hass, f"{PATH_LEGACY_BASE}_package_status"))

    # Aliased endpoints (new, nice to have)
    hass.http.register_view(KeysView(hass, PATH_ALIAS_BASE))
    hass.http.register_view(ItemView(hass, PATH_ALIAS_BASE))
    hass.http.register_view(PackageStatusView(hass, f"{PATH_ALIAS_BASE}_package_status"))

    hass.data[DOMAIN]["http_registered"] = True
