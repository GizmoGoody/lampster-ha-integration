"""Serve The Lampster dashboard card.

The card ships with the integration, so it needs no separate install. Its
address includes a hash of the file, so browsers load a changed card at
once instead of an old cached copy.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.core import HomeAssistant

CARD_URL = "/lampster/lampster-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "lampster-card.js"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card file and load it on every dashboard."""
    if "frontend" not in hass.config.components or hass.http is None:
        # No dashboards to serve (for example, in tests)
        return

    # Imported here because the frontend is optional (after_dependencies)
    from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    content = await hass.async_add_executor_job(CARD_FILE.read_bytes)
    version = hashlib.sha256(content).hexdigest()[:12]
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
