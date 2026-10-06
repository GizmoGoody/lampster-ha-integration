"""BLE constants for The Lampster.

Protocol documentation: https://github.com/Noki/the-lampster
All characteristic UUIDs and command values are based on Noki's reverse engineering work.
"""

# BLE Service and Characteristic UUIDs
# Discovered via characteristic enumeration on actual device
# Based on handles from Noki's documentation:
#   0x0021 (mode), 0x0025 (white), 0x002a (RGB)
SERVICE_UUID = "01ff5553-ba5e-f4ee-5ca1-eb1e5e4b1ce0"
CHAR_MODE = "01ff5554-ba5e-f4ee-5ca1-eb1e5e4b1ce0"    # Handle 0x0020 (≈ 0x0021)
CHAR_WHITE = "01ff5556-ba5e-f4ee-5ca1-eb1e5e4b1ce0"  # Handle 0x0024 (≈ 0x0025)
CHAR_RGB = "01ff5559-ba5e-f4ee-5ca1-eb1e5e4b1ce0"    # Handle 0x0029 (≈ 0x002a)

# Standard Bluetooth Temperature characteristic (sint16, 0.01 °C). The device
# notifies it about every 5 seconds while connected; appears to be internal.
CHAR_TEMPERATURE = "00002a6e-0000-1000-8000-00805f9b34fb"

# Standard Device Information characteristics (UTF-8 strings)
CHAR_FIRMWARE_REVISION = "00002a26-0000-1000-8000-00805f9b34fb"  # "10"
CHAR_HARDWARE_REVISION = "00002a27-0000-1000-8000-00805f9b34fb"  # "100B"

# Mode control commands (written to CHAR_MODE)
MODE_POWER_ON = 0xC0
MODE_POWER_OFF = 0x40
MODE_RGB = 0xA8
MODE_WHITE = 0xC8
MODE_OFF = 0x28
# Off, keeping the mode, as the touch button turns it off
MODE_RGB_OFF = 0x28
MODE_WHITE_OFF = 0x48

# Bits observed in the MODE value read back from the device (e.g. 0x48 is
# white mode while off, 0x28 is RGB mode while off)
MODE_BIT_POWER = 0x80
MODE_BIT_RGB = 0x20

# The device rejects mode writes (GATT "Write Not Permitted") while it is
# still processing a previous mode change; rejected writes are retried
MODE_WRITE_ATTEMPTS = 3
MODE_WRITE_RETRY_DELAY = 0.5

# Value ranges for color control
MIN_VALUE = 0x00  # 0%
MAX_VALUE = 0x64  # 100 in decimal = 100%

# Device identification
DEVICE_NAME_PREFIX = "Lamp"  # Devices typically have "Lamp" in their name
