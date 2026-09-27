# The Lampster - Home Assistant Integration

## Project Overview

This project provides a Home Assistant custom integration for controlling The Lampster RGB Bluetooth lamp. The project is developed in two phases:

1. **Phase 1**: Local testing scripts on macOS using `uv` for dependency management
2. **Phase 2**: Full Home Assistant custom integration

## Attribution

**IMPORTANT**: All protocol information is based on [Noki's reverse engineering work](https://github.com/Noki/the-lampster). This attribution must be maintained in all documentation, code comments, and public communications about this project.

## Project Structure

```
lampster-ha-integration/
├── lampster/                          # Core Python library
│   ├── __init__.py                   # Package exports
│   ├── client.py                     # LampsterClient - main BLE control class
│   ├── constants.py                  # BLE UUIDs, characteristics, commands
│   ├── models.py                     # RGBColor, WhiteColor, LampState models
│   └── exceptions.py                 # Custom exception classes
│
├── tests/                             # Phase 1: Local testing scripts
│   ├── test_discovery.py             # Device discovery and UUID enumeration
│   ├── test_power.py                 # Power on/off testing
│   ├── test_rgb.py                   # RGB color control testing
│   ├── test_white.py                 # White temperature testing
│   └── test_all_modes.py             # Comprehensive functionality test
│
├── custom_components/lampster/        # Phase 2: Home Assistant integration
│   ├── manifest.json                 # Integration metadata
│   ├── __init__.py                   # Integration entry point
│   ├── config_flow.py                # Device discovery & configuration UI
│   ├── light.py                      # Light entity implementation
│   ├── const.py                      # HA-specific constants
│   ├── strings.json                  # UI strings for config flow
│   └── translations/en.json          # English translations
│
├── pyproject.toml                     # uv/pip project configuration
├── .gitignore                         # Git ignore patterns
├── README.md                          # User-facing documentation
├── CLAUDE.md                          # This file - AI assistant context
└── LICENSE                            # Project license (MIT)
```

## Technology Stack

- **Language**: Python 3.11+
- **Package Manager**: uv (local dev) / pip (HA integration)
- **BLE Library**: bleak (cross-platform Bluetooth Low Energy)
- **Target Platform**: Home Assistant 2024.1+
- **Development Platform**: macOS (Phase 1), Linux (Phase 2)

## Development Workflow

### Phase 1: Local Testing

Phase 1 focuses on validating the BLE protocol using local test scripts on macOS.

**Setup**:
```bash
cd /Users/spitfire/Projects/lampster-ha-integration
uv sync
```

**Testing Workflow**:
1. Run `uv run tests/test_discovery.py` to find device address
2. Update `DEVICE_ADDRESS` in all test files
3. Run individual tests: `test_power.py`, `test_rgb.py`, `test_white.py`
4. Run comprehensive test: `test_all_modes.py`
5. Document any protocol deviations in issues/notes

**Key Considerations**:
- Characteristic UUIDs in `constants.py` may need adjustment based on device
- Use characteristic enumeration in `test_discovery.py` to validate UUIDs
- Keep lamp within 2 meters during testing
- BLE connections can be flaky - retry if needed

### Phase 2: Home Assistant Integration

Phase 2 builds on the validated core library to create a full HA integration.

**Setup**:
1. Copy `custom_components/lampster/` to HA config directory
2. Ensure `lampster/` core library is importable
3. Restart Home Assistant
4. Add integration via UI: Settings → Devices & Services → Add Integration

**Implementation Priority**:
1. `manifest.json` - Integration metadata
2. `const.py` - Constants
3. `__init__.py` - Setup entry point
4. `config_flow.py` - Device discovery UI
5. `light.py` - Light entity with RGB and color temp support
6. `strings.json` - UI translations

## Code Conventions

### Python Style
- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Document all public APIs with docstrings
- Keep functions focused and modular

### Naming Conventions
- Classes: `PascalCase` (e.g., `LampsterClient`, `RGBColor`)
- Functions/methods: `snake_case` (e.g., `set_rgb_color`, `power_on`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MODE_POWER_ON`, `CHAR_RGB`)
- Private members: `_leading_underscore` (e.g., `_client`, `_write_mode`)

### BLE Protocol Constants
All BLE-related constants live in `lampster/constants.py`:
- Characteristic UUIDs: `CHAR_MODE`, `CHAR_RGB`, `CHAR_WHITE`
- Mode commands: `MODE_POWER_ON`, `MODE_POWER_OFF`, etc.
- Value ranges: `MIN_VALUE`, `MAX_VALUE`

### Error Handling
- Use custom exceptions from `lampster/exceptions.py`
- `ConnectionError` - BLE connection issues
- `CommandError` - Command execution failures
- `DiscoveryError` - Device discovery failures
- Always provide context in exception messages

### State Management
The Lampster doesn't support reading state, so:
- Track state locally in `LampState` dataclass
- State is optimistic (not verified by device)
- Document this limitation in code comments
- Consider implementing state refresh commands

## Testing Strategy

### Phase 1 Testing
- **Manual testing** using test scripts
- Validate each function: discovery, power, RGB, white
- Test mode switching (RGB ↔ white)
- Test edge cases (min/max values, rapid changes)
- Document findings in git commit messages

### Phase 2 Testing
- **Integration testing** in Home Assistant
- Test config flow (discovery, setup, errors)
- Test light entity (on/off, colors, brightness)
- Test automations with the light
- Test reconnection after power cycle
- Verify no errors in HA logs

## Version Management

This project uses semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes to API or HA integration
- **MINOR**: New features, non-breaking changes
- **PATCH**: Bug fixes, documentation updates

### Current Version: 1.1.0
- Phase 1 and Phase 2 complete
- Fixes setup on current Home Assistant (issue #1)
- Stays connected while on; touch button changes arrive as notifications
- Options flow for connection behavior; effects; transitions; diagnostics
  and repairs; automated tests (tests/automated) and GitHub Actions
- See README.md for the full feature list and protocol notes

### Version History
See git tags for version history:
```bash
git tag -l -n9
```

### Creating a Release
1. Update version in `pyproject.toml`
2. Update version in `lampster/__init__.py`
3. Update version in `custom_components/lampster/manifest.json` (Phase 2)
4. Update CHANGELOG.md (when created)
5. Commit: `git commit -m "chore: bump version to X.Y.Z"`
6. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
7. Push: `git push && git push --tags`

## Git Workflow

### Branch Strategy
- `main` - stable, tested code
- `develop` - integration branch for features
- `feature/*` - individual features
- `bugfix/*` - bug fixes

### Commit Message Format
Follow conventional commits:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

**Examples**:
```
feat(client): add RGB color control
fix(discovery): handle devices without names
docs(readme): add troubleshooting section
test(rgb): add edge case tests for color values
```

### Commit Conventions
- Keep commits atomic and focused
- Write clear, descriptive commit messages
- Reference issues: `fixes #123`, `closes #456`
- Sign commits if possible

## Dependencies

### Runtime Dependencies
- `bleak>=0.21.0` - BLE library for Python

### Development Dependencies (Optional)
- `pytest>=7.4.0` - Testing framework
- `black>=23.0.0` - Code formatting
- `ruff>=0.1.0` - Linting

### Installation
```bash
# Runtime only
uv sync

# With dev dependencies
uv sync --all-extras
```

## Protocol Details

### BLE Characteristics
Based on [Noki's documentation](https://github.com/Noki/the-lampster):

| Characteristic | Handle | UUID Pattern | Function |
|----------------|--------|--------------|----------|
| Mode Control | 0x0021 | 0000ffe9-... | Power, mode selection |
| RGB Control | 0x002a | 0000ffeb-... | RGB LED control |
| White Control | 0x0025 | 0000ffea-... | Warm/cold white control |

**Note**: UUIDs are estimated based on common patterns. Actual UUIDs may vary by device and should be validated using the characteristic enumeration feature in `test_discovery.py`.

### Command Format

**Mode Control** (1 byte):
- `0xC0` - Power on
- `0x40` - Power off
- `0xA8` - RGB mode
- `0xC8` - White mode
- `0x28` - Off mode

**RGB Control** (3 bytes):
- Format: `[RR, GG, BB]`
- Range: 0x00-0x64 (0-100 per channel)

**White Control** (2 bytes):
- Format: `[WW, CC]`
- Range: 0x00-0x64 (0-100 per value)
- WW = Warm white intensity
- CC = Cold white intensity

## Known Issues & Limitations

### Current Limitations
1. **No state reading**: Device doesn't support reading current state
   - State is tracked locally in the client
   - Power cycles lose state synchronization

2. **Optimistic updates**: HA entity assumes commands succeed
   - No verification from device
   - Consider adding command confirmation

3. **Connection reliability**: BLE can be flaky
   - May need retry logic
   - Keep device close during operation

4. **UUID variability**: Characteristic UUIDs may vary by device
   - Validate UUIDs using test_discovery.py
   - Update constants.py if needed

### Future Improvements
- [ ] Add automatic reconnection logic
- [ ] Implement connection retry with exponential backoff
- [ ] Add state refresh command (reapply last known state)
- [ ] Support multiple Lampster devices
- [ ] Add effects/animations (if supported by device)
- [ ] Improve error messages and user feedback

## Home Assistant Integration (Phase 2)

### Config Flow
- Automatic discovery via Bluetooth integration
- Manual setup with device selection
- Unique ID based on MAC address (prevents duplicates)
- Error handling for connection failures

### Light Entity
- **Supported Features**:
  - On/Off control
  - RGB color (0-255 → 0-100 conversion)
  - Color temperature (mireds → warm/cold ratio)
  - Brightness (0-255 → scaled with color)

- **Color Modes**:
  - `ColorMode.RGB` - RGB color control
  - `ColorMode.COLOR_TEMP` - White temperature control

- **State Management**:
  - Optimistic updates (no read capability)
  - Local state tracking
  - Available property based on connection status

### Integration Requirements
- Home Assistant 2024.1+
- Bluetooth integration enabled
- Bluetooth adapter on HA host
- Python 3.11+

## Troubleshooting

### Discovery Issues
- Ensure lamp is powered on
- Keep lamp within 2m of Bluetooth adapter
- Check Bluetooth is enabled
- Try power cycling the lamp
- Check system Bluetooth isn't blocking scans

### Connection Issues
- Verify device address is correct
- Unpair device from system Bluetooth if previously paired
- Check signal strength (RSSI in discovery)
- Try power cycling the lamp
- Verify no other apps are connected

### Command Issues
- Check connection is established first
- Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
- Verify characteristic UUIDs match device
- Check for BLE permissions on macOS
- Try re-establishing connection

### UUID Mismatches
1. Run `test_discovery.py` with characteristic enumeration enabled
2. Compare actual UUIDs with those in `constants.py`
3. Update `CHAR_MODE`, `CHAR_RGB`, `CHAR_WHITE` if different
4. Document changes in commit message

## Resources

### Documentation
- [Noki's Protocol Documentation](https://github.com/Noki/the-lampster) - BLE protocol
- [Home Assistant Developer Docs](https://developers.home-assistant.io/) - HA integration development
- [Bleak Documentation](https://bleak.readthedocs.io/) - Python BLE library

### Community
- Home Assistant Community Forums
- Home Assistant Discord
- GitHub Issues (this repository)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Follow code conventions and style
4. Add tests for new functionality
5. Update documentation as needed
6. Maintain Noki attribution in protocol-related code
7. Submit a pull request with clear description

### Before Submitting
- [ ] Code follows project conventions
- [ ] Tests pass (Phase 1 test scripts work)
- [ ] Documentation updated
- [ ] Commit messages follow conventional format
- [ ] Attribution maintained

## License

MIT License (see LICENSE file)

## Contact & Support

- **Issues**: GitHub Issues
- **Protocol Questions**: See [Noki's repository](https://github.com/Noki/the-lampster)
- **HA Questions**: [Home Assistant Community](https://community.home-assistant.io)

---

**Last Updated**: 2026-09-27
**Project Phase**: Phase 2 complete - Home Assistant integration
**Current Version**: 1.1.0
