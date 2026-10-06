# The Lampster - Home Assistant Integration

Home Assistant custom integration for The Lampster, an RGB Bluetooth lamp (Model: LA-2017B).

## Features

- ✅ **Automatic Bluetooth Discovery** - Device appears automatically in HA
- ✅ **RGB Color Control** - Full RGB color picker support
- ✅ **Color Temperature** - Warm to cool white (2700K - 6500K)
- ✅ **Favorite Colors** - Red, green, blue, white, cyan, magenta, yellow and ten common white temperatures added to the color picker (appended to your own favorites; each is added only once, so removed ones stay removed)
- ✅ **Effects** - Color Loop, Random, Candle, Fireplace and Breathe, from the light card
- ✅ **Transitions** - Fade on, off or between colors over any number of seconds
- ✅ **Diagnostics and repairs** - Downloadable diagnostics, and a repair notice when The Lampster cannot be reached
- ✅ **Brightness Control** - Adjust light intensity
- ✅ **Power Control** - Turn on/off
- ✅ **Touch Button Sync** - Touch button changes show up instantly while The Lampster is on
- ✅ **Diagnostics** - Signal strength, connect/command times, internal temperature, connection status and Bluetooth uplink
- ✅ **Dashboard Card** - A tile card in polished aluminum, rusted steel or The Lampster's own Army, Artsy and Color finishes, with rivets or screws; included, with nothing else to install
- ✅ **Local Control** - No cloud required

## Requirements

