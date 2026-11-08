"""Device registry helpers that work across Home Assistant versions."""
from __future__ import annotations

from homeassistant.helpers import device_registry as dr


def find_device(
    registry: dr.DeviceRegistry,
    *,
    identifiers: set[tuple[str, str]] | None = None,
    connections: set[tuple[str, str]] | None = None,
) -> dr.DeviceEntry | None:
    """Return the first device matching identifiers or connections.

    Home Assistant 2026.9 deprecated async_get_device (identifiers are no
    longer unique across config entries) in favor of async_get_devices;
    older versions only have async_get_device.
    """
    if hasattr(registry, "async_get_devices"):
        devices = registry.async_get_devices(identifiers=identifiers, connections=connections)
        return devices[0] if devices else None
    return registry.async_get_device(identifiers=identifiers, connections=connections)
