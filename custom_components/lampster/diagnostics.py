"""Diagnostics support for The Lampster integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LampsterCoordinator

# The lamp's Bluetooth address identifies the device; keep it out of shared files
TO_REDACT = {CONF_ADDRESS, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LampsterCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "coordinator": coordinator.diagnostics(),
    }
