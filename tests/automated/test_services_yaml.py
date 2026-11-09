"""Check services.yaml against Home Assistant's selector rules and the effect list."""

from pathlib import Path

import yaml
from homeassistant.helpers import selector

from custom_components.lampster.effects import EFFECTS

SERVICES = Path(__file__).parents[2] / "custom_components/lampster/services.yaml"


def test_selectors_are_valid() -> None:
    """Home Assistant can read every selector (it ignores the whole file otherwise)."""
    for service in yaml.safe_load(SERVICES.read_text()).values():
        for field in (service.get("fields") or {}).values():
            selector.validate_selector(field["selector"])


def test_effect_options_match_effects() -> None:
    """The Start effect dropdown lists exactly the effects the action accepts."""
    services = yaml.safe_load(SERVICES.read_text())
    options = services["start_effect"]["fields"]["effect"]["selector"]["select"]["options"]
    assert options == list(EFFECTS)
