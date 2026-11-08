"""Tests for the config and options flows, and diagnostics."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.lampster.const import (
    CONF_ALWAYS_CONNECTED,
    CONF_OFF_DISCONNECT_DELAY,
    CONF_POLL_INTERVAL,
    DOMAIN,
)
from custom_components.lampster.diagnostics import async_get_config_entry_diagnostics

from .conftest import ADDRESS

DISCOVERY = SimpleNamespace(address=ADDRESS, name="Lampster")


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """A discovered lamp is confirmed and added as The Lampster."""
    with patch("custom_components.lampster.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=DISCOVERY
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "The Lampster"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """A lamp that is already set up is not offered again."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Manual setup aborts when no lamp is in range."""
    with patch(
        "custom_components.lampster.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_picks_device(hass: HomeAssistant) -> None:
    """Manual setup lists the lamp and creates the entry."""
    with (
        patch(
            "custom_components.lampster.config_flow.async_discovered_service_info",
            return_value=[DISCOVERY],
        ),
        patch("custom_components.lampster.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "The Lampster"


async def test_options_timing_step(hass: HomeAssistant) -> None:
    """Unchecked: the timing settings are asked on a second step."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALWAYS_CONNECTED: False}
    )
    assert result["step_id"] == "timing"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_POLL_INTERVAL: 45, CONF_OFF_DISCONNECT_DELAY: 120}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_ALWAYS_CONNECTED: False,
        CONF_POLL_INTERVAL: 45,
        CONF_OFF_DISCONNECT_DELAY: 120,
    }


async def test_options_always_connected_skips_timing(hass: HomeAssistant) -> None:
    """Checked: the flow finishes on the first step and keeps timing values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
        options={CONF_POLL_INTERVAL: 45, CONF_OFF_DISCONNECT_DELAY: 120},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALWAYS_CONNECTED: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ALWAYS_CONNECTED] is True
    assert entry.options[CONF_POLL_INTERVAL] == 45


async def test_diagnostics_redacts_address(hass: HomeAssistant) -> None:
    """The Bluetooth address is not included in the diagnostics download."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {
        entry.entry_id: SimpleNamespace(diagnostics=lambda: {"connection_status": "connected"})
    }
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert ADDRESS not in str(result)
    assert result["coordinator"] == {"connection_status": "connected"}
