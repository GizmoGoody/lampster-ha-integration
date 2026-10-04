"""BLE client for controlling The Lampster.

Protocol based on: https://github.com/Noki/the-lampster
"""

import asyncio
from collections.abc import Callable
import dataclasses
import logging
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .constants import (
    CHAR_FIRMWARE_REVISION,
    CHAR_HARDWARE_REVISION,
    CHAR_MODE,
    CHAR_RGB,
    CHAR_TEMPERATURE,
    CHAR_WHITE,
    DEVICE_NAME_PREFIX,
    MODE_BIT_POWER,
    MODE_BIT_RGB,
    MODE_WRITE_ATTEMPTS,
    MODE_WRITE_RETRY_DELAY,
    MODE_POWER_OFF,
    MODE_POWER_ON,
    MODE_RGB,
    MODE_WHITE,
)
from .exceptions import CommandError, ConnectionError, DiscoveryError
from .models import LampState, RGBColor, WhiteColor

_LOGGER = logging.getLogger(__name__)


def _parse_mode(value: int) -> tuple[bool, str]:
    """Parse a MODE byte: bit 0x80 is power, bit 0x20 is RGB (otherwise white)."""
    is_on = bool(value & MODE_BIT_POWER)
    if not is_on:
        return False, "off"
    return True, "rgb" if value & MODE_BIT_RGB else "white"


def _parse_rgb(data: bytes) -> Optional[RGBColor]:
    """Parse RGB characteristic bytes (r, g, b; 0-100 each)."""
    if len(data) < 3:
        return None
    return RGBColor(*(min(v, 100) for v in data[:3]))


def _parse_white(data: bytes) -> Optional[WhiteColor]:
    """Parse WHITE characteristic bytes (warm, cold; 0-100 each)."""
    if len(data) < 2:
        return None
    return WhiteColor(*(min(v, 100) for v in data[:2]))


