"""Tests for the connection policy, effects, transitions and repairs."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.lampster import coordinator as coordinator_module
from custom_components.lampster import effects
from custom_components.lampster.const import DOMAIN
from custom_components.lampster.coordinator import (
    FAILURES_BEFORE_ISSUE,
    NOT_HEARD_ISSUE_AFTER,
    RECONNECT_DELAY,
    STATE_UPDATE_BATCH_DELAY,
    LampsterCoordinator,
)
from custom_components.lampster.lampster.models import LampState, RGBColor, WhiteColor
from custom_components.lampster.light import LampsterLight

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


async def test_breathe_from_off_uses_last_color(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Breathe started from off breathes the last color, which Home Assistant shows."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_rgb_color", RGBColor(60, 0, 0))
    # Turned off (as The Lampster reports it): no mode or color while off
    coordinator._async_set_state(LampState(is_on=False, mode="off"), batch=False)
    assert coordinator.data.is_on is False

    await coordinator.async_start_effect("breathe", 255)
    await asyncio.sleep(1)
    assert lamp.mode & 0x20  # color mode
    red, green, blue = lamp.rgb
    assert red > 0 and green == 0 and blue == 0
    await coordinator.async_stop_effect()


async def test_color_change_during_breathe(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A color chosen while Breathe runs restarts it in that color; other effects stop."""
    coordinator = make_coordinator(always_connected=True)
    light = LampsterLight(coordinator)
    coordinator.effect = "breathe"
    with patch.object(coordinator, "async_start_effect") as start:
        await light.async_turn_on(rgb_color=(0, 0, 255), brightness=255)
        start.assert_awaited_once()
        effect = start.await_args.args[0]
        state = start.await_args.kwargs.get("start", start.await_args.args[-1])
        assert effect == "breathe"
        assert state.mode == "rgb" and state.rgb_color == RGBColor(0, 0, 100)

        start.reset_mock()
        await light.async_turn_on(color_temp_kelvin=2700, brightness=255)
        effect = start.await_args.args[0]
        state = start.await_args.kwargs.get("start", start.await_args.args[-1])
        assert state.mode == "white" and state.white_color.warm == 100

        start.reset_mock()
        coordinator.effect = "colorloop"
        await light.async_turn_on(rgb_color=(0, 0, 255))
        start.assert_not_awaited()  # any other effect stops for a color


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


