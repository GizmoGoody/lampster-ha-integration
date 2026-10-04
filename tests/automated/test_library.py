"""Tests for the bundled lampster BLE library."""
from __future__ import annotations

import pytest

from custom_components.lampster.lampster import client as client_module
from custom_components.lampster.lampster.client import LampsterClient, _parse_mode
from custom_components.lampster.lampster.exceptions import CommandError
from custom_components.lampster.lampster.models import LampState, RGBColor, WhiteColor

from .conftest import MODE, WHITE, FakeBleakClient, FakeLamp


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0xC8, (True, "white")),
        (0xC0, (True, "white")),
        (0xA8, (True, "rgb")),
        (0x48, (False, "off")),
        (0x40, (False, "off")),
        (0x28, (False, "off")),
    ],
)
def test_parse_mode(value: int, expected: tuple[bool, str]) -> None:
    """MODE is a bit field: 0x80 power, 0x20 RGB."""
    assert _parse_mode(value) == expected


def _client(lamp: FakeLamp) -> LampsterClient:
    client = LampsterClient("AA")
    client._client = lamp.client = FakeBleakClient(lamp, None)
    return client


async def test_read_state(lamp: FakeLamp) -> None:
    """Values read from the device become a LampState."""
    lamp.mode = 0xA8
    lamp.rgb = bytes([10, 20, 30])
    state = await _client(lamp).read_state()
    assert state == LampState(True, "rgb", RGBColor(10, 20, 30), WhiteColor(50, 0))


async def test_set_white_from_off_powers_on_once(lamp: FakeLamp) -> None:
    """Switching to white mode powers it on; no rejected POWER_ON is sent."""
    client = _client(lamp)
    await client.refresh_state()
    await client.set_white_color(WhiteColor(30, 10))
    assert lamp.mode == 0xC8
    assert lamp.white == bytes([30, 10])
    assert client.state.is_on


async def test_same_mode_color_change_is_single_write(lamp: FakeLamp) -> None:
    """Changing color within the current mode writes only the color."""
    lamp.mode = 0xC8
    client = _client(lamp)
    await client.refresh_state()
    lamp.white_writes.clear()
    await client.set_white_color(WhiteColor(20, 20))
    assert lamp.white_writes == [(20, 20)]


async def test_mode_write_retried_when_rejected(
    lamp: FakeLamp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected mode write is retried."""
    monkeypatch.setattr(client_module, "MODE_WRITE_RETRY_DELAY", 0)
    client = _client(lamp)
    fake = client._client
    original = fake.write_gatt_char
    failures = {"left": 1}

    async def flaky(char: str, data: bytes, response: bool = False) -> None:
        if char.startswith(MODE) and failures["left"]:
            failures["left"] -= 1
            raise RuntimeError("Write Not Permitted")
        await original(char, data, response)

    fake.write_gatt_char = flaky
    await client._write_mode(0xC8)
    assert lamp.mode == 0xC8


async def test_mode_write_gives_up(lamp: FakeLamp, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mode write that keeps failing raises CommandError."""
    monkeypatch.setattr(client_module, "MODE_WRITE_RETRY_DELAY", 0)
    client = _client(lamp)

    async def always_fails(char: str, data: bytes, response: bool = False) -> None:
        raise RuntimeError("Write Not Permitted")

    client._client.write_gatt_char = always_fails
    with pytest.raises(CommandError):
        await client._write_mode(0xA8)


async def test_power_off_keeps_mode_and_levels(lamp: FakeLamp) -> None:
    """Power off clears only the power bit, like the touch button.

    The levels are kept, so a tap brings back the same mode and levels.
    """
    for on, off in ((0xC8, 0x48), (0xA8, 0x28)):
        lamp.mode = on
        lamp.white = bytes([35, 2])
        client = _client(lamp)
        await client.refresh_state()
        await client.power_off()
        assert lamp.mode == off
        assert lamp.white == bytes([35, 2])
        assert not client.state.is_on


async def test_power_off_falls_back_to_zeroed(
    lamp: FakeLamp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the lamp rejects the button-style off, the zeroing sequence is used."""
    monkeypatch.setattr(client_module, "MODE_WRITE_RETRY_DELAY", 0)
    lamp.mode = 0xA8
    client = _client(lamp)
    await client.refresh_state()
    fake = client._client
    original = fake.write_gatt_char

    async def rejects_28(char: str, data: bytes, response: bool = False) -> None:
        if char.startswith(MODE) and data[0] == 0x28:
            raise RuntimeError("Write Not Permitted")
        await original(char, data, response)

    fake.write_gatt_char = rejects_28
    await client.power_off()
    assert lamp.mode == 0x40
    assert lamp.white == bytes([0, 0])
    assert not client.state.is_on


async def test_notifications_update_state(lamp: FakeLamp) -> None:
    """Pushed MODE/WHITE changes update the state and call back."""
    lamp.mode = 0xC8
    client = _client(lamp)
    await client.refresh_state()
    seen: list[LampState] = []
    temperatures: list[float] = []
    await client.start_notifications(seen.append, temperatures.append)

    lamp.touch_tap()
    assert seen[-1].is_on is False
    lamp.push(WHITE, bytes([33, 3]))
    assert client.state.white_color == WhiteColor(33, 3)


async def test_read_versions(lamp: FakeLamp) -> None:
    """Firmware and hardware revisions are decoded as text."""
    assert await _client(lamp).read_versions() == {"firmware": "10", "hardware": "100B"}
