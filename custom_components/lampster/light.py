"""Light platform for The Lampster integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from .lampster.models import RGBColor, WhiteColor

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .const import DOMAIN, SERVICE_START_EFFECT
from .coordinator import COMMAND_ERRORS, LampsterCoordinator
from .effects import EFFECT_SPEED_MAX, EFFECT_SPEED_MIN, EFFECTS, MODE_RGB, MODE_WHITE
from .entity import LampsterEntity

_LOGGER = logging.getLogger(__name__)

# Color temperature range in Kelvin
# Warm white: ~2700K, Cool white: ~6500K
MIN_KELVIN = 2700
MAX_KELVIN = 6500
DEFAULT_KELVIN = 3500

# Favorite colors added to the light's more-info dialog: pure colors, then
# common white temperatures. Missing ones are appended to the user's list once.
OFFERED_FAVORITES_KEY = "offered_favorite_colors"
DEFAULT_FAVORITE_COLORS = [
    {"rgb_color": [255, 0, 0]},  # Red
    {"rgb_color": [0, 255, 0]},  # Green
    {"rgb_color": [0, 0, 255]},  # Blue
    {"rgb_color": [255, 255, 255]},  # White (RGB)
    {"rgb_color": [0, 255, 255]},  # Cyan
    {"rgb_color": [255, 0, 255]},  # Magenta
    {"rgb_color": [255, 255, 0]},  # Yellow
    {"color_temp_kelvin": 2700},  # Incandescent
    {"color_temp_kelvin": 3000},  # Warm
    {"color_temp_kelvin": 3200},  # Neutral warm
    {"color_temp_kelvin": 3500},  # Neutral
    {"color_temp_kelvin": 4000},  # Cool
    {"color_temp_kelvin": 4500},  # Cool daylight
    {"color_temp_kelvin": 5000},  # Soft daylight
    {"color_temp_kelvin": 5600},  # Daylight
    {"color_temp_kelvin": 6000},  # Noon daylight
    {"color_temp_kelvin": 6500},  # Bright daylight
]


def _to_percent(value: float) -> int:
    """Convert a 0-255 value to the device's 0-100 range."""
    return max(0, min(100, round(value / 255 * 100)))


def _rgb_to_device(rgb: tuple[int, int, int], brightness: int) -> RGBColor:
    """Convert a full-brightness HA RGB color plus brightness to device values."""
    factor = brightness / 255
    return RGBColor(*(_to_percent(channel * factor) for channel in rgb))


def _kelvin_to_device(kelvin: int, brightness: int) -> WhiteColor:
    """Convert a color temperature plus brightness to warm/cold device values.

    The color comes from the warm/cold ratio; brightness sets the stronger of
    the two channels. The lamp can drive both channels fully at once (its own
    touch button does), so mid temperatures reach full output at 100%.
    """
    kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
    # Lower Kelvin = warmer = more warm LED
    warm_ratio = 1 - ((kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN))
    level = _to_percent(brightness)
    if warm_ratio >= 0.5:
        return WhiteColor(level, round(level * (1 - warm_ratio) / warm_ratio))
    return WhiteColor(round(level * warm_ratio / (1 - warm_ratio)), level)


