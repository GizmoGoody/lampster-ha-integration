"""Constants for The Lampster integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Domain
DOMAIN = "lampster"

# Config flow
CONF_DEVICE = "device"

# Default values
DEFAULT_NAME = "Lampster"

# Attributes
ATTR_DEVICE_ADDRESS = "device_address"
ATTR_MODEL = "model"
ATTR_MANUFACTURER = "manufacturer"

# Connection option: one of two modes
CONF_CONNECTION_MODE = "connection_mode"
# Connected while The Lampster is on; checks it while off and disconnected
CONNECTION_PERIODIC = "periodic"
# Connected at all times
CONNECTION_CONSTANT = "constant"
CONNECTION_MODES = [CONNECTION_PERIODIC, CONNECTION_CONSTANT]

# Periodic connection timing (seconds)
CONF_RECONNECT_INTERVAL = "reconnect_interval"
DEFAULT_RECONNECT_INTERVAL = 30
CONF_DISCONNECT_AFTER = "disconnect_after"
DEFAULT_DISCONNECT_AFTER = 60


def get_connection_mode(options: Mapping[str, Any]) -> str:
    """Return the chosen connection mode, or the default if none is set."""
    mode = options.get(CONF_CONNECTION_MODE)
    if mode in CONNECTION_MODES:
        return mode
    return CONNECTION_PERIODIC
