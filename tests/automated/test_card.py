"""Tests for serving The Lampster dashboard card."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.lampster.card import CARD_FILE, CARD_URL, async_register_card


async def test_card_served_and_loaded(hass: HomeAssistant) -> None:
    """With dashboards: the file is served and loaded with a content hash."""
    hass.config.components.add("frontend")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_url:
        await async_register_card(hass)

    (path,) = hass.http.async_register_static_paths.call_args.args[0]
    assert path.url_path == CARD_URL
    assert Path(path.path) == CARD_FILE and CARD_FILE.is_file()
    url = add_url.call_args.args[1]
    assert url.startswith(f"{CARD_URL}?v=") and len(url) > len(CARD_URL) + 3


async def test_card_skipped_without_frontend(hass: HomeAssistant) -> None:
    """Without dashboards there is nothing to serve, and setup still works."""
    assert "frontend" not in hass.config.components
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_url:
        await async_register_card(hass)
    add_url.assert_not_called()
