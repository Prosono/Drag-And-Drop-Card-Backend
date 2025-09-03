DOMAIN = "drag_and_drop_card_backend"

# Keep the old storage filename so existing users don't lose data
STORAGE_VERSION = 1
STORAGE_FILENAME = "dragdrop_storage"

# HTTP paths — keep legacy + add a namespaced alias
PATH_LEGACY_BASE = "/api/dragdrop_storage"
PATH_ALIAS_BASE  = f"/api/{DOMAIN}"
