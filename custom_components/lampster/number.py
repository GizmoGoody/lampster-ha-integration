"""Effects speed setting for The Lampster integration."""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LampsterCoordinator
from .effects import EFFECT_SPEED_MAX, EFFECT_SPEED_MIN
from .entity import LampsterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up The Lampster settings from a config entry."""
    coordinator: LampsterCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LampsterEffectsSpeed(coordinator)])


class LampsterEffectsSpeed(LampsterEntity, RestoreNumber):
    """Speed of the effects, in percent of normal.

    Effects chosen from the light (for example in its more-info dialog) run at
    this speed; the start_effect action can give a run its own speed.
    """

    _attr_translation_key = "effects_speed"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = EFFECT_SPEED_MIN
    _attr_native_max_value = EFFECT_SPEED_MAX
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: LampsterCoordinator) -> None:
        """Initialize the setting."""
        super().__init__(coordinator, "effects_speed")
        # Keep IDs short and stable regardless of the device name
        self.entity_id = "number.lampster_effects_speed"

    async def async_added_to_hass(self) -> None:
        """Restore the speed set before Home Assistant restarted."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value:
            self.coordinator.effect_speed = int(last.native_value)

    @property
    def available(self) -> bool:
        """A setting stored in Home Assistant can be changed at any time."""
        return True

    @property
    def native_value(self) -> int:
        """Return the speed in percent."""
        return self.coordinator.effect_speed

    async def async_set_native_value(self, value: float) -> None:
        """Set the speed; a running effect that follows it restarts at the new speed."""
        await self.coordinator.async_set_effect_speed(int(value))
        self.async_write_ha_state()
