"""Tests for the connection policy, effects, transitions and repairs."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.lampster import coordinator as coordinator_module
from custom_components.lampster import effects
from custom_components.lampster.const import DOMAIN
from custom_components.lampster.coordinator import (
    FAILURES_BEFORE_ISSUE,
    RECONNECT_DELAY,
    STATE_UPDATE_BATCH_DELAY,
    LampsterCoordinator,
)
from custom_components.lampster.lampster.models import RGBColor, WhiteColor

from .conftest import ADDRESS, FakeBleakClient, FakeLamp

CoordinatorFactory = Callable[..., LampsterCoordinator]


@pytest.fixture
async def make_coordinator(
    hass: HomeAssistant, lamp: FakeLamp
) -> AsyncGenerator[CoordinatorFactory]:
    """Build coordinators wired to the fake lamp; stop them afterwards."""
    created: list[LampsterCoordinator] = []

    async def fake_establish_connection(*args, disconnected_callback=None, **kwargs):
        client = FakeBleakClient(lamp, disconnected_callback)
        lamp.client = client
        return client

    service_info = SimpleNamespace(name="Lampster", rssi=-60, source="AA:BB:CC:DD:EE:FF")
    with (
        patch(
            "homeassistant.components.bluetooth.update_coordinator.async_address_present",
            return_value=True,
        ),
        patch.object(
            coordinator_module.bluetooth,
            "async_ble_device_from_address",
            return_value=SimpleNamespace(address=ADDRESS),
        ),
        patch.object(
            coordinator_module.bluetooth, "async_last_service_info", return_value=service_info
        ),
        patch.object(coordinator_module, "establish_connection", fake_establish_connection),
    ):

        def factory(**options) -> LampsterCoordinator:
            settings = {
                "always_connected": False,
                "poll_interval": 30,
                "off_disconnect_delay": 60,
            } | options
            coordinator = LampsterCoordinator(hass, ADDRESS, **settings)
            created.append(coordinator)
            return coordinator

        yield factory

        for coordinator in created:
            await coordinator.async_stop()


def fire(hass: HomeAssistant, seconds: float) -> None:
    """Move time forward so scheduled callbacks run."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))


