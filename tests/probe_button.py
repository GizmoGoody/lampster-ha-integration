#!/usr/bin/env python3
"""Probe how The Lampster's touch button interacts with a BLE connection.

Answers:
1. Does the advertisement change when the button is pressed (disconnected)?
2. Which characteristics support notify/indicate?
3. Does the lamp push notifications when the button is pressed (connected)?
4. Do the characteristic values change when the button is pressed (connected)?
5. Does the button still work while connected, in white and in RGB mode?

Disable the Lampster integration in Home Assistant before running this: the
lamp accepts only one connection at a time.

Usage: python tests/probe_button.py [--skip-adverts]

Protocol based on: https://github.com/Noki/the-lampster
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import sys
import traceback

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bleak import BleakClient, BleakScanner

from lampster.client import LampsterClient
from lampster.constants import CHAR_MODE, CHAR_RGB, CHAR_WHITE, DEVICE_NAME_PREFIX
from lampster.models import RGBColor, WhiteColor

ADVERT_WATCH_SECONDS = 30
BUTTON_WATCH_SECONDS = 30
READ_INTERVAL = 0.5

CHAR_NAMES = {CHAR_MODE: "MODE", CHAR_RGB: "RGB", CHAR_WHITE: "WHITE"}

# The lamp notifies these every ~5 seconds regardless of the button; they are
# logged to the file only so they don't bury the prompts.
PERIODIC_CHARS = {
    "00002a6e-0000-1000-8000-00805f9b34fb",  # Temperature
    "01ff5560-ba5e-f4ee-5ca1-eb1e5e4b1ce0",  # Unknown, ~3300
}

LOG_DIR = Path(__file__).parent.parent / "debug"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"probe_button_{datetime.now():%Y%m%d_%H%M%S}.log"

findings: dict[str, object] = {}

# True while waiting for input, so nothing prints over the prompt
prompting = False


def log(message: str = "", console: bool = True) -> None:
    """Append to the log file, and print unless a prompt is waiting."""
    line = f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {message}" if message else ""
    if console and not prompting:
        print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


async def ask(prompt: str) -> str:
    """Ask the user a question without blocking the event loop."""
    global prompting
    prompting = True
    try:
        answer = (await asyncio.to_thread(input, f"\n>>> {prompt} ")).strip()
    finally:
        prompting = False
    log(f"QUESTION: {prompt} ANSWER: {answer!r}", console=False)
    return answer


async def ask_yes_no(prompt: str) -> str:
    """Ask until the answer is y or n."""
    while (answer := (await ask(f"{prompt} (y/n)")).lower()) not in ("y", "n"):
        print("Please type y or n, then press Enter.")
    return answer


async def wait_for_start(label: str, seconds: int) -> None:
    """Explain the button exercise and wait for Enter."""
    await ask(
        f"[{label}] Press Enter to start. Then, until STOP appears ({seconds}s), "
        "tap the touch button a few times (a few seconds apart) and try one long press."
    )
    log(f"GO: tap the button now ({seconds}s)")


def advert_summary(adv) -> tuple:
    """The advertisement fields HA compares to decide whether anything changed."""
    return (
        adv.local_name,
        tuple(sorted((k, v.hex()) for k, v in adv.manufacturer_data.items())),
        tuple(sorted((k, v.hex()) for k, v in adv.service_data.items())),
        tuple(sorted(adv.service_uuids)),
        adv.tx_power,
    )


async def watch_advertisements():
    """Phase 1: scan while the user presses the button; report advert changes."""
    log("=" * 70)
    log("PHASE 1: Advertisements while disconnected")
    log("=" * 70)
    await wait_for_start("adverts", ADVERT_WATCH_SECONDS)

    device = None
    last = None
    changes = 0
    seen = 0

    def callback(dev, adv):
        nonlocal device, last, changes, seen
        if not (adv.local_name and DEVICE_NAME_PREFIX in adv.local_name):
            return
        if device is None:
            device = dev
        seen += 1
        summary = advert_summary(adv)
        if summary != last:
            if last is not None:
                changes += 1
            log(f"ADVERT {'initial' if last is None else 'CHANGED'}: rssi={adv.rssi} "
                f"name={summary[0]} mfr={summary[1]} svc_data={summary[2]} "
                f"uuids={summary[3]} tx={summary[4]}")
            last = summary

    async with BleakScanner(detection_callback=callback):
        await asyncio.sleep(ADVERT_WATCH_SECONDS)
    log("STOP")

    log(f"Advertisements received: {seen}, content changes: {changes}")
    findings["advert_changes_on_button"] = changes
    return device


async def find_lampster():
    """Scan briefly for the lamp without the button exercise."""
    log("Scanning for the Lampster...")
    return await BleakScanner.find_device_by_filter(
        lambda dev, adv: bool(adv.local_name and DEVICE_NAME_PREFIX in adv.local_name),
        timeout=15,
    )


async def enumerate_characteristics(client: BleakClient) -> list:
    """Phase 2: list characteristics and their properties."""
    log("=" * 70)
    log("PHASE 2: Services and characteristics")
    log("=" * 70)
    notifiable = []
    for service in client.services:
        log(f"Service {service.uuid} ({service.description})")
        for char in service.characteristics:
            value = ""
            if "read" in char.properties:
                try:
                    value = f" value={(await client.read_gatt_char(char)).hex()}"
                except Exception as err:
                    value = f" read failed: {err}"
            name = CHAR_NAMES.get(char.uuid, "")
            log(f"  Char {char.uuid} handle=0x{char.handle:04x} {name} "
                f"props={','.join(char.properties)}{value}")
            if "notify" in char.properties or "indicate" in char.properties:
                notifiable.append(char)
    findings["notifiable"] = [f"{c.uuid} ({CHAR_NAMES.get(c.uuid, '')})" for c in notifiable]
    return notifiable


async def watch_button(client: BleakClient, label: str, notifications: list) -> None:
    """Poll the state characteristics while the user presses the button."""
    await wait_for_start(label, BUTTON_WATCH_SECONDS)
    start_notifications = len(notifications)
    last: dict[str, str] = {}
    read_changes = 0
    end = asyncio.get_running_loop().time() + BUTTON_WATCH_SECONDS

    while asyncio.get_running_loop().time() < end:
        for uuid, name in CHAR_NAMES.items():
            try:
                value = (await client.read_gatt_char(uuid)).hex()
            except Exception as err:
                log(f"READ {name} failed: {err}")
                continue
            if last.get(name) != value:
                if name in last:
                    read_changes += 1
                    log(f"READ {name} CHANGED: {last[name]} -> {value}")
                last[name] = value
        await asyncio.sleep(READ_INTERVAL)
    log("STOP")

    pushed = sum(
        1 for uuid, _ in notifications[start_notifications:] if uuid not in PERIODIC_CHARS
    )
    log(f"[{label}] read value changes: {read_changes}, button notifications: {pushed}")
    responded = await ask_yes_no(f"[{label}] Did the lamp physically respond to the button?")
    findings[label] = {
        "lamp_responded": responded,
        "read_changes": read_changes,
        "button_notifications": pushed,
    }


async def connect(device, attempts: int = 3) -> BleakClient | None:
    """Connect and make sure the lamp's control service was discovered.

    Windows sometimes returns an incomplete service list from its cache, so
    bypass the cache and reconnect if the MODE characteristic is missing.
    """
    for attempt in range(1, attempts + 1):
        log(f"Connecting (attempt {attempt})...")
        # Windows can take 10-20s to connect and resolve services
        client = BleakClient(device, timeout=45, winrt={"use_cached_services": False})
        try:
            await client.connect()
        except Exception as err:
            log(f"Connect failed: {type(err).__name__} {err}")
            await asyncio.sleep(3)
            continue

        if client.services.get_characteristic(CHAR_MODE):
            log("Connected")
            return client

        log("Connected, but the lamp's control service is missing; reconnecting")
        await client.disconnect()
        await asyncio.sleep(3)

    log("Could not connect with a complete service list")
    return None


async def main(skip_adverts: bool) -> None:
    log(f"Logging to {LOG_FILE}")
    device = await (find_lampster() if skip_adverts else watch_advertisements())
    if device is None:
        log("No Lampster found. Is it powered, in range, and is HA's integration disabled?")
        return
    log(f"Found {device.name} at {device.address}")

    client = await connect(device)
    if client is None:
        return

    try:
        notifiable = await enumerate_characteristics(client)

        notifications: list = []

        def on_notify(char, data: bytearray) -> None:
            notifications.append((char.uuid, data.hex()))
            log(
                f"NOTIFY {char.uuid} {CHAR_NAMES.get(char.uuid, '')}: {data.hex()}",
                console=char.uuid not in PERIODIC_CHARS,
            )

        for char in notifiable:
            try:
                await client.start_notify(char, on_notify)
                log(f"Subscribed to {char.uuid} {CHAR_NAMES.get(char.uuid, '')}")
            except Exception as err:
                log(f"Subscribe to {char.uuid} failed: {err}")

        lamp = LampsterClient(device.address)
        lamp._client = client
        await lamp.refresh_state()
        log(f"Current state: {lamp.state}")

        log("=" * 70)
        log("PHASE 3: Button while connected, WHITE mode")
        log("=" * 70)
        await lamp.set_white_color(WhiteColor(50, 0))
        log("Lamp set to warm white 50%")
        await watch_button(client, "connected_white", notifications)

        log("=" * 70)
        log("PHASE 4: Button while connected, RGB mode")
        log("=" * 70)
        await lamp.refresh_state()
        await lamp.set_rgb_color(RGBColor(0, 0, 60))
        log("Lamp set to blue")
        await watch_button(client, "connected_rgb", notifications)

        # Leave the lamp in white mode, which keeps the button usable
        await lamp.refresh_state()
        await lamp.set_white_color(WhiteColor(50, 0))
        log("Restored warm white 50%")

    finally:
        await client.disconnect()

    log("Disconnected")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    for key, value in findings.items():
        log(f"{key}: {value}")
    log(f"Log saved to {LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-adverts",
        action="store_true",
        help="skip phase 1 (advertisement watch) and just find the lamp",
    )
    try:
        asyncio.run(main(parser.parse_args().skip_adverts))
    except KeyboardInterrupt:
        log("Stopped by user")
    except Exception:
        log("CRASHED:\n" + traceback.format_exc())
        log(f"Log saved to {LOG_FILE}")
        sys.exit(1)
