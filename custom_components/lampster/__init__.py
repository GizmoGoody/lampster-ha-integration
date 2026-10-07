"""The Lampster integration.

Protocol based on: https://github.com/Noki/the-lampster
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card, async_remove_card_resource
from .const import (
    CONF_ALWAYS_CONNECTED,
    CONF_OFF_DISCONNECT_DELAY,
    CONF_POLL_INTERVAL,
    DEFAULT_ALWAYS_CONNECTED,
    DEFAULT_OFF_DISCONNECT_DELAY,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import LampsterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up The Lampster: serve its dashboard card."""
    await async_register_card(hass)
    return True


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
        always_connected=options.get(CONF_ALWAYS_CONNECTED, DEFAULT_ALWAYS_CONNECTED),
        poll_interval=int(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
        off_disconnect_delay=int(
            options.get(CONF_OFF_DISCONNECT_DELAY, DEFAULT_OFF_DISCONNECT_DELAY)
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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the card from the dashboard resources with the last The Lampster."""
    others = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]
    if not others:
        await async_remove_card_resource(hass)
