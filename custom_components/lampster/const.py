"""Constants for The Lampster integration."""

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

# Options
CONF_ALWAYS_CONNECTED = "always_connected"
CONF_POLL_INTERVAL = "poll_interval"
CONF_OFF_DISCONNECT_DELAY = "off_disconnect_delay"

DEFAULT_ALWAYS_CONNECTED = False
DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_OFF_DISCONNECT_DELAY = 60  # seconds

# Actions
SERVICE_START_EFFECT = "start_effect"