def _device_to_kelvin(color: WhiteColor) -> tuple[int, int] | None:
    """Return (kelvin, brightness 0-255) for warm/cold device values."""
    total = color.warm + color.cold
    if total == 0:
        return None
    # More warm = lower Kelvin (warmer)
    warm_ratio = color.warm / total
    kelvin = round(MIN_KELVIN + (1 - warm_ratio) * (MAX_KELVIN - MIN_KELVIN))
    return kelvin, round(max(color.warm, color.cold) * 2.55)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up The Lampster light from a config entry."""
    coordinator: LampsterCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([LampsterLight(coordinator)])

    async_get_current_platform().async_register_entity_service(
        SERVICE_START_EFFECT,
        {
            vol.Required("effect"): vol.In(EFFECTS),
            vol.Optional("speed"): vol.All(
                vol.Coerce(int), vol.Range(min=EFFECT_SPEED_MIN, max=EFFECT_SPEED_MAX)
            ),
            vol.Optional("brightness_pct"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
        },
        "async_start_effect_action",
    )


class LampsterLight(LampsterEntity, LightEntity):
    """Representation of The Lampster light."""

    _attr_name = None
    # Selects the desk lamp icons in icons.json
    _attr_translation_key = "lampster"
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
    _attr_effect_list = [EFFECT_OFF, *EFFECTS]
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    # Defaults until the device reports a recognised mode; HA requires a
    # color mode whenever the light is on.
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_color_temp_kelvin = DEFAULT_KELVIN
    _attr_rgb_color = (255, 255, 255)

    def __init__(self, coordinator: LampsterCoordinator) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        # Keep IDs short and stable regardless of the device name
        self.entity_id = "light.lampster"

        # Initialize state from coordinator data
        self._update_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    def _update_from_coordinator(self) -> None:
        """Update entity state from coordinator data.

        When the device is off or in an unknown mode, the last color settings
        are kept so brightness-only changes still have a color to apply.
        """
        if not self.coordinator.data:
            return

        state = self.coordinator.data
        self._attr_is_on = state.is_on

        if state.mode == "rgb" and state.rgb_color:
            self._attr_color_mode = ColorMode.RGB
            rgb = state.rgb_color
            peak = max(rgb.red, rgb.green, rgb.blue)
            if peak > 0:
                # Device values have brightness baked in; HA expects the
                # full-brightness color with brightness reported separately.
                self._attr_rgb_color = (
                    round(rgb.red * 255 / peak),
                    round(rgb.green * 255 / peak),
                    round(rgb.blue * 255 / peak),
                )
            self._attr_brightness = round(peak * 2.55)

        elif state.mode == "white" and state.white_color:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            if converted := _device_to_kelvin(state.white_color):
                self._attr_color_temp_kelvin, self._attr_brightness = converted
            else:
                self._attr_brightness = 0

    async def async_added_to_hass(self) -> None:
        """Add default favorite colors the user does not already have.

        Each default is offered only once (tracked in this entity's own
        registry options), so a default the user removes stays removed.
        """
        await super().async_added_to_hass()
        if not self.registry_entry:
            return
        options = self.registry_entry.options
        light_options = dict(options.get("light", {}))
        favorites = list(light_options.get("favorite_colors", []))
        offered = options.get(DOMAIN, {}).get(OFFERED_FAVORITES_KEY, [])

        def key(color: dict[str, Any]) -> tuple:
            return tuple(
                (attr, tuple(value) if isinstance(value, list | tuple) else value)
                for attr, value in sorted(color.items())
            )

        have = {key(color) for color in favorites}
        already_offered = {key(color) for color in offered}
        new = [
            color
            for color in DEFAULT_FAVORITE_COLORS
            if key(color) not in have and key(color) not in already_offered
        ]

        registry = er.async_get(self.hass)
        if new:
            light_options["favorite_colors"] = favorites + new
            registry.async_update_entity_options(self.entity_id, "light", light_options)
        if len(already_offered) < len(DEFAULT_FAVORITE_COLORS):
            registry.async_update_entity_options(
                self.entity_id,
                DOMAIN,
                {**options.get(DOMAIN, {}), OFFERED_FAVORITES_KEY: DEFAULT_FAVORITE_COLORS},
            )

    @property
    def effect(self) -> str:
        """Return the running effect."""
        return self.coordinator.effect or EFFECT_OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light, optionally fading over a transition."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)
        effect = kwargs.get(ATTR_EFFECT)
        transition = kwargs.get(ATTR_TRANSITION)

        # Brightness change while an effect runs: restart it at the new level
        if (
            effect is None
            and self.coordinator.effect
            and ATTR_BRIGHTNESS in kwargs
            and set(kwargs) <= {ATTR_BRIGHTNESS, ATTR_TRANSITION}
        ):
            effect = self.coordinator.effect

        try:
            if effect in EFFECTS:
                # Restarting the running effect keeps the speed it was started with
                speed = (
                    self.coordinator.effect_speed_override
                    if effect == self.coordinator.effect
                    else None
                )
                await self.coordinator.async_start_effect(effect, brightness, speed)
                return

            if effect == EFFECT_OFF:
                await self.coordinator.async_stop_effect()

            if ATTR_RGB_COLOR in kwargs:
                mode = MODE_RGB
                color = _rgb_to_device(kwargs[ATTR_RGB_COLOR], brightness)
            elif ATTR_COLOR_TEMP_KELVIN in kwargs:
                mode = MODE_WHITE
                color = _kelvin_to_device(kwargs[ATTR_COLOR_TEMP_KELVIN], brightness)
            elif ATTR_BRIGHTNESS in kwargs or (transition and not self._attr_is_on):
                # Current color at the new brightness (or fading on from off)
                if self._attr_color_mode == ColorMode.RGB:
                    mode = MODE_RGB
                    color = _rgb_to_device(self._attr_rgb_color, brightness)
                else:
                    mode = MODE_WHITE
                    color = _kelvin_to_device(self._attr_color_temp_kelvin, brightness)
            elif not self._attr_is_on:
                await self.coordinator.async_command("power_on")
                return
            else:
                return

            if transition:
                await self.coordinator.async_transition(mode, color, transition)
            else:
                await self.coordinator.async_command(
                    "set_rgb_color" if mode == MODE_RGB else "set_white_color", color
                )

        except COMMAND_ERRORS as err:
            raise HomeAssistantError(f"Failed to turn on The Lampster: {err}") from err

    async def async_start_effect_action(
        self, effect: str, speed: int | None = None, brightness_pct: int | None = None
    ) -> None:
        """Start an effect, optionally at its own speed and brightness (action)."""
        brightness = (
            round(brightness_pct * 255 / 100)
            if brightness_pct is not None
            else self._attr_brightness or 255
        )
        try:
            await self.coordinator.async_start_effect(effect, brightness, speed)
        except COMMAND_ERRORS as err:
            raise HomeAssistantError(f"Failed to start the effect: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light, optionally fading over a transition."""
        try:
            if transition := kwargs.get(ATTR_TRANSITION):
                await self.coordinator.async_transition_off(transition)
            else:
                await self.coordinator.async_command("power_off")

        except COMMAND_ERRORS as err:
            raise HomeAssistantError(f"Failed to turn off The Lampster: {err}") from err
