"""Tests for effects, transitions and color conversions."""
from __future__ import annotations

import itertools
import random

import pytest

from custom_components.lampster.effects import (
    EFFECT_CANDLE,
    EFFECTS,
    MODE_RGB,
    MODE_WHITE,
    color_values,
    current_color,
    effect_mode,
    effect_steps,
    transition_steps,
    zero_color,
)
from custom_components.lampster import effects
from custom_components.lampster.lampster.models import LampState, RGBColor, WhiteColor
from custom_components.lampster.light import (
    _device_to_kelvin,
    _kelvin_to_device,
    _rgb_to_device,
)


def test_transition_reaches_target() -> None:
    """A transition ends exactly on the target over the requested time."""
    steps = transition_steps(WhiteColor(0, 0), WhiteColor(40, 10), 10)
    assert steps[-1].color == WhiteColor(40, 10)
    assert len(steps) <= 40  # never more steps than the largest 1% change
    assert sum(step.delay for step in steps) == pytest.approx(10)


def test_transition_short_duration_is_limited() -> None:
    """Very short transitions do not flood the connection."""
    steps = transition_steps(RGBColor(0, 0, 0), RGBColor(100, 0, 0), 1)
    assert len(steps) <= 4
    assert steps[-1].color == RGBColor(100, 0, 0)


def test_transition_no_change() -> None:
    """A transition to the current color is a single step."""
    assert len(transition_steps(RGBColor(5, 5, 5), RGBColor(5, 5, 5), 3)) == 1


@pytest.mark.parametrize("effect", EFFECTS)
def test_effect_steps_are_valid(effect: str) -> None:
    """Every effect yields colors in range with positive delays."""
    state = LampState(True, "rgb", RGBColor(50, 20, 0), WhiteColor(30, 0))
    for step in itertools.islice(effect_steps(effect, 200, state), 200):
        assert step.delay > 0
        if step.color is not None:  # None: off for the step
            assert all(0 <= value <= 100 for value in color_values(step.color))


def test_fireworks_shells() -> None:
    """Each shell: off 1-5 s, an orange trail ramping from 5% to 20% over 3-5 s,
    a burst at 50% then 80-100% in a firework color, then a fade to off.
    The light's brightness is ignored, and no step is all zero."""
    random.seed(1)
    steps = list(itertools.islice(effect_steps("fireworks", 3, None), 4000))
    assert steps[0].color is None  # starts off
    shells = 0
    i = 0
    while i < len(steps) - 80:
        off = steps[i]
        assert off.color is None and 1.0 <= off.delay <= 5.0
        i += 1
        # Trail: orange from 5% up to 20%, never the red that dimmer orange rounds to
        trail = []
        while max(color_values(steps[i].color)) <= 20:
            red, green, blue = color_values(steps[i].color)
            assert red >= 5 and green >= 2 and blue == 0
            trail.append(steps[i])
            i += 1
        assert 3.0 - 1e-9 <= sum(s.delay for s in trail) <= 5.0 + 1e-9
        assert color_values(trail[-1].color) == (20, 8, 0)
        # Burst: 50%, then the peak, in a firework color
        start, peak = color_values(steps[i].color), color_values(steps[i + 1].color)
        assert max(start) == 50 and 80 <= max(peak) <= 100
        assert any(
            all(abs(v - c * max(peak) / 100) <= 1 for v, c in zip(peak, color))
            for color in effects.FIREWORKS_COLORS
        )
        i += 2
        # Fade: down to off over 1-3 s (including the peak step)
        fade = [steps[i - 1]]
        while steps[i].color is not None:
            assert max(color_values(steps[i].color)) <= max(color_values(fade[-1].color))
            fade.append(steps[i])
            i += 1
        assert 0.8 - 1e-9 <= sum(s.delay for s in fade) <= 3.0 + 1e-9
        shells += 1
    assert shells > 30
    assert all(s.color is None or any(color_values(s.color)) for s in steps)


def test_pursuit_alternates_slowly() -> None:
    """Pursuit alternates red and blue, changing color twice a second."""
    steps = list(itertools.islice(effect_steps("pursuit", 255, None), 12))
    # Starts straight on full red, then fades out
    assert color_values(steps[0].color) == (100, 0, 0)
    assert sum(step.delay for step in steps[:2]) == pytest.approx(0.4)
    # Then each color takes half a second: blue, red, ...
    assert sum(step.delay for step in steps[2:5]) == pytest.approx(0.5)
    assert {color_values(step.color)[2] > 0 for step in steps[2:5]} == {True}
    assert {color_values(step.color)[0] > 0 for step in steps[5:8]} == {True}


def test_effect_modes() -> None:
    """Candle runs in white; color effects in RGB."""
    assert effect_mode(EFFECT_CANDLE, None) == MODE_WHITE
    assert effect_mode("colorloop", None) == MODE_RGB


def test_current_and_zero_color() -> None:
    """The current color is only used when the lamp shows that mode."""
    state = LampState(True, "white", RGBColor(9, 9, 9), WhiteColor(30, 5))
    assert current_color(state, MODE_WHITE) == WhiteColor(30, 5)
    assert current_color(state, MODE_RGB) == zero_color(MODE_RGB)


def test_rgb_to_device_scales_by_brightness() -> None:
    """HA RGB at half brightness maps to half the device range."""
    assert _rgb_to_device((255, 0, 0), 128) == RGBColor(50, 0, 0)


@pytest.mark.parametrize("kelvin", [1000, 2700, 4600, 6500, 9000])
def test_kelvin_to_device_is_clamped(kelvin: int) -> None:
    """Out-of-range color temperatures are clamped, never invalid."""
    color = _kelvin_to_device(kelvin, 255)
    assert max(color.warm, color.cold) == 100


def test_mid_temperature_uses_both_channels_fully() -> None:
    """At the middle temperature, 100% drives both LEDs fully."""
    assert _kelvin_to_device(4600, 255) == WhiteColor(100, 100)


@pytest.mark.parametrize("kelvin", [2700, 3000, 4000, 5000, 6500])
@pytest.mark.parametrize("brightness", [64, 128, 255])
def test_white_round_trip(kelvin: int, brightness: int) -> None:
    """Device values convert back to about the same temperature and brightness."""
    back_kelvin, back_brightness = _device_to_kelvin(_kelvin_to_device(kelvin, brightness))
    assert abs(back_kelvin - kelvin) <= 120
    assert abs(back_brightness - brightness) <= 3


def test_touch_button_extremes() -> None:
    """Values seen from the touch button: (1, 50) and (51, 100)."""
    assert abs(_device_to_kelvin(WhiteColor(1, 50))[1] - 128) <= 1  # 50%
    assert _device_to_kelvin(WhiteColor(51, 100))[1] == 255  # 100%
