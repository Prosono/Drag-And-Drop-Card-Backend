from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN

class DragDropBackendFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        # Single instance only
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # No user parameters; just create the entry
        return self.async_create_entry(title="Drag & Drop Card Backend", data={})

    async def async_step_import(self, user_input):
        # Import from YAML (if someone still has it)
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Drag & Drop Card Backend", data={})
