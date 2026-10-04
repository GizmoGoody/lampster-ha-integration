"""Shared fixtures for The Lampster tests."""
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

ADDRESS = "C0:00:00:01:72:39"

MODE = "01ff5554"
WHITE = "01ff5556"
RGB = "01ff5559"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Load integrations from custom_components in every test."""


class FakeLamp:
    """Behaves like The Lampster over BLE, as observed on real hardware.

    - MODE bit 0x80 is power, 0x20 is RGB; switching mode powers it on
    - POWER_ON (0xC0) is rejected while already on
    - Every change is pushed to subscribers, like the real notifications
    """

    def __init__(self) -> None:
        self.mode = 0x48  # off, white
        self.white = bytes([50, 0])
        self.rgb = bytes([0, 0, 30])
        self.client: FakeBleakClient | None = None
        self.white_writes: list[tuple[int, ...]] = []
        # The real lamp does not report mode writes made over Bluetooth
        self.report_mode_writes = True

    def push(self, key: str, data: bytes) -> None:
        if self.client and self.client.is_connected and key in self.client.subscriptions:
            self.client.subscriptions[key](None, bytearray(data))

    def touch_tap(self) -> None:
        """Simulate a touch-button tap: white on <-> off; color on -> white on."""
        if self.mode & 0x80 and self.mode & 0x20:
            self.mode = 0xC8
        else:
            self.mode = 0xC8 if not self.mode & 0x80 else 0x48
        self.push(MODE, bytes([self.mode]))

    def touch_hold(self, steps: int = 5) -> None:
        """Simulate the start of a touch-button hold: brightness steps."""
        warm, cold = self.white
        for _ in range(steps):
            warm, cold = max(1, warm - 1), max(0, cold - 1)
            self.white = bytes([warm, cold])
            self.push(WHITE, self.white)


class FakeBleakClient:
    """Minimal BleakClientWithServiceCache stand-in backed by a FakeLamp."""

    def __init__(self, lamp: FakeLamp, disconnected_callback: Callable | None) -> None:
        self.lamp = lamp
        self.is_connected = True
        self.disconnected_callback = disconnected_callback
        self.subscriptions: dict[str, Callable] = {}
        self.services = SimpleNamespace(get_characteristic=lambda uuid: True)

    async def clear_cache(self) -> None:
        """Nothing cached."""

    async def write_gatt_char(self, char: str, data: bytes, response: bool = False) -> None:
        key = char[:8]
        if key == MODE:
            value = data[0]
            if value == 0xC0 and self.lamp.mode & 0x80:
                from bleak.exc import BleakError

                raise BleakError("Write Not Permitted")
            self.lamp.mode = value
            # Color writes are not echoed back
            if self.lamp.report_mode_writes:
                self.lamp.push(key, bytes(data))
        elif key == WHITE:
            self.lamp.white = bytes(data)
            self.lamp.white_writes.append(tuple(data))
        elif key == RGB:
            self.lamp.rgb = bytes(data)

    async def read_gatt_char(self, char: str) -> bytes:
        return {
            MODE: bytes([self.lamp.mode]),
            WHITE: self.lamp.white,
            RGB: self.lamp.rgb,
            "00002a26": b"10",
            "00002a27": b"100B\x00",
        }[char[:8]]

    async def start_notify(self, char: str, callback: Callable) -> None:
        self.subscriptions[char[:8]] = callback

    async def disconnect(self) -> None:
        if self.is_connected:
            self.is_connected = False
            if self.disconnected_callback:
                self.disconnected_callback(self)

    def drop(self) -> None:
        """Simulate the connection dropping on its own."""
        self.disconnect_now = True
        self.is_connected = False
        if self.disconnected_callback:
            self.disconnected_callback(self)


@pytest.fixture
def lamp() -> FakeLamp:
    """A fresh fake lamp."""
    return FakeLamp()
