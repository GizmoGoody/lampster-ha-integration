"""The Lampster integration.

Protocol based on: https://github.com/Noki/the-lampster
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DISCONNECT_AFTER,
    CONF_RECONNECT_INTERVAL,
    CONNECTION_CONSTANT,
    DEFAULT_DISCONNECT_AFTER,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    get_connection_mode,
)
from .coordinator import LampsterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up The Lampster from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = entry.data[CONF_ADDRESS]

    # Entries created before 1.4.4 are titled after the Bluetooth name
    if entry.title == "Lampster":
        hass.config_entries.async_update_entry(entry, title="The Lampster")

    # The "Connected" binary sensor (1.1.0-1.3.x) was replaced by the
    # "Connection" status sensor
    registry = er.async_get(hass)
    if old_entity_id := registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{address}_connected"
    ):
        registry.async_remove(old_entity_id)

    # Create coordinator for BLE connection management
    options = entry.options
    coordinator = LampsterCoordinator(
        hass,
        address,
        always_connected=get_connection_mode(options) == CONNECTION_CONSTANT,
        poll_interval=int(
            options.get(CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL)
        ),
        off_disconnect_delay=int(
            options.get(CONF_DISCONNECT_AFTER, DEFAULT_DISCONNECT_AFTER)
        ),
    )

    # Store coordinator for the platforms
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start listening for advertisements only after entities are set up, so
    # they receive the first poll. async_start() returns an unsubscribe
    # callback, which runs when the entry is unloaded.
    entry.async_on_unload(coordinator.async_start())

    # Apply changed connection options by reloading
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LampsterCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()

    return unload_ok