class LampsterClient:
    """Client for controlling The Lampster via Bluetooth LE."""

    def __init__(self, address: str):
        """Initialize client with device address.

        Args:
            address: Bluetooth MAC address of the device (e.g., "XX:XX:XX:XX:XX:XX")
        """
        self.address = address
        self._client: Optional[BleakClient] = None
        self._state = LampState(is_on=False, mode="off")

    @staticmethod
    async def discover(timeout: float = 5.0, stop_on_first: bool = True) -> list[BLEDevice]:
        """Discover Lampster devices nearby.

        Uses early-exit strategy to stop scanning as soon as a device is found.

        Args:
            timeout: Scan timeout in seconds (default: 5, reduced from 10)
            stop_on_first: Stop scanning after finding first device (default: True for speed)

        Returns:
            List of discovered BLE devices matching Lampster pattern

        Raises:
            DiscoveryError: If no devices are found
        """
        _LOGGER.info("Scanning for Lampster devices...")

        if stop_on_first:
            # Early exit: stop as soon as we find one matching device
            lampster_devices = []
            seen_addresses = set()

            def detection_callback(device, advertisement_data):
                # Check if device name contains "Lamp" and not already found
                if device.name and DEVICE_NAME_PREFIX in device.name:
                    if device.address not in seen_addresses:
                        seen_addresses.add(device.address)
                        lampster_devices.append(device)
                        return True  # Stop scanning
                return False

            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()

            # Wait up to timeout or until device found
            start_time = asyncio.get_event_loop().time()
            while not lampster_devices and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(0.1)

            await scanner.stop()
        else:
            # Traditional scan: wait for full timeout
            devices = await BleakScanner.discover(timeout=timeout)
            lampster_devices = [
                d for d in devices if d.name and DEVICE_NAME_PREFIX in d.name
            ]

        if not lampster_devices:
            raise DiscoveryError("No Lampster devices found")

        _LOGGER.info(f"Found {len(lampster_devices)} Lampster device(s)")
        return lampster_devices

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect to the Lampster device.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            self._client = BleakClient(self.address, timeout=timeout)
            await self._client.connect()
            _LOGGER.info(f"Connected to Lampster at {self.address}")
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self):
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
            _LOGGER.info("Disconnected from Lampster")

    async def _write_mode(self, mode: int):
        """Write to mode characteristic.

        Args:
            mode: Mode command byte

        Raises:
            ConnectionError: If not connected
            CommandError: If write fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        last_error: Exception | None = None
        for attempt in range(1, MODE_WRITE_ATTEMPTS + 1):
            try:
                # Use write-with-response for mode switching (per Noki's char-write-req)
                await self._client.write_gatt_char(CHAR_MODE, bytes([mode]), response=True)
                _LOGGER.debug(f"Wrote mode: 0x{mode:02x}")
                return
            except Exception as e:
                last_error = e

            # The device also rejects writing the mode it is already in
            try:
                if await self._read_mode() == mode:
                    _LOGGER.debug(f"Mode already 0x{mode:02x}")
                    return
            except Exception:
                pass

            _LOGGER.debug(
                f"Mode write 0x{mode:02x} rejected (attempt {attempt}): {last_error}"
            )
            await asyncio.sleep(MODE_WRITE_RETRY_DELAY)

        raise CommandError(f"Failed to write mode: {last_error}") from last_error

    async def _read_mode(self) -> int:
        """Read the current mode byte from the device."""
        return (await self._client.read_gatt_char(CHAR_MODE))[0]

    async def _ensure_on(self):
        """Power on if still off.

        Switching to RGB or white mode normally powers the lamp on by itself,
        and the device rejects POWER_ON while already on, so check first.
        """
        if not await self._read_mode() & MODE_BIT_POWER:
            await self._write_mode(MODE_POWER_ON)
            await asyncio.sleep(0.4)

    async def power_on(self):
        """Turn the lamp on the way its touch button does.

        Sets the power bit of the current mode, so the lamp comes back in the
        mode and at the levels it was turned off with, then reads them. If
        that would leave it dark (the levels are zero), turns it on in warm
        white at 50% instead.

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        try:
            mode = await self._read_mode()
            if not mode & MODE_BIT_POWER:
                await self._write_mode(mode | MODE_BIT_POWER)
            state = await self.read_state()
            color = state.rgb_color if state.mode == "rgb" else state.white_color
            if state.is_on and color and any(color.to_bytes()):
                self._state = state
                _LOGGER.info(f"Lamp powered on as it was: {state}")
                return
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Failed to power on: {e}") from e
        await self._power_on_default()

    async def _power_on_default(self):
        """Turn the lamp on in warm white at 50%.

        Goes through set_white_color, which only sends POWER_ON while the
        lamp is still off (the lamp rejects it while on).
        """
        await self.set_white_color(WhiteColor(50, 0))
        _LOGGER.info("Lamp powered on (warm white 50%)")

    async def power_off(self):
        """Turn the lamp off the way its touch button does.

        The touch button clears the power bit and keeps the mode (0x48 from
        white, 0x28 from color), so the next tap brings back the same mode
        and levels. If the lamp does not accept that, fall back to switching
        to white, zeroing the levels and powering off, which always works
        but leaves the levels at zero for the next tap.

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        try:
            mode = await self._read_mode()
            if mode & MODE_BIT_POWER:
                try:
                    await self._write_mode(mode & ~MODE_BIT_POWER)
                    turned_off = not await self._read_mode() & MODE_BIT_POWER
                except CommandError as e:
                    _LOGGER.debug(f"Power off keeping the mode failed: {e}")
                    turned_off = False
                if not turned_off:
                    await self._power_off_zeroed()
            self._state.is_on = False
            self._state.mode = "off"
            _LOGGER.info("Lamp powered off")
        except Exception as e:
            raise CommandError(f"Failed to power off: {e}") from e

    async def _power_off_zeroed(self):
        """Power off by switching to white and zeroing the levels first."""
        _LOGGER.debug("Powering off with zeroed levels")
        try:
            # Switch to white mode first (required for power off to work from RGB mode)
            await self._write_mode(MODE_WHITE)
            await asyncio.sleep(0.4)  # Device needs time to process mode change

            # Set WHITE and RGB to zero AFTER mode switch
            await self._client.write_gatt_char(CHAR_WHITE, bytes([0, 0]), response=False)
            await asyncio.sleep(0.1)
            await self._client.write_gatt_char(CHAR_RGB, bytes([0, 0, 0]), response=False)
            await asyncio.sleep(0.4)  # Let colors zero out

            # Now send power off
            await self._write_mode(MODE_POWER_OFF)
            self._state.white_color = WhiteColor(0, 0)
            self._state.rgb_color = RGBColor(0, 0, 0)
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Failed to power off: {e}") from e

    async def set_rgb_mode(self):
        """Switch to RGB mode.

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        await self._write_mode(MODE_RGB)
        self._state.mode = "rgb"
        _LOGGER.debug("Switched to RGB mode")

    async def set_white_mode(self):
        """Switch to white mode.

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        await self._write_mode(MODE_WHITE)
        self._state.mode = "white"
        _LOGGER.debug("Switched to white mode")

    async def set_rgb_color(self, color: RGBColor):
        """Set RGB color (automatically switches to RGB mode).

        Args:
            color: RGBColor object with values 0-100

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        try:
            # Already on in rgb mode: a single color write is enough. This
            # keeps rapid changes (e.g. dragging a color picker) responsive.
            if self._state.is_on and self._state.mode == "rgb":
                await self._client.write_gatt_char(CHAR_RGB, color.to_bytes(), response=False)
                self._state.rgb_color = color
                _LOGGER.debug(f"Updated rgb color: {color}")
                return

            # Write color data FIRST (device may need this before mode switch)
            await self._client.write_gatt_char(CHAR_RGB, color.to_bytes(), response=False)
            await asyncio.sleep(0.2)  # Let color data settle

            # Switch to RGB mode
            await self.set_rgb_mode()
            await asyncio.sleep(0.4)  # Device needs time to process mode change

            await self._ensure_on()

            # Switching mode can restore the device's remembered color for
            # that mode, overriding the write above; write it again
            await self._client.write_gatt_char(CHAR_RGB, color.to_bytes(), response=False)

            _LOGGER.info(f"Set RGB color: {color}")

            self._state.is_on = True
            self._state.rgb_color = color
        except Exception as e:
            raise CommandError(f"Failed to set RGB color: {e}") from e

    async def set_white_color(self, color: WhiteColor):
        """Set white color (automatically switches to white mode).

        Args:
            color: WhiteColor object with warm/cold values 0-100

        Raises:
            ConnectionError: If not connected
            CommandError: If command fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        try:
            # Already on in white mode: a single color write is enough. This
            # keeps rapid changes (e.g. dragging a color picker) responsive.
            if self._state.is_on and self._state.mode == "white":
                await self._client.write_gatt_char(CHAR_WHITE, color.to_bytes(), response=False)
                self._state.white_color = color
                _LOGGER.debug(f"Updated white color: {color}")
                return

            # Write color data FIRST (device may need this before mode switch)
            await self._client.write_gatt_char(CHAR_WHITE, color.to_bytes(), response=False)
            await asyncio.sleep(0.2)  # Let color data settle

            # Switch to white mode
            await self.set_white_mode()
            await asyncio.sleep(0.4)  # Device needs time to process mode change

            await self._ensure_on()

            # Switching mode can restore the device's remembered color for
            # that mode, overriding the write above; write it again
            await self._client.write_gatt_char(CHAR_WHITE, color.to_bytes(), response=False)

            _LOGGER.info(f"Set white color: {color}")

            self._state.is_on = True
            self._state.white_color = color
        except Exception as e:
            raise CommandError(f"Failed to set white color: {e}") from e

    async def read_state(self) -> LampState:
        """Read current state from device.

        Reads actual values from device characteristics and returns parsed state.
        Useful for verification, reconnection sync, or detecting manual changes.

        Returns:
            LampState with current device values

        Raises:
            ConnectionError: If not connected
            CommandError: If read fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        try:
            # Read all characteristics
            mode_bytes = await self._client.read_gatt_char(CHAR_MODE)
            rgb_bytes = await self._client.read_gatt_char(CHAR_RGB)
            white_bytes = await self._client.read_gatt_char(CHAR_WHITE)

            is_on, mode = _parse_mode(mode_bytes[0])
            state = LampState(
                is_on=is_on,
                mode=mode,
                rgb_color=_parse_rgb(rgb_bytes),
                white_color=_parse_white(white_bytes),
            )

            _LOGGER.debug(f"Read state from device: {state}")
            return state

        except Exception as e:
            raise CommandError(f"Failed to read state: {e}") from e

    async def refresh_state(self):
        """Refresh local state by reading from device.

        Updates internal state tracking with actual device values.
        Useful after reconnection or to detect manual button presses.

        Raises:
            ConnectionError: If not connected
            CommandError: If read fails
        """
        self._state = await self.read_state()
        _LOGGER.info("State refreshed from device")

    async def read_versions(self) -> dict[str, str]:
        """Read the firmware and hardware revisions the device reports.

        Returns:
            Dict with "firmware" and/or "hardware" keys; a value that cannot
            be read is left out

        Raises:
            ConnectionError: If not connected
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        versions: dict[str, str] = {}
        for key, char in (
            ("firmware", CHAR_FIRMWARE_REVISION),
            ("hardware", CHAR_HARDWARE_REVISION),
        ):
            try:
                raw = await self._client.read_gatt_char(char)
            except Exception as e:
                _LOGGER.debug(f"Could not read {key} revision: {e}")
                continue
            if value := bytes(raw).decode("utf-8", errors="ignore").strip("\x00 "):
                versions[key] = value
        return versions

    async def start_notifications(
        self,
        on_state: Callable[[LampState], None],
        on_temperature: Optional[Callable[[float], None]] = None,
    ):
        """Subscribe to state changes pushed by the device.

        The device notifies MODE, WHITE and RGB changes, including those made
        with its touch button, so local state stays current without polling.

        Args:
            on_state: Called with the updated state after each change
            on_temperature: Called with the internal temperature (°C), which
                the device sends about every 5 seconds

        Raises:
            ConnectionError: If not connected
            CommandError: If subscribing fails
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to device")

        def handle_mode(_char, data: bytearray) -> None:
            if data:
                is_on, mode = _parse_mode(data[0])
                self._state = dataclasses.replace(self._state, is_on=is_on, mode=mode)
                on_state(self._state)

        def handle_rgb(_char, data: bytearray) -> None:
            if color := _parse_rgb(data):
                self._state = dataclasses.replace(self._state, rgb_color=color)
                on_state(self._state)

        def handle_white(_char, data: bytearray) -> None:
            if color := _parse_white(data):
                self._state = dataclasses.replace(self._state, white_color=color)
                on_state(self._state)

        try:
            await self._client.start_notify(CHAR_MODE, handle_mode)
            await self._client.start_notify(CHAR_RGB, handle_rgb)
            await self._client.start_notify(CHAR_WHITE, handle_white)
        except Exception as e:
            raise CommandError(f"Failed to subscribe to state changes: {e}") from e

        if on_temperature is None:
            return

        def handle_temperature(_char, data: bytearray) -> None:
            if len(data) >= 2:
                on_temperature(int.from_bytes(data[:2], "little", signed=True) / 100)

        try:
            await self._client.start_notify(CHAR_TEMPERATURE, handle_temperature)
        except Exception as e:
            # Not essential for control; keep going without it
            _LOGGER.debug(f"Temperature notifications unavailable: {e}")

    @property
    def state(self) -> LampState:
        """Get current lamp state (locally tracked).

        Returns local state that may be out of sync with device.
        Use read_state() or refresh_state() to get actual device values.
        """
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected to device."""
        return self._client is not None and self._client.is_connected
