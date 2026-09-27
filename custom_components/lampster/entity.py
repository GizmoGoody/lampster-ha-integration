"""Base entity for The Lampster integration."""
from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from .const import DOMAIN
from .coordinator import LampsterCoordinator


class LampsterEntity(PassiveBluetoothCoordinatorEntity[LampsterCoordinator]):
    """Base class for Lampster entities, sharing one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LampsterCoordinator, key: str | None = None) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            coordinator.address if key is None else f"{coordinator.address}_{key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name="The Lampster",
            manufacturer="The Lampster",
            model="LA-2017B",
        )
