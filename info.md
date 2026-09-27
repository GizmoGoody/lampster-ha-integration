{% if installed %}
## Changes in version {{version}}

{% if version_installed.replace("v", "").replace(".","") | int < 110  %}
### What is new in v1.1.0

- ✅ **Setup fixed** - The Lampster sets up again on current Home Assistant versions (issue #1)
- ✅ **Instant touch button sync** - Taps and holds on The Lampster show up in Home Assistant right away
- ✅ **Responsive control** - One shared connection; dragging the color wheel is smooth
- ✅ **Connection settings** - Keep the connection at all times, or set the check interval and hang-on time
- ✅ **Effects and transitions** - Color Loop, Random, Candle, Fireplace and Breathe; fades on, off and between colors
- ✅ **Brighter whites** - 100% now drives both LEDs fully at in-between color temperatures
- ✅ **Favorite colors** - Pure colors and ten white temperatures added to the color picker
- ✅ **Diagnostics** - Connection status, Bluetooth uplink, timing, temperature, diagnostics download and repair notices

{% endif %}
{% endif %}

## About

Control The Lampster, an RGB Bluetooth lamp (Model: LA-2017B), directly from Home Assistant.

### Features

- 🎨 **RGB Color Picker** - Choose any color
- 🌡️ **Color Temperature** - Warm white (2700K) to cool white (6500K)
- 💡 **Brightness** - Adjust light intensity 0-100%
- 🔵 **Auto-Discovery** - Automatically finds The Lampster
- ⏱️ **Manual Button Detection** - Syncs when you use the physical button
- 📊 **Device Info** - Shows model and manufacturer in device page

### Supported Devices

- The Lampster (Model: LA-2017B)
- Hardware Revision: 100B
- Firmware: 10

### Requirements

- Home Assistant 2024.12 or newer
- Bluetooth adapter with BLE support (built-in or USB dongle)
- The Lampster within Bluetooth range (~10m)

### Setup

After installation:

1. Go to **Settings** → **Devices & Services**
2. If auto-discovery worked, click **Configure** on the discovered The Lampster entry
3. If not, click **Add Integration** and search for "The Lampster"
4. Select your device from the list
5. The light entity will be added: `light.lampster`

### Usage

Control the light like any other HA light:

- Use the light controls in the UI
- Create automations with color/brightness changes
- Use with voice assistants (Alexa, Google Home, Siri via HomeKit)
- Include in scenes and scripts

### Known Limitations

- Only one Bluetooth connection at a time (close official app if connected)
- The Lampster app and Home Assistant cannot be connected at the same time; use one or the other
- ~10m range depending on environment
- While The Lampster is off, turning it on by touch is noticed within the check interval (default 30 seconds) unless *Maintain Bluetooth connection at all times* is enabled

### Support

- **Issues**: [GitHub Issues](https://github.com/yamanote1138/lampster-ha-integration/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yamanote1138/lampster-ha-integration/discussions)

### Credits

Protocol documentation based on reverse engineering by [Noki](https://github.com/Noki/the-lampster).
