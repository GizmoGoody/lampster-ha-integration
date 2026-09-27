"""The Lampster - Python library for controlling The Lampster RGB Bluetooth lamp.

Based on protocol documentation from: https://github.com/Noki/the-lampster
"""

from .client import LampsterClient
from .models import RGBColor, WhiteColor, LampState
from .exceptions import (
    LampsterException,
    ConnectionError,
    CommandError,
    DiscoveryError,
)

__version__ = "1.1.0"

__all__ = [
    "LampsterClient",
    "RGBColor",
    "WhiteColor",
    "LampState",
    "LampsterException",
    "ConnectionError",
    "CommandError",
    "DiscoveryError",
]
