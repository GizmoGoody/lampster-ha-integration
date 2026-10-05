"""Coordinator for The Lampster integration."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
import dataclasses
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .effects import (
    EFFECT_SPEED_DEFAULT,
    MODE_RGB,
    Color,
    Step,
    current_color,
    effect_mode,
    effect_steps,
    scale_steps,
    transition_steps,
    zero_color,
)
from .lampster.client import LampsterClient
from .lampster.constants import CHAR_MODE
from .lampster.exceptions import (
    ConnectionError as LampsterConnectionError,
    LampsterException,
)
from .lampster.models import LampState
from .registry import find_device

_LOGGER = logging.getLogger(__name__)

# Minimum 10 seconds per HA docs: "BlueZ must resolve services when connecting"
CONNECT_TIMEOUT = 10

# Retry soon after an unexpected disconnect while the connection should be up;
# later attempts come from the regular check interval
RECONNECT_DELAY = 5

# Touch-button holds send several brightness steps per second; batch them
# into one entity update
STATE_UPDATE_BATCH_DELAY = 0.5

# A touch-button tap during a color effect or fade switches The Lampster to
# white instead of off; if no hold (white brightness steps) follows within
# this time, it was a tap and The Lampster is turned off
TOUCH_OFF_DELAY = 0.8

# Raise a repair issue after this many connection failures in a row
FAILURES_BEFORE_ISSUE = 5
ISSUE_CANNOT_CONNECT = "cannot_connect"
ISSUE_NO_CONNECTION_SLOT = "no_connection_slot"

# Connection events kept for the diagnostics download
EVENT_HISTORY = 50

COMMAND_ERRORS = (LampsterException, BleakError, TimeoutError)

REASON_RECONNECT = "reconnect after drop"

# Connection status values (see LampsterCoordinator.connection_status)
STATUS_CONNECTED = "connected"
STATUS_STANDBY = "standby"
STATUS_CONNECTING = "connecting"
STATUS_CHECKING = "checking"
STATUS_RECONNECTING = "reconnecting"
STATUS_FAILED = "failed"
STATUS_DISCONNECTED = "disconnected"
CONNECTION_STATUSES = [
    STATUS_CONNECTED,
    STATUS_STANDBY,
    STATUS_CONNECTING,
    STATUS_CHECKING,
    STATUS_RECONNECTING,
    STATUS_FAILED,
    STATUS_DISCONNECTED,
]


class LampsterCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator to manage the Lampster BLE connection and state.

    Connection policy (the lamp accepts only one connection at a time):
    - While the lamp is on, stay connected. The lamp pushes every change,
      including touch-button presses, so state updates instantly.
    - After it turns off, stay connected for off_disconnect_delay seconds,
      then disconnect, unless always_connected is set.
    - While disconnected, connect every poll_interval seconds to check
      whether it was turned on with the touch button; stay connected if so.
    - Home Assistant commands connect on demand.

    Commands are serialized over the one connection. While a command is in
    flight, newer requests replace older queued ones, so only the latest
    requested state is sent.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        *,
        always_connected: bool,
        poll_interval: int,
        off_disconnect_delay: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self._address = address
        self._always_connected = always_connected
        self._poll_interval = poll_interval
        self._off_disconnect_delay = off_disconnect_delay

        self._lock = asyncio.Lock()
        self._client: LampsterClient | None = None
        # A brief check is in progress (connecting or connected)
        self._checking = False
        # A connection attempt other than a check is in progress
        self._connecting = False
        # The last connection attempt or command failed
        self._failed = False
        self._pending_command: tuple[str, tuple[Any, ...]] | None = None
        self._stopping = False
        self._cancel_off_disconnect: CALLBACK_TYPE | None = None
        self._cancel_reconnect: CALLBACK_TYPE | None = None
        self._cancel_batched_update: CALLBACK_TYPE | None = None
        # Effect or transition running in the background, and the mode it
        # keeps the lamp in (None while it finishes)
        self._task: asyncio.Task | None = None
        self._task_mode: str | None = None
        # The task has brought the lamp into its mode; from then on a report
        # of another mode means the touch button was used
        self._task_engaged = False
        self._versions_read = False
        self._consecutive_failures = 0
        self._last_error: str | None = None
        self._events: deque[tuple[str, str]] = deque(maxlen=EVENT_HISTORY)

        # None until the first successful connection
        self.data: LampState | None = None
        self.temperature: float | None = None
        self.effect: str | None = None
        # Speed for effects in percent (the Effects speed setting)
        self.effect_speed: int = EFFECT_SPEED_DEFAULT
        # The running effect's own speed when an action started it with one;
        # None when it follows effect_speed
        self.effect_speed_override: int | None = None
        self._effect_brightness = 255

        # Diagnostics
        self.last_connect_ms: int | None = None
        self.last_command_ms: int | None = None

    @property
    def connected(self) -> bool:
        """Return True if currently connected to the lamp."""
        return self._client is not None and self._client.is_connected

    @property
    def connection_status(self) -> str:
        """Return a one-word description of the connection.

        connected: holding the connection (lamp on, or keep connected while off)
        standby: lamp off, connection held until the stay-connected delay ends
        connecting: connecting for a command or a reconnect
        checking: briefly connecting/connected to check whether the lamp is on
        reconnecting: the connection dropped; a retry is scheduled
        failed: the last connection attempt or command failed
        disconnected: anything else
        """
        if self._checking:
            return STATUS_CHECKING
        if self._connecting:
            return STATUS_CONNECTING
        if self.connected:
            return STATUS_STANDBY if self._cancel_off_disconnect else STATUS_CONNECTED
        if self._cancel_reconnect:
            return STATUS_RECONNECTING
        if self._failed:
            return STATUS_FAILED
        return STATUS_DISCONNECTED

    @property
    def available(self) -> bool:
        """Return True if the lamp is connected or advertising.

        The lamp stops advertising while connected, so the advertisement-based
        availability from the base class alone would eventually go stale.
        """
        return self.connected or super().available

    @property
    def last_service_info(self) -> bluetooth.BluetoothServiceInfoBleak | None:
        """Return the most recent advertisement seen for the lamp."""
        return bluetooth.async_last_service_info(
            self.hass, self._address, connectable=True
        )

    def _should_stay_connected(self) -> bool:
        """Whether the connection should be kept open right now."""
        return self._always_connected or bool(self.data and self.data.is_on)

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start listening for advertisements and checking on a timer."""
        cancel_advertisements = super().async_start()
        cancel_timer = async_track_time_interval(
            self.hass, self._async_scheduled_check, timedelta(seconds=self._poll_interval)
        )

        @callback
        def _async_cancel() -> None:
            cancel_timer()
            cancel_advertisements()

        return _async_cancel

    async def async_stop(self) -> None:
        """Cancel timers and effects, and disconnect (used on unload)."""
        self._stopping = True
        await self._async_stop_task()
        self._async_delete_issues()
        self._async_cancel_reconnect()
        self._async_cancel_batched_update()
        async with self._lock:
            await self._async_disconnect("integration unloading")

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Connect when the lamp is first seen or reappears (e.g. plugged in).

        HA only calls this when the advertisement content changes or the
        lamp reappears, not for every repeated advertisement.
        """
        super()._async_handle_bluetooth_event(service_info, change)
        if not self.connected and not self._lock.locked():
            self.hass.async_create_background_task(
                self._async_try_connect("advertisement received"),
                f"lampster {self._address} connect",
            )

    async def _async_scheduled_check(self, _now: datetime) -> None:
        await self._async_try_connect("check interval")

    async def _async_try_connect(self, reason: str) -> None:
        """Connect to read the lamp's state; stay connected if it should be.

        Runs on the check interval, on advertisements and after unexpected
        disconnects. Does nothing if already connected or busy.
        """
        if (
            self._stopping
            or self.hass.state is not CoreState.running
            or self.connected
            or self._lock.locked()
            or not bluetooth.async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
        ):
            return

        async with self._lock:
            if self.connected:
                return
            # Without "keep connected while off", this is a brief check until
            # we know whether the lamp is on
            self._checking = not self._always_connected and reason != REASON_RECONNECT
            try:
                await self._async_ensure_connected(reason)
            except COMMAND_ERRORS as err:
                self._checking = False
                self._async_connection_failed(f"connecting ({reason})", err)
                return

            if self._should_stay_connected():
                self._checking = False
                self._record(
                    "Staying connected ("
                    + (
                        "maintain connection at all times"
                        if self._always_connected
                        else "The Lampster is on"
                    )
                    + ")"
                )
                self.async_update_listeners()
            else:
                await self._async_disconnect("check found The Lampster off")
                self._checking = False
                self.async_update_listeners()

    async def async_command(self, method_name: str, *args: Any) -> None:
        """Execute a command on the device.

        Stops any running effect. If other commands are queued behind the one
        in flight, only the most recent is sent; earlier ones return without
        doing anything.
        """
        await self._async_stop_task()
        self._pending_command = (method_name, args)

        async with self._lock:
            if self._pending_command is None:
                # Superseded by a newer command that has already been sent
                return
            method_name, args = self._pending_command
            self._pending_command = None

            try:
                client = await self._async_execute(method_name, args)
            except COMMAND_ERRORS as err:
                # The connection may have dropped; retry once on a fresh one
                self._record(f"Command {method_name} failed, retrying: {err}")
                await self._async_disconnect(f"command {method_name} failed")
                try:
                    client = await self._async_execute(method_name, args)
                except COMMAND_ERRORS as err2:
                    await self._async_disconnect(f"command {method_name} failed again")
                    self._async_connection_failed(f"command {method_name}", err2)
                    raise

            self._async_set_state(client.state, batch=False)

    async def _async_execute(
        self, method_name: str, args: tuple[Any, ...]
    ) -> LampsterClient:
        """Run a client method, connecting first if needed. Lock must be held."""
        client = await self._async_ensure_connected(f"command {method_name}")
        start = time.monotonic()
        await getattr(client, method_name)(*args)
        self.last_command_ms = round((time.monotonic() - start) * 1000)
        return client

    async def _async_ensure_connected(self, reason: str) -> LampsterClient:
        """Return a connected client, connecting if needed. Lock must be held."""
        if self.connected:
            return self._client

        self._async_cancel_reconnect()
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if not ble_device:
            raise LampsterConnectionError(
                f"The Lampster ({self._address}) was not found or is not connectable"
            )

        self._record(f"Connecting ({reason})")
        self._failed = False
        self._connecting = not self._checking
        self.async_update_listeners()
        try:
            service_info = self.last_service_info
            start = time.monotonic()
            bleak_client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                (service_info.name if service_info else None) or self._address,
                disconnected_callback=self._handle_disconnect,
                max_attempts=3,
                timeout=CONNECT_TIMEOUT,
            )
            self.last_connect_ms = round((time.monotonic() - start) * 1000)

            client = LampsterClient(self._address)
            client._client = bleak_client
            try:
                if not bleak_client.services.get_characteristic(CHAR_MODE):
                    # A stale service cache can hide the lamp's control service
                    await bleak_client.clear_cache()
                    raise LampsterConnectionError(
                        "The Lampster control service was not found; cleared the service cache"
                    )
                # Sync with the device so commands start from its actual state
                await client.refresh_state()
                await client.start_notifications(
                    self._handle_state_notification, self._handle_temperature
                )
                if not self._versions_read:
                    await self._async_update_device_versions(client)
            except COMMAND_ERRORS:
                await bleak_client.disconnect()
                raise
        finally:
            self._connecting = False

        self._client = client
        self._record(
            f"Connected in {self.last_connect_ms} ms ({reason}), "
            f"The Lampster state: {client.state}"
        )
        self._async_connection_succeeded()
        if self._task_mode is None:
            # The caller decides whether to stay connected (a command may be
            # about to turn the lamp on), so don't start the off countdown here
            self._async_set_state(client.state, batch=False, apply_policy=False)
        else:
            # An effect or transition is showing its own target; keep it
            self.async_update_listeners()
        return client

    async def _async_update_device_versions(self, client: LampsterClient) -> None:
        """Show the firmware and hardware revisions on the device page."""
        versions = await client.read_versions()
        self._versions_read = True
        registry = dr.async_get(self.hass)
        if versions and (
            device := find_device(registry, identifiers={(DOMAIN, self._address)})
        ):
            registry.async_update_device(
                device.id,
                sw_version=versions.get("firmware"),
                hw_version=versions.get("hardware"),
            )

    async def _async_disconnect(self, reason: str) -> None:
        """Disconnect if connected. Lock must be held."""
        self._async_cancel_off_disconnect()
        client, self._client = self._client, None
        if client is not None:
            self._record(f"Disconnecting ({reason})")
            try:
                await client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error disconnecting: %s", err)
            self.temperature = None
            self.async_update_listeners()

    @callback
    def _handle_disconnect(self, bleak_client: Any) -> None:
        """Handle the connection dropping without us asking."""
        if self._client is None or self._client._client is not bleak_client:
            return
        self._client = None
        self.temperature = None
        self._async_cancel_off_disconnect()

        if not self._stopping and self._should_stay_connected():
            self._record(
                f"Connection dropped unexpectedly; reconnecting in {RECONNECT_DELAY} s"
            )
            self._async_cancel_reconnect()
            self._cancel_reconnect = async_call_later(
                self.hass, RECONNECT_DELAY, self._async_reconnect
            )
        else:
            self._record("Connection dropped unexpectedly")
        self.async_update_listeners()

    async def _async_reconnect(self, _now: datetime) -> None:
        self._cancel_reconnect = None
        await self._async_try_connect(REASON_RECONNECT)

    @callback
    def _handle_state_notification(self, state: LampState) -> None:
        """Handle a change pushed by the lamp (touch button or our own writes)."""
        _LOGGER.debug("The Lampster reported: %s", state)
        if self._task_mode is not None:
            if state.is_on and state.mode == self._task_mode:
                # The effect's or transition's own writes; not recorded per step
                self._task_engaged = True
                return
            if not self._task_engaged:
                # Still switching the lamp into the task's mode
                return
            # The touch button switched mode or turned it off: stop the task
            self._record(
                f"The Lampster left {self._task_mode} mode; stopping "
                + (f"effect {self.effect}" if self.effect else "transition")
            )
            if self._task_mode == MODE_RGB and state.is_on and state.mode == "white":
                # In color mode the touch button switches to white rather
                # than off; treat a tap as "turn off"
                self.hass.async_create_background_task(
                    self._async_touch_off(state.white_color), "lampster touch off"
                )
            self.hass.async_create_task(self._async_stop_task())
        self._async_set_state(state, batch=True)

    async def _async_touch_off(self, white: Any) -> None:
        """Turn off after a tap that stopped a color effect or fade.

        A hold changes the white brightness within TOUCH_OFF_DELAY; then the
        user is dimming, so The Lampster stays on.
        """
        await asyncio.sleep(TOUCH_OFF_DELAY)
        state = self.data
        if state and state.is_on and state.mode == "white" and state.white_color == white:
            self._record("Touch button tapped during a color effect or fade; turning off")
            try:
                await self.async_command("power_off")
            except COMMAND_ERRORS as err:
                _LOGGER.debug("Turning off after touch failed: %s", err)

    @callback
    def _handle_temperature(self, temperature: float) -> None:
        """Handle the lamp's periodic internal temperature report."""
        rounded = round(temperature, 1)
        if rounded != self.temperature:
            self.temperature = rounded
            self._async_schedule_batched_update()

    @callback
    def _async_set_state(
        self, state: LampState, *, batch: bool, apply_policy: bool = True
    ) -> None:
        """Store new state, apply the connection policy and notify entities."""
        was_on = bool(self.data and self.data.is_on)
        self.data = dataclasses.replace(state)

        if self.connected and apply_policy:
            if self._should_stay_connected():
                if self._cancel_off_disconnect is not None:
                    _LOGGER.debug("The Lampster turned back on; staying connected")
                self._async_cancel_off_disconnect()
            elif self._cancel_off_disconnect is None and not self._checking:
                if was_on:
                    self._record(
                        f"The Lampster turned off; disconnecting in "
                        f"{self._off_disconnect_delay} s unless it is turned back on"
                    )
                self._cancel_off_disconnect = async_call_later(
                    self.hass, self._off_disconnect_delay, self._async_off_disconnect
                )

        if batch:
            self._async_schedule_batched_update()
        else:
            self._async_cancel_batched_update()
            self.async_update_listeners()

    async def _async_off_disconnect(self, _now: datetime) -> None:
        """Disconnect once the lamp has stayed off for the configured delay."""
        self._cancel_off_disconnect = None
        async with self._lock:
            # It may have been turned back on, or a command may have
            # rescheduled this while waiting for the lock
            if self._cancel_off_disconnect is None and not self._should_stay_connected():
                await self._async_disconnect(
                    f"The Lampster off for {self._off_disconnect_delay} s"
                )

    async def async_start_effect(
        self, effect: str, brightness: int, speed: int | None = None
    ) -> None:
        """Start a software effect at a brightness (0-255).

        Runs at the given speed (percent), or else at effect_speed.
        """
        await self._async_stop_task()
        mode = effect_mode(effect, self.data)
        steps = scale_steps(
            effect_steps(effect, brightness, self.data), speed or self.effect_speed
        )
        self.effect = effect
        self.effect_speed_override = speed
        self._effect_brightness = brightness
        self._async_start_task(mode, steps, f"effect {effect}")
        self._record(f"Started effect {effect} at {speed or self.effect_speed}% speed")
        self.async_update_listeners()

    async def async_set_effect_speed(self, speed: int) -> None:
        """Set the speed for effects; a running effect that follows it restarts."""
        self.effect_speed = speed
        if self.effect and self.effect_speed_override is None:
            await self.async_start_effect(self.effect, self._effect_brightness)

    async def async_stop_effect(self) -> None:
        """Stop the running effect, if any (the lamp keeps its last color)."""
        await self._async_stop_task()

    async def async_transition(self, mode: str, target: Color, duration: float) -> None:
        """Fade to a color over duration seconds.

        Fades from the current color when the lamp already shows this mode,
        otherwise from dark. Home Assistant shows the target right away.
        """
        await self._async_stop_task()
        start = current_color(self.data, mode)
        steps = transition_steps(start, target, duration)
        self.data = dataclasses.replace(
            self.data or LampState(is_on=True, mode=mode),
            is_on=True,
            mode=mode,
            **({"rgb_color": target} if mode == MODE_RGB else {"white_color": target}),
        )
        self._async_start_task(mode, steps, "transition")
        self._record(f"Fading to {target} over {duration} s")
        self.async_update_listeners()

    async def async_transition_off(self, duration: float) -> None:
        """Fade to dark over duration seconds, then turn off."""
        await self._async_stop_task()
        if not self.data or not self.data.is_on:
            await self.async_command("power_off")
            return
        mode = self.data.mode
        steps = transition_steps(current_color(self.data, mode), zero_color(mode), duration)

        async def finish(client: LampsterClient) -> None:
            await client.power_off()

        self.data = dataclasses.replace(self.data, is_on=False, mode="off")
        self._async_start_task(mode, steps, "transition off", finish)
        self._record(f"Fading off over {duration} s")
        self.async_update_listeners()

    @callback
    def _async_start_task(
        self,
        mode: str,
        steps: Iterable[Step],
        name: str,
        finish: Callable[[LampsterClient], Awaitable[None]] | None = None,
    ) -> None:
        self._task_mode = mode
        self._task_engaged = False
        self._task = self.hass.async_create_background_task(
            self._async_run_steps(mode, steps, name, finish), f"lampster {name}"
        )

    async def _async_stop_task(self) -> None:
        """Stop the running effect or transition, if any."""
        task, self._task = self._task, None
        self._task_mode = None
        if task is None:
            return
        was_effect = self.effect is not None
        self.effect = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if was_effect:
            self.async_update_listeners()

    async def _async_run_steps(
        self,
        mode: str,
        steps: Iterable[Step],
        name: str,
        finish: Callable[[LampsterClient], Awaitable[None]] | None,
    ) -> None:
        """Send each step's color, then run finish (if any) and publish the result."""
        write = "set_rgb_color" if mode == MODE_RGB else "set_white_color"
        try:
            client: LampsterClient | None = None
            for step in steps:
                async with self._lock:
                    client = await self._async_ensure_connected(name)
                    if self._task_engaged and not (
                        client.state.is_on and client.state.mode == mode
                    ):
                        # The touch button turned The Lampster off or changed
                        # mode; writing now would switch it back on
                        return
                    await getattr(client, write)(step.color)
                    # The Lampster is now in the task's mode. It only reports
                    # mode changes, not our color writes, so this cannot be
                    # left to its reports (none come when it was already in
                    # this mode); from here a mode report means the touch button
                    self._task_engaged = True
                    self._async_cancel_off_disconnect()
                await asyncio.sleep(step.delay)
            # Done: the lamp's own reports apply normally again
            self._task_mode = None
            async with self._lock:
                client = await self._async_ensure_connected(name)
                if finish is not None:
                    await finish(client)
                self._task = None
                self._async_set_state(client.state, batch=False)
        except COMMAND_ERRORS as err:
            _LOGGER.warning("%s stopped: %s", name.capitalize(), err)
            self._record(f"{name.capitalize()} stopped: {err}")
            self._task = None
            self._task_mode = None
            self.effect = None
            self.async_update_listeners()

    @callback
    def _record(self, message: str) -> None:
        """Log a connection event and keep it for the diagnostics download."""
        _LOGGER.debug(message)
        self._events.append((dt_util.utcnow().isoformat(timespec="seconds"), message))

    @callback
    def _async_connection_failed(self, what: str, err: Exception) -> None:
        """Count a failure; raise a repair issue if they keep happening."""
        self._failed = True
        self._consecutive_failures += 1
        self._last_error = str(err) or type(err).__name__
        self._record(f"{what.capitalize()} failed: {self._last_error}")
        if self._consecutive_failures >= FAILURES_BEFORE_ISSUE:
            no_slot = "connection slot" in self._last_error.lower()
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{ISSUE_NO_CONNECTION_SLOT if no_slot else ISSUE_CANNOT_CONNECT}_{self._address}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_NO_CONNECTION_SLOT if no_slot else ISSUE_CANNOT_CONNECT,
                translation_placeholders={
                    "attempts": str(self._consecutive_failures),
                    "error": self._last_error,
                },
            )
        self.async_update_listeners()

    @callback
    def _async_connection_succeeded(self) -> None:
        if self._consecutive_failures >= FAILURES_BEFORE_ISSUE:
            self._async_delete_issues()
        self._consecutive_failures = 0

    @callback
    def _async_delete_issues(self) -> None:
        for key in (ISSUE_CANNOT_CONNECT, ISSUE_NO_CONNECTION_SLOT):
            ir.async_delete_issue(self.hass, DOMAIN, f"{key}_{self._address}")

    def diagnostics(self) -> dict[str, Any]:
        """Return the coordinator's state for the diagnostics download."""
        service_info = self.last_service_info
        return {
            "connection_status": self.connection_status,
            "connected": self.connected,
            "available": self.available,
            "settings": {
                "always_connected": self._always_connected,
                "poll_interval": self._poll_interval,
                "off_disconnect_delay": self._off_disconnect_delay,
            },
            "state": str(self.data) if self.data else None,
            "effect": self.effect,
            "temperature": self.temperature,
            "last_connect_ms": self.last_connect_ms,
            "last_command_ms": self.last_command_ms,
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._last_error,
            "last_advertisement": {
                "rssi": service_info.rssi,
                "source": service_info.source,
                "name": service_info.name,
            }
            if service_info
            else None,
            "recent_events": [
                {"time": time_, "event": event} for time_, event in self._events
            ],
        }

    @callback
    def _async_schedule_batched_update(self) -> None:
        if self._cancel_batched_update is None:
            self._cancel_batched_update = async_call_later(
                self.hass, STATE_UPDATE_BATCH_DELAY, self._async_flush_batched_update
            )

    @callback
    def _async_flush_batched_update(self, _now: datetime) -> None:
        self._cancel_batched_update = None
        self.async_update_listeners()

    @callback
    def _async_cancel_batched_update(self) -> None:
        if self._cancel_batched_update is not None:
            self._cancel_batched_update()
            self._cancel_batched_update = None

    @callback
    def _async_cancel_off_disconnect(self) -> None:
        if self._cancel_off_disconnect is not None:
            self._cancel_off_disconnect()
            self._cancel_off_disconnect = None

    @callback
    def _async_cancel_reconnect(self) -> None:
        if self._cancel_reconnect is not None:
            self._cancel_reconnect()
            self._cancel_reconnect = None