async def test_check_while_off_disconnects(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A check that finds the lamp off disconnects straight away."""
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    assert not coordinator.connected
    assert coordinator.data.is_on is False
    assert coordinator.connection_status == "disconnected"


async def test_check_finds_on_stays_connected(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A check that finds the lamp on (touch button) stays connected."""
    lamp.mode = 0xC8
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    assert coordinator.connected
    assert coordinator.connection_status == "connected"


async def test_touch_off_standby_then_disconnect(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Turning off by touch: Standby for the hang-on time, then disconnect."""
    lamp.mode = 0xC8
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")

    lamp.touch_tap()
    fire(hass, STATE_UPDATE_BATCH_DELAY + 0.1)
    await hass.async_block_till_done()
    assert coordinator.data.is_on is False
    assert coordinator.connection_status == "standby"

    fire(hass, 61)
    await hass.async_block_till_done()
    assert not coordinator.connected
    assert coordinator.connection_status == "disconnected"


async def test_touch_on_during_standby_cancels_disconnect(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Turning back on within the hang-on time keeps the connection."""
    lamp.mode = 0xC8
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    lamp.touch_tap()
    lamp.touch_tap()
    fire(hass, 61)
    await hass.async_block_till_done()
    assert coordinator.connected
    assert coordinator.connection_status == "connected"


async def test_always_connected_stays_while_off(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """With the connection maintained, it stays up while the lamp is off."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator._async_try_connect("check interval")
    assert coordinator.connected
    assert coordinator.connection_status == "connected"


async def test_command_connects_and_turns_on(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A command from off connects, turns the lamp on and stays connected."""
    coordinator = make_coordinator()
    await coordinator.async_command("set_rgb_color", RGBColor(60, 0, 0))
    assert coordinator.connected
    assert coordinator.data.is_on
    assert coordinator.data.mode == "rgb"
    assert lamp.mode == 0xA8


async def test_rapid_commands_keep_latest(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Commands queued behind one in flight collapse to the latest."""
    coordinator = make_coordinator()
    await coordinator.async_command("set_rgb_color", RGBColor(10, 0, 0))
    await asyncio.gather(
        *(coordinator.async_command("set_rgb_color", RGBColor(i, 5, 0)) for i in range(10))
    )
    assert coordinator.data.rgb_color == RGBColor(9, 5, 0)


async def test_drop_reconnects(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """An unexpected drop while on schedules a reconnect."""
    lamp.mode = 0xC8
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    lamp.client.drop()
    assert coordinator.connection_status == "reconnecting"

    fire(hass, RECONNECT_DELAY + 1)
    await hass.async_block_till_done()
    assert coordinator.connected


async def test_transition_ramps_to_target(
    hass: HomeAssistant,
    lamp: FakeLamp,
    make_coordinator: CoordinatorFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transition from off ramps up and ends on the target."""
    monkeypatch.setattr(effects, "TRANSITION_MIN_STEP", 0.001)
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    lamp.white_writes.clear()

    await coordinator.async_transition("white", WhiteColor(40, 10), 0.05)
    assert coordinator.data.white_color == WhiteColor(40, 10)  # shown right away
    await coordinator._task
    ramp = [write for write in lamp.white_writes if write != (0, 0)]
    assert len(ramp) >= 10
    assert ramp[-1] == (40, 10)
    assert coordinator.data.is_on


async def test_transition_off_fades_then_powers_off(
    hass: HomeAssistant,
    lamp: FakeLamp,
    make_coordinator: CoordinatorFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fading off ends with the lamp off."""
    monkeypatch.setattr(effects, "TRANSITION_MIN_STEP", 0.001)
    lamp.mode = 0xC8
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    await coordinator.async_transition_off(0.05)
    await coordinator._task
    assert lamp.mode & 0x80 == 0
    assert coordinator.data.is_on is False


async def test_effect_stopped_by_command(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Any command stops a running effect."""
    coordinator = make_coordinator()
    await coordinator.async_start_effect("fireplace", 200)
    assert coordinator.effect == "fireplace"
    await coordinator.async_command("set_white_color", WhiteColor(30, 0))
    assert coordinator.effect is None
    assert coordinator.data.mode == "white"


async def test_touch_off_during_effect_stays_off(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Turning off with the touch button stops the effect and keeps it off."""
    coordinator = make_coordinator()
    await coordinator.async_start_effect("fireplace", 200)
    for _ in range(40):
        if coordinator._task_engaged:
            break
        await asyncio.sleep(0.05)
    assert coordinator._task_engaged

    lamp.touch_tap()  # color on -> white on (the lamp's own behavior)
    await asyncio.sleep(3)
    await hass.async_block_till_done()
    assert lamp.mode & 0x80 == 0
    assert coordinator.effect is None
    assert coordinator.data.is_on is False


async def test_touch_tap_during_effect_started_in_color_mode(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """An effect started while already in color mode still stops on a tap.

    No mode report arrives when the effect starts, since the mode is unchanged.
    """
    coordinator = make_coordinator()
    await coordinator.async_command("set_rgb_color", RGBColor(60, 0, 0))
    await coordinator.async_start_effect("fireplace", 200)
    await asyncio.sleep(0.5)
    assert coordinator._task_engaged

    lamp.touch_tap()  # color on -> white on
    await asyncio.sleep(3)
    await hass.async_block_till_done()
    assert coordinator.effect is None
    assert lamp.mode & 0x80 == 0


async def test_touch_hold_during_effect_stays_on(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Holding the touch button during an effect dims instead of turning off."""
    coordinator = make_coordinator()
    await coordinator.async_start_effect("fireplace", 200)
    for _ in range(40):
        if coordinator._task_engaged:
            break
        await asyncio.sleep(0.05)

    lamp.touch_tap()
    lamp.touch_hold()
    await asyncio.sleep(3)
    await hass.async_block_till_done()
    assert lamp.mode & 0x80
    assert coordinator.effect is None
    assert coordinator.data.mode == "white"


def event_log(coordinator: LampsterCoordinator) -> list[str]:
    """Return the diagnostics events, oldest first."""
    return [event["event"] for event in coordinator.diagnostics()["recent_events"]]


async def test_diagnostics_record_commands_and_touch(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Commands, taps and holds appear in the diagnostics events."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_white_color", WhiteColor(40, 10))
    assert "Command set_white_color White(warm=40, cold=10)" in event_log(coordinator)

    lamp.touch_hold(steps=5)
    lamp.touch_hold(steps=5)
    # One event for the whole hold, once it has ended
    assert not any(event.startswith("Touch button hold") for event in event_log(coordinator))
    fire(hass, 2)
    await hass.async_block_till_done()
    holds = [event for event in event_log(coordinator) if event.startswith("Touch button hold")]
    assert holds == ["Touch button hold: White(warm=40, cold=10) to White(warm=30, cold=0)"]

    lamp.touch_tap()
    assert event_log(coordinator)[-1] == "Touch button: State(off)"


async def test_repair_issue_raised_and_cleared(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Repeated failures raise a repair issue; a success clears it."""
    coordinator = make_coordinator()
    issue_id = f"cannot_connect_{ADDRESS}"

    async def fail(*args, **kwargs):
        raise TimeoutError("timed out")

    with patch.object(coordinator_module, "establish_connection", fail):
        for _ in range(FAILURES_BEFORE_ISSUE):
            await coordinator._async_try_connect("check interval")
    assert coordinator.connection_status == "failed"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    await coordinator._async_try_connect("check interval")
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    diagnostics = coordinator.diagnostics()
    assert diagnostics["consecutive_failures"] == 0
    assert diagnostics["recent_events"]
