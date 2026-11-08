"""Diagnostic sensors for The Lampster integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CONNECTION_STATUSES, LampsterCoordinator
from .entity import LampsterEntity
from .registry import find_device


def _bluetooth_source(coordinator: LampsterCoordinator) -> str | None:
    """Return the name of the adapter or proxy that last heard the lamp.

    Uses the device name as shown in Home Assistant (including any name the
    user gave it), falling back to the scanner's own name.
    """
    if not (service_info := coordinator.last_service_info):
        return None
    source = service_info.source
    registry = dr.async_get(coordinator.hass)
    for connection in (
        (dr.CONNECTION_BLUETOOTH, source.upper()),
        (dr.CONNECTION_BLUETOOTH, source.lower()),
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(source)),
    ):
        if device := find_device(registry, connections={connection}):
            return device.name_by_user or device.name
    scanner = bluetooth.async_scanner_by_source(coordinator.hass, source)
    return scanner.name if scanner else source


@dataclass(frozen=True, kw_only=True)
class LampsterSensorEntityDescription(SensorEntityDescription):
    """Describes a Lampster diagnostic sensor."""

    value_fn: Callable[[LampsterCoordinator], str | int | float | None]
    # Only meaningful while connected (the lamp reports it over the connection)
    requires_connection: bool = False
    # Entity ID becomes sensor.lampster_<object_id> (defaults to key)
    object_id: str | None = None


SENSORS: tuple[LampsterSensorEntityDescription, ...] = (
    LampsterSensorEntityDescription(
        key="connection",
        translation_key="connection",
        device_class=SensorDeviceClass.ENUM,
        options=CONNECTION_STATUSES,
        value_fn=lambda c: c.connection_status,
    ),
    LampsterSensorEntityDescription(
        key="temperature",
        object_id="internal_temperature",
        entity_registry_enabled_default=False,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        requires_connection=True,
        value_fn=lambda c: c.temperature,
    ),
    LampsterSensorEntityDescription(
        key="rssi",
        object_id="signal_strength",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.last_service_info.rssi if c.last_service_info else None,
    ),
    LampsterSensorEntityDescription(
        # Typically 1-3 s, so reported in seconds
        key="connect_time",
        entity_registry_enabled_default=False,
        translation_key="connect_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: (
            round(c.last_connect_ms / 1000, 1) if c.last_connect_ms is not None else None
        ),
    ),
    LampsterSensorEntityDescription(
        key="command_time",
        entity_registry_enabled_default=False,
        translation_key="command_time",
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.last_command_ms,
    ),
    LampsterSensorEntityDescription(
        key="bluetooth_source",
        object_id="bluetooth_uplink",
        translation_key="bluetooth_source",
        value_fn=_bluetooth_source,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up The Lampster sensors from a config entry."""
    coordinator: LampsterCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LampsterSensor(coordinator, description) for description in SENSORS
    )


class LampsterSensor(LampsterEntity, SensorEntity):
    """Diagnostic sensor for connection health and responsiveness."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: LampsterSensorEntityDescription

    def __init__(
        self,
        coordinator: LampsterCoordinator,
        description: LampsterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # Keep IDs short and stable regardless of the device name
        self.entity_id = f"sensor.lampster_{description.object_id or description.key}"

    @property
    def available(self) -> bool:
        """Return True if the value can currently be known."""
        if self.entity_description.requires_connection:
            return super().available and self.coordinator.connected
        return super().available

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
