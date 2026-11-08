"""Config flow for The Lampster integration."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CONNECTION_MODE,
    CONF_DISCONNECT_AFTER,
    CONF_RECONNECT_INTERVAL,
    CONNECTION_MODES,
    CONNECTION_PERIODIC,
    DEFAULT_DISCONNECT_AFTER,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    get_connection_mode,
)

_LOGGER = logging.getLogger(__name__)


class LampsterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for The Lampster."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LampsterOptionsFlow:
        """Get the options flow for this handler."""
        return LampsterOptionsFlow()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title="The Lampster",
                data={CONF_ADDRESS: self._discovery_info.address},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": "The Lampster"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            discovery_info = self._discovered_devices[address]

            return self.async_create_entry(
                title="The Lampster",
                data={CONF_ADDRESS: address},
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            # Check if device name contains "Lamp"
            if (
                discovery_info.name
                and "Lamp" in discovery_info.name
                and discovery_info.address not in current_addresses
                and discovery_info.address not in self._discovered_devices
            ):
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"The Lampster ({address})"
                            for address, info in self._discovered_devices.items()
                        }
                    ),
                }
            ),
        )


def _seconds_selector(minimum: int, maximum: int, step: int) -> NumberSelector:
    """Return a number box for a duration in seconds."""
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement="s",
            mode=NumberSelectorMode.BOX,
        )
    )


class LampsterOptionsFlow(config_entries.OptionsFlow):
    """Handle the Bluetooth connection options for The Lampster.

    The timing options only apply to the Periodic connection, so they are
    shown on a second step only in that case.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the connection mode."""
        options = self.config_entry.options
        if user_input is not None:
            if user_input[CONF_CONNECTION_MODE] == CONNECTION_PERIODIC:
                return await self.async_step_timing()
            # Keep the timing values for when Periodic is chosen again
            return self.async_create_entry(
                data={
                    CONF_CONNECTION_MODE: user_input[CONF_CONNECTION_MODE],
                    CONF_RECONNECT_INTERVAL: options.get(
                        CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL
                    ),
                    CONF_DISCONNECT_AFTER: options.get(
                        CONF_DISCONNECT_AFTER, DEFAULT_DISCONNECT_AFTER
                    ),
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECTION_MODE,
                        default=get_connection_mode(options),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=mode, label=mode.capitalize())
                                for mode in CONNECTION_MODES
                            ],
                            translation_key=CONF_CONNECTION_MODE,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_timing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set the Periodic connection timing."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_CONNECTION_MODE: CONNECTION_PERIODIC, **user_input}
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="timing",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RECONNECT_INTERVAL,
                        default=options.get(
                            CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL
                        ),
                    ): _seconds_selector(10, 300, 5),
                    vol.Optional(
                        CONF_DISCONNECT_AFTER,
                        default=options.get(
                            CONF_DISCONNECT_AFTER, DEFAULT_DISCONNECT_AFTER
                        ),
                    ): _seconds_selector(0, 600, 5),
                }
            ),
        )