- Home Assistant 2024.12 or newer (2026.3+ to show the integration's own icon)
- The Lampster phone app must not be connected: The Lampster accepts one Bluetooth connection, so use either the app or Home Assistant
- Bluetooth adapter with BLE support
- Python 3.11 or newer
- The Lampster (Model: LA-2017B)

## Installation

### Method 1: HACS (Recommended)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

1. Ensure [HACS](https://hacs.xyz/) is installed
2. In Home Assistant, open **HACS**
3. Click the **⋮** menu (top right) → **Custom repositories**
4. Repository: `https://github.com/yamanote1138/lampster-ha-integration`
5. Type: **Integration**, then click **Add**
6. Search HACS for "The Lampster", open it and click **Download**
7. Restart Home Assistant
8. Go to **Settings** → **Devices & Services** → **Add Integration**
9. Search for "The Lampster" and follow the setup flow

### Method 2: Manual Installation

1. Copy the `custom_components/lampster` directory to your Home Assistant `config/custom_components/` directory:

   ```bash
   # On your HA machine
   cd /config
   mkdir -p custom_components
   cp -r /path/to/lampster-ha-integration/custom_components/lampster custom_components/
   ```

2. Restart Home Assistant

3. Go to **Settings** → **Devices & Services** → **Add Integration**

4. Search for "The Lampster" and follow the setup flow

## Configuration

### Automatic Discovery

The integration will automatically discover The Lampster via Bluetooth. When it is found, you will see a notification in Home Assistant to set it up.

### Manual Setup

1. Navigate to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "The Lampster"
4. Select your device from the list
5. Click **Submit**

The integration will create a light entity named `light.lampster`.

### Connection Settings

Go to **Settings** → **Devices & Services** → **The Lampster** → **Configure**. The timing settings appear on a second step, only when *Maintain Bluetooth connection at all times* is unchecked:

| Setting | Default | Meaning |
|---------|---------|---------|
| Maintain Bluetooth connection at all times | Off | Keep the Bluetooth connection active even while The Lampster is off, so commands are more responsive. Permanently ties up one of the connection slots on your Bluetooth adapter or proxy (ESPHome Bluetooth proxies have 3 by default). |
| Check interval | 30 s | While The Lampster is off and disconnected, how often Home Assistant briefly connects to check whether it was turned on with the touch button |
| Connection hang-on time | 60 s | How long the connection remains active after The Lampster is turned off |

## Usage

### Via UI

Use the standard Home Assistant light controls:

- **Power**: Toggle on/off
- **Brightness**: Slide to adjust (0-100%)
- **Color**: RGB color picker
- **Temperature**: Warm to cool white slider

### Effects and transitions

Effects are chosen from the light card or with `light.turn_on`:

| Effect | Description |
|--------|-------------|
| Color Loop | Cycles through all colors, once a minute |
| Random | A different color every 5 seconds |
| Candle | Warm white with an irregular flicker |
| Fireplace | Red and orange embers that flare and fade |
| Breathe | The current color slowly brightens and dims |

The Lampster has no built-in effects or fades, so Home Assistant sends each step over the Bluetooth connection. Any other command, turning it off, or pressing the touch button stops an effect. In color mode, The Lampster's touch button switches to white instead of turning off, so a tap during a color effect or fade turns The Lampster off; holding the button instead stops the effect and dims in white.

Transitions fade over the given number of seconds:

```yaml
action: light.turn_on
target:
  entity_id: light.lampster
data:
  color_temp_kelvin: 2700
  brightness_pct: 100
  transition: 600  # 10 minute wake-up
```

### Dashboard card

The integration includes a dashboard card, so there is nothing else to install. To add it, edit a dashboard, select **Add card**, and search for **The Lampster**.

The card is Home Assistant's tile card in a finish of your choice. Every tile card option works the same way and appears in the same editor: name, state content, tap and hold actions, and features such as the brightness slider. Below them, the **The Lampster style** panel sets the finish:

- **Collection** and **Style**: Metal (Polished Aluminum, Brushed Aluminum, Rusted Steel, or Painted in any color), Lampster Army, Lampster Artsy or Lampster Color. Collection **None** keeps your theme's own tile card and adds only the head, in a **Head color** of your choice, and the fasteners
- **Randomize**: draws new reflections, rust, wear, splatter or sheen and keeps every other setting (every style except Brushed Aluminum)
- **Features style**: the slider and other features sit on the style itself (Match style), on a flat patch of the style's base color without rust, wear or splatter (Flat), or in a channel pressed into the panel (Channel), where a slider keeps its shape, the channel follows its curve, and its bar looks like a slatted roll-up door
- **Fasteners**: Rivets, Phillips, Hex, Socket or None, matching the style or in any color
- **Fastener spacing**: Corners only, or fasteners all the way around at 1/2, 1/4, 1/8, 1/16, 1/32 or 1/64 spacing. The "+ ends" choices (and Ends) put one fastener at each end of a single-row card instead of in its corners. Fasteners that would touch the head or the features are left out

The color pickers list the theme colors (such as Teal or Amber). For any other color, type it into the picker as a CSS color, such as `#1f6f78`, `rgb(31, 111, 120)` or a color name like `goldenrod`, and select **Custom color**.

The card's edge is drawn as a slightly raised panel. The tile card's Icon and Show entity picture options are left out of the editor, because the card shows the head there.

In place of the tile card's icon, the card shows The Lampster's head, with the light's current color in the lens.

```yaml
type: custom:lampster-card
entity: light.the_lampster
features:
  - type: light-brightness
# The Lampster style (all optional)
style: rusted              # see the list below
pattern: 4242              # the reflections, rust, wear, splatter or sheen pattern
features_style: match      # match, flat or channel
head_color: light-grey     # for style: none; a theme color or any CSS color
fasteners: rivets          # rivets, phillips, hex, socket or none
fastener_color: match      # match, a theme color such as amber, or any CSS color
fastener_spacing: 4        # 0 (corners), 2, 4, 8, 16, 32 or 64; add E (such as 4E) for ends on a single row
paint_color: teal          # for style: painted; a theme color or any CSS color
```

| Option | Values | Default |
|--------|--------|---------|
| `style` | `none` (your theme's tile card), `polished`, `brushed`, `rusted`, `painted`, `army_black`, `army_blue`, `army_gold`, `army_green`, `army_red`, `army_white`, `artsy_black`, `artsy_gold`, `artsy_green`, `artsy_red`, `artsy_white`, `color_black`, `color_blue`, `color_gold`, `color_green`, `color_red` | `polished` |
| `paint_color` | For `painted`: a theme color such as `teal`, or any CSS color such as `"#1f6f78"` | `teal` |
| `head_color` | For `none`: the head's color, as a theme color or any CSS color | `light-grey` |
| `pattern` | Any whole number; each number draws a different pattern | The default look |
| `fasteners` | `rivets`, `phillips`, `hex`, `socket`, `none` | `rivets` |
| `fastener_color` | `match` (follows the style), a theme color such as `amber`, or any CSS color | `match` |
| `fastener_spacing` | How many gaps each long edge is divided into: `0` (corners only), `2`, `4`, `8`, `16`, `32`, `64`. Add `E` (such as `4E`, or `0E` for ends only) to put one fastener at each end of a single-row card instead of in its corners | `4` |
| `features_style` | `match` (the style itself), `flat` (the style's base color only) or `channel` (a channel pressed into the panel) | `match` |

The editor writes every option the chosen style uses into the YAML, defaults included. All other options are the [tile card's](https://www.home-assistant.io/dashboards/tile/). The tile card's `icon` and `show_entity_picture` options have no effect, because the head is shown there.

### Via Automations

```yaml
# Turn on with specific RGB color
service: light.turn_on
target:
  entity_id: light.lampster
data:
  rgb_color: [255, 0, 0]  # Red
  brightness: 200

# Set color temperature (warm white)
service: light.turn_on
target:
  entity_id: light.lampster
data:
  color_temp_kelvin: 2700
  brightness: 150

# Turn off
service: light.turn_off
target:
  entity_id: light.lampster
```

### Via Scripts

```yaml
# script.yaml
lampster_red:
  alias: "The Lampster: Red"
  sequence:
    - service: light.turn_on
      target:
        entity_id: light.lampster
      data:
        rgb_color: [255, 0, 0]
        brightness: 255

lampster_warm_white:
  alias: "The Lampster: Warm White"
  sequence:
    - service: light.turn_on
      target:
        entity_id: light.lampster
      data:
        color_temp_kelvin: 2700
        brightness: 200
```

## Technical Details

### BLE Protocol

Protocol based on reverse engineering by [Noki](https://github.com/Noki/the-lampster).

**Device Information:**
- Model: LA-2017B
- Manufacturer: The Lampster
- Hardware: 100B
- Firmware: 10

**BLE Characteristics:**
- Mode: `01ff5554-ba5e-f4ee-5ca1-eb1e5e4b1ce0` (Handle 0x0020)
- RGB: `01ff5559-ba5e-f4ee-5ca1-eb1e5e4b1ce0` (Handle 0x0029)
- White: `01ff5556-ba5e-f4ee-5ca1-eb1e5e4b1ce0` (Handle 0x0024)

### Color Conversions

**RGB Mode:**
- Home Assistant: 0-255 per channel
- Device: 0-100 per channel
- Brightness scaling applied during conversion

**Color Temperature Mode:**
- Home Assistant: Kelvin (2700K - 6500K)
- Device: Warm/cold percentage (0-100 each)
- Lower Kelvin = warmer = more warm LED
- Higher Kelvin = cooler = more cold LED
- The ratio of warm to cold sets the color temperature; brightness sets the stronger of the two LEDs, so 100% at a mid temperature drives both LEDs fully
- Holding the touch button raises or lowers both LEDs by the same amount (one step at a time, about 10 steps per second). Going down, it stops when the dimmer LED reaches its lowest step; going up, it stops when the brighter LED reaches full
- Because both LEDs change by the same amount, the color shifts during a hold: brightening pulls the color toward the middle (about 4600 K) and dimming pushes it back toward the end it started from. For example, warm white at warm 50 / cold 1 (about 2770 K) brightens to warm 100 / cold 51 (about 4000 K), and cool white at warm 0 / cold 53 brightens to warm 48 / cold 100 (about 5300 K). Home Assistant shows this shift because it is what The Lampster is doing
- An LED that reaches zero while dimming stays at zero while the other keeps dimming, so dimming all the way down and back up with the touch button ends near 4600 K whatever color temperature was set. At 1% there is no room left for a color temperature, so after dimming to 1% in Home Assistant the touch button brightens every white the same way
- Brightness changes made from Home Assistant keep the warm/cold ratio, so the color temperature stays the same while dimming

### Connection Handling

- **While The Lampster is on**, Home Assistant stays connected. The Lampster pushes every change over the connection, including touch button taps and holds, so they show up instantly
- **After it turns off**, the connection stays open for the configured time (default 60 s), then closes
- **While off and disconnected**, Home Assistant connects every check interval (default 30 s) to see whether The Lampster was turned on with the touch button, and stays connected if so. The Lampster's Bluetooth advertisement does not include its state, so this is the only way to notice
- **Commands from Home Assistant** connect on demand (1-3 s through a proxy); after that the connection stays open while The Lampster is on
- Dropped connections are re-established automatically while The Lampster is on
- While a command is being sent, newer requests replace queued ones, so dragging a color picker sends only the latest color
- Mode changes that The Lampster rejects while it is still processing a previous one (for example, right after powering on) are retried after a short pause
- Bursts of touch-button updates (a hold sends several per second) are batched into one state update

### Diagnostic Entities

Found on the device page under **Diagnostic**. Signal strength, Connect time, Command time and Internal temperature are disabled by default; enable them from the entity settings when needed.

| Entity | Meaning |
|--------|---------|
| Signal strength | RSSI of the last advertisement (dBm) |
| Connect time | How long the last BLE connection took to establish (ms) |
| Command time | How long the last command took once connected (ms) |
| Internal temperature | Temperature reported by The Lampster about every 5 s while connected (°C); probably the LEDs or circuit board |
| Bluetooth uplink | Bluetooth adapter or proxy that last heard The Lampster, by its name in Home Assistant |
| Connection | Connection status in one word (see below) |

## Troubleshooting

### Integration does not appear

1. Check that Bluetooth is enabled in Home Assistant
2. Ensure the device is powered on and nearby (< 2m recommended)
3. Check Home Assistant logs: **Settings** → **System** → **Logs**
4. Look for errors containing "lampster"

### Dashboard card shows "Custom element does not exist"

The integration loads the card on every dashboard by itself. If a dashboard was already open when Home Assistant started or the integration was updated, reload the page. In the Home Assistant Companion app, use **Reset frontend cache** in the app's settings.

### Device not discovered

1. Ensure The Lampster advertises a Bluetooth name containing "Lamp" (it should be "Lampster")
2. Check Bluetooth range - move device closer
3. Power cycle the device
4. Restart Home Assistant

### Connection issues

1. Only one Bluetooth connection at a time - close the official app
2. Power cycle the device
3. Check Home Assistant logs for specific errors
4. Ensure no other integrations are using the device

### Colors not changing

1. Verify device is connected (check entity state)
2. Power cycle the device
3. Remove and re-add the integration
4. Check debug logs for BLE errors

### Understanding connection behavior

The **Connection** diagnostic sensor shows what the connection is doing:

| Status | Meaning |
|--------|---------|
| Connected | Holding the connection: The Lampster is on, or *Maintain Bluetooth connection at all times* is enabled |
| Standby | The Lampster is off; the connection is held until the *Connection hang-on time* runs out |
| Connecting | Connecting for a command or a reconnect |
| Checking | Briefly connecting to check whether The Lampster was turned on with the touch button (only when *Maintain Bluetooth connection at all times* is disabled) |
| Reconnecting | The connection dropped unexpectedly; a new attempt is scheduled in 5 seconds |
| Failed | The last connection attempt or command failed; cleared by the next attempt |
| Disconnected | Not connected, nothing pending |

If The Lampster is unplugged or out of range, the sensor is unavailable.

Expected behavior with the default settings:

- It shows **Connected for as long as The Lampster is on**, however long ago the last command was
- The 60 second **Standby** countdown starts when The Lampster is **turned off** (from Home Assistant or the touch button), not after the last command
- While The Lampster is off, it shows **Checking** for a few seconds every 30 seconds, then **Disconnected**. Each check adds two history entries; to keep them out of the recorder, exclude the sensor in `configuration.yaml`:

  ```yaml
  recorder:
    exclude:
      entities:
        - sensor.lampster_connection
  ```

To see exactly why it connects and disconnects, enable debug logging (below). Each connection and disconnection is logged with its reason, for example:

```
Connecting (check interval)
Connected in 1843 ms (check interval), lamp state: State(off)
Disconnecting (check found lamp off)
Connecting (command set_rgb_color)
Lamp turned off; disconnecting in 60 s unless it is turned back on
Disconnecting (lamp off for 60 s)
Connection dropped unexpectedly; reconnecting in 5 s
```

### Download diagnostics

**Settings** → **Devices & Services** → **The Lampster** → **⋮** → **Download diagnostics** saves one file with the connection settings, connection status, firmware versions, recent connection events and the last error. The Bluetooth address of The Lampster is removed from the file.

### Repair notices

If Home Assistant fails to connect to The Lampster 5 times in a row, a repair notice appears under **Settings** → **Repairs**. A separate notice explains when every Bluetooth connection slot that can reach The Lampster is in use. Both clear themselves once a connection succeeds.

When the Lampster app is connected, The Lampster stops advertising, so Home Assistant sees it as unavailable (the same as when it is unplugged) rather than raising a notice.

### Enable Debug Logging

Easiest: **Settings** → **Devices & Services** → **The Lampster** → **⋮** → **Enable debug logging**. Reproduce the behavior, then choose **Disable debug logging**; Home Assistant downloads the log file.

To keep debug logging on across restarts, add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.lampster: debug
    lampster: debug
```

Then restart Home Assistant.

## Known Limitations

1. **Single Connection**: The Lampster accepts one Bluetooth connection at a time, so the Lampster app and Home Assistant cannot be used together
2. **Touch Button While Off**: With the default settings, turning The Lampster on with the touch button is noticed at the next check (within the check interval). Enable *Maintain Bluetooth connection at all times* to make it instant
3. **State Persistence**: Device remembers last color even when powered off
4. **Range**: Bluetooth LE has limited range (~10m line of sight, less through walls)
5. **Power Off from RGB**: Requires switching to white mode first (handled automatically)

## Development

### Project Structure

```
custom_components/lampster/
├── __init__.py          # Integration setup
├── card.py             # Serves the dashboard card
├── frontend/
│   └── lampster-card.js # The dashboard card
├── manifest.json        # Integration metadata
├── const.py            # Constants
├── config_flow.py      # Discovery and config UI
├── light.py            # Light entity implementation
├── strings.json        # UI strings
└── translations/
    └── en.json         # English translations
```

### Core Library

The integration uses the `lampster` Python library for BLE communication. See the main README for library documentation.

### Testing

Automated tests live in `tests/automated/` and run on GitHub for every push, together with Home Assistant's `hassfest` and the HACS validation. To run them locally (Python 3.14):

```bash
pip install pytest-homeassistant-custom-component
pytest
```

The other scripts in `tests/` control a real lamp and are run by hand, for example `python tests/probe_button.py`.

Manual checks in Home Assistant:

1. Enable debug logging (see above)
2. Monitor logs: `tail -f /config/home-assistant.log | grep lampster`
3. Test basic operations: on/off, RGB colors, white temperatures
4. Test automations and scripts
5. Test device reconnection (power cycle device)

## Attribution

All BLE protocol information based on reverse engineering by **[Noki](https://github.com/Noki/the-lampster)**.

## License

MIT License - See LICENSE file for details

## Support

- **Issues**: [GitHub Issues](https://github.com/yamanote1138/lampster-ha-integration/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yamanote1138/lampster-ha-integration/discussions)
- **Protocol Documentation**: [Noki's the-lampster](https://github.com/Noki/the-lampster)
