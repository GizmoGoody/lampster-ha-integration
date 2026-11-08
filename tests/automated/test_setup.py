"""Tests for setting up and stopping The Lampster integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lampster.const import DOMAIN

from .conftest import ADDRESS


async def test_disconnects_when_home_assistant_stops(hass: HomeAssistant) -> None:
    """Home Assistant does not unload entries when it stops: the integration disconnects itself."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    coordinator = MagicMock(async_start=MagicMock(return_value=lambda: None), async_stop=AsyncMock())
    with (
        patch("custom_components.lampster.LampsterCoordinator", return_value=coordinator),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    coordinator.async_stop.assert_awaited_once_with("Home Assistant stopping")


async def test_no_disconnect_on_stop_after_unload(hass: HomeAssistant) -> None:
    """Once the entry is unloaded, stopping Home Assistant does not disconnect it again."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    coordinator = MagicMock(async_start=MagicMock(return_value=lambda: None), async_stop=AsyncMock())
    with (
        patch("custom_components.lampster.LampsterCoordinator", return_value=coordinator),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_stop.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    coordinator.async_stop.assert_not_awaited()