async def test_effect_from_off_shows_on(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """An effect started while off shows The Lampster as on while it runs."""
    lamp.mode = 0x48  # white, off
    coordinator = make_coordinator()
    await coordinator._async_try_connect("check interval")
    assert coordinator.data.is_on is False

    await coordinator.async_start_effect("fireplace", 200)
    assert coordinator.data.is_on
    assert coordinator.data.mode == "rgb"
    assert coordinator.effect_brightness == 200
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()
    assert coordinator.data.is_on  # the lamp's own mode report does not undo it

    await coordinator.async_stop_effect()
    assert coordinator.data.is_on  # stopped, it keeps the last color


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


async def test_diagnostics_hold_during_effect_is_a_hold(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """An effect turning the lamp on is not taken for the touch button.

    The lamp does not report the effect's writes, so a hold during an effect
    started from off must be recorded as a hold, not as turning on.
    """
    coordinator = make_coordinator(always_connected=True)
    await coordinator._async_try_connect("check interval")  # lamp is off
    await coordinator.async_start_effect("candle", 200)
    for _ in range(40):
        if coordinator._task_engaged:
            break
        await asyncio.sleep(0.05)
    lamp.touch_hold(steps=2)
    assert not any(
        event.startswith("Touch button: State(on") for event in event_log(coordinator)
    )


async def test_connection_source_from_slot_allocations(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """The uplink is the adapter or proxy that reports holding the connection."""

    def scanner(source: str, allocated: list[str]) -> SimpleNamespace:
        allocations = SimpleNamespace(allocated=allocated)
        return SimpleNamespace(source=source, get_allocations=lambda: allocations)

    scanners = [
        scanner("11:11:11:11:11:11", ["AA:AA:AA:AA:AA:AA"]),
        scanner("22:22:22:22:22:22", [ADDRESS.lower()]),
    ]
    coordinator = make_coordinator(always_connected=True)
    with patch.object(
        coordinator_module.bluetooth,
        "async_current_scanners",
        return_value=scanners,
        create=True,
    ):
        assert coordinator.connection_source is None  # not connected yet
        await coordinator._async_try_connect("check interval")
        assert coordinator.connection_source == "22:22:22:22:22:22"

        scanners.pop()  # no adapter or proxy reports the connection
        assert coordinator.connection_source is None


async def test_white_request_reported_exactly(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A requested color temperature is shown as requested, not as converted back.

    At 10% brightness, 3200 K becomes warm 10 / cold 2, which converts back
    to 3333 K. Once the touch button changes the LEDs, the device values apply.
    """
    coordinator = make_coordinator(always_connected=True)
    light = LampsterLight(coordinator)
    await light.async_turn_on(color_temp_kelvin=3200, brightness=26)
    light._update_from_coordinator()
    assert (light.color_temp_kelvin, light.brightness) == (3200, 26)

    lamp.touch_hold(steps=1)
    light._update_from_coordinator()
    assert light.color_temp_kelvin != 3200


async def test_touch_on_reads_actual_levels(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Turning on with the touch button reads the levels the lamp shows.

    The lamp reports only the mode, so without the read the white levels
    Home Assistant last knew would be shown.
    """
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_white_color", WhiteColor(40, 10))
    lamp.touch_tap()  # off
    lamp.white = bytes([25, 5])  # changed without a report
    lamp.touch_tap()  # on
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.data.is_on
    assert coordinator.data.white_color == WhiteColor(25, 5)


async def test_touch_hold_stops_white_effect(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """A hold during a white effect stops it, so the lamp's dimming is kept."""
    coordinator = make_coordinator()
    await coordinator.async_command("set_white_color", WhiteColor(40, 0))
    await coordinator.async_start_effect("candle", 200)
    for _ in range(40):
        if coordinator._task_engaged:
            break
        await asyncio.sleep(0.05)
    assert coordinator._task_engaged

    lamp.touch_hold(steps=3)
    await asyncio.sleep(1)
    await hass.async_block_till_done()
    assert coordinator.effect is None
    assert lamp.mode & 0x80
    held = lamp.white
    await asyncio.sleep(1)
    assert lamp.white == held  # no more candle steps


async def test_effect_speed_restarts_running_effect(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Changing the Effects speed restarts an effect that follows it, not one with its own."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_start_effect("colorloop", 200)
    first = coordinator._task
    await coordinator.async_set_effect_speed(150)
    assert coordinator.effect == "colorloop"
    assert coordinator._task is not first  # restarted at the new speed

    await coordinator.async_start_effect("colorloop", 200, speed=50)
    own_speed = coordinator._task
    await coordinator.async_set_effect_speed(75)
    assert coordinator._task is own_speed
    assert coordinator.effect_speed_override == 50


async def test_start_effect_action(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """The action starts an effect with its own speed, brightness and color."""
    coordinator = make_coordinator(always_connected=True)
    light = LampsterLight(coordinator)
    with patch.object(coordinator, "async_start_effect") as start:
        await light.async_start_effect_action("fireplace", speed=150, brightness_pct=40)
        start.assert_awaited_once_with("fireplace", 102, 150, None)
        start.reset_mock()
        await light.async_start_effect_action("candle")
        start.assert_awaited_once_with("candle", 255, None, None)
        start.reset_mock()
        await light.async_start_effect_action("breathe", rgb_color=(255, 0, 128))
        start.assert_awaited_once_with("breathe", 255, None, (255, 0, 128))
        # Only Breathe uses a color
        with pytest.raises(ServiceValidationError):
            await light.async_start_effect_action("fireplace", rgb_color=(255, 0, 0))
    with patch.object(coordinator, "async_stop_effect") as stop:
        await light.async_stop_effect_action()
        stop.assert_awaited_once()


async def test_step_time_includes_the_write(
    hass: HomeAssistant,
    lamp: FakeLamp,
    make_coordinator: CoordinatorFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A step's write time counts toward its delay, so slow writes keep the pace.

    Two steps of 0.5 s and 0.2 s with writes of 0.3 s take about 0.8 s, not 1.3 s.
    """
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_rgb_color", RGBColor(10, 0, 0))

    async def slow_write(color: RGBColor) -> None:
        await asyncio.sleep(0.3)

    monkeypatch.setattr(coordinator._client, "set_rgb_color", slow_write)
    steps = [effects.Step(RGBColor(1, 0, 0), 0.5), effects.Step(RGBColor(2, 0, 0), 0.2)]
    start = time.monotonic()
    await coordinator._async_run_steps("rgb", iter(steps), "test", None)
    assert time.monotonic() - start < 1.1


async def test_effect_off_step_turns_lamp_off(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """An off step turns The Lampster off (keeping color mode); the next step turns it on."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_rgb_color", RGBColor(10, 0, 0))
    seen: list[int] = []
    original = coordinator._client.switch_off

    async def record_off() -> None:
        await original()
        seen.append(lamp.mode)

    coordinator._client.switch_off = record_off
    steps = [
        effects.Step(RGBColor(20, 0, 0), 0.01),
        effects.Step(None, 0.01),
        effects.Step(RGBColor(30, 0, 0), 0.01),
    ]
    coordinator._async_start_task("rgb", iter(steps), "test")
    await coordinator._task
    assert seen == [0x28]  # off, still in color mode
    assert lamp.mode & 0x80  # back on for the last step
    assert lamp.rgb == bytes([30, 0, 0])


async def test_touch_on_while_effect_off_stops_it(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Turning The Lampster on by touch while an effect has it off stops the effect."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_rgb_color", RGBColor(10, 0, 0))

    def steps():
        yield effects.Step(RGBColor(20, 0, 0), 0.01)
        while True:
            yield effects.Step(None, 0.05)

    coordinator.effect = "fireworks"
    coordinator._async_start_task("rgb", steps(), "effect fireworks")
    for _ in range(40):
        if coordinator._task_off:
            break
        await asyncio.sleep(0.02)
    assert coordinator._task_off
    lamp.touch_tap()  # on again
    await asyncio.sleep(0.2)
    await hass.async_block_till_done()
    assert coordinator.effect is None
    assert lamp.mode & 0x80


async def test_not_heard_repair_issue(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Not connected and not heard for a while: a repair issue; heard again: cleared.

    Connection failures meanwhile do not raise the misleading slot notice.
    """
    coordinator = make_coordinator()
    issue_id = f"not_heard_{ADDRESS}"
    coordinator._available = False  # no adapter or proxy hears it
    coordinator._async_check_not_heard()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None  # not yet

    coordinator._not_heard_since = time.monotonic() - NOT_HEARD_ISSUE_AFTER
    coordinator._async_check_not_heard()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    for _ in range(FAILURES_BEFORE_ISSUE):
        coordinator._async_connection_failed(
            "connecting", TimeoutError("No backend with an available connection slot")
        )
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"no_connection_slot_{ADDRESS}") is None

    coordinator._available = True  # heard again
    coordinator._async_check_not_heard()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_breathe_in_a_given_color(
    hass: HomeAssistant, lamp: FakeLamp, make_coordinator: CoordinatorFactory
) -> None:
    """Breathe started with a color breathes that color, also from white."""
    coordinator = make_coordinator(always_connected=True)
    await coordinator.async_command("set_white_color", WhiteColor(40, 10))
    await coordinator.async_start_effect("breathe", 255, color=(255, 0, 0))
    assert coordinator.effect_color == (255, 0, 0)
    await asyncio.sleep(0.5)
    assert lamp.rgb_writes
    assert all(green == 0 and blue == 0 for _, green, blue in lamp.rgb_writes)
    assert max(red for red, _, _ in lamp.rgb_writes) > 0

    # Changing the Effects speed restarts it in the same color
    await coordinator.async_set_effect_speed(150)
    assert coordinator.effect_color == (255, 0, 0)
    await coordinator.async_stop_effect()

    # Effects with their own colors ignore a color
    await coordinator.async_start_effect("colorloop", 255, color=(255, 0, 0))
    assert coordinator.effect_color is None
    await coordinator.async_stop_effect()


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
