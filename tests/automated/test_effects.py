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
    Step,
    effect_steps,
    scale_steps,
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
        assert all(0 <= value <= 100 for value in color_values(step.color))


def _spin_colors(effect: str, count: int) -> list[RGBColor]:
    return [step.color for step in itertools.islice(effect_steps(effect, 255, None), count)]


def test_spin_directions() -> None:
    """Spin lights one color at a time: red, blue, green counterclockwise."""
    red, green, blue = RGBColor(100, 0, 0), RGBColor(0, 100, 0), RGBColor(0, 0, 100)
    assert _spin_colors("spin_ccw", 4) == [red, blue, green, red]
    assert _spin_colors("spin_cw", 4) == [red, green, blue, red]


def test_spin_alternating_changes_direction() -> None:
    """Spin Alternating turns one way, then the other."""
    red, green, blue = (100, 0, 0), (0, 100, 0), (0, 0, 100)
    ccw_next = {red: blue, blue: green, green: red}
    cw_next = {after: before for before, after in ccw_next.items()}
    per_direction = round(effects.SPIN_ALTERNATE_AFTER / effects.SPIN_STEP)
    colors = [color_values(c) for c in _spin_colors("spin_alternating", per_direction * 3)]
    for i in range(1, len(colors)):
        # Each step moves the way the previous step's direction pointed
        expected = ccw_next if ((i - 1) // per_direction) % 2 == 0 else cw_next
        assert colors[i] == expected[colors[i - 1]], i


def test_fireworks_bursts_are_spaced() -> None:
    """Fireworks shells launch dimly, then burst in a firework color at least 0.9 s apart."""
    random.seed(1)
    colors = (*effects.FIREWORKS_COLORS, effects.FIREWORKS_GOLD)
    now, last_start, previous, starts, launches = 0.0, None, 0, 0, 0
    for step in itertools.islice(effect_steps("fireworks", 255, None), 5000):
        values = color_values(step.color)
        brightest = max(values)
        if 0 < previous < 25 and 0 < brightest < 25:
            launches += 1  # a dim rising trail before a burst
        if brightest > 50 and previous < 40:
            if last_start is not None:
                assert now - last_start >= 0.9 - 1e-9
            last_start = now
            starts += 1
            assert any(
                all(abs(v - c * brightest / 100) <= 1 for v, c in zip(values, color))
                for color in colors
            )
        previous = brightest
        now += step.delay
    assert starts > 100
    assert launches > starts


def test_pursuit_alternates_slowly() -> None:
    """Pursuit alternates red and blue, changing color twice a second."""
    steps = list(itertools.islice(effect_steps("pursuit", 255, None), 12))
    assert sum(step.delay for step in steps[:3]) == pytest.approx(0.5)
    reds = {color_values(step.color)[0] > 0 for step in steps[:3]}
    blues = {color_values(step.color)[2] > 0 for step in steps[3:6]}
    assert reds == {True} and blues == {True}
    assert color_values(steps[1].color) == (100, 0, 0)


def test_scale_steps_speed() -> None:
    """Effect speed scales step times, never shorter than 0.1 s when sped up."""
    steps = [Step(RGBColor(1, 0, 0), 1.0), Step(RGBColor(2, 0, 0), 0.15), Step(RGBColor(3, 0, 0), 0.08)]
    assert [s.delay for s in scale_steps(iter(steps), 100)] == [1.0, 0.15, 0.08]
    assert [s.delay for s in scale_steps(iter(steps), 200)] == [0.5, 0.1, 0.08]
    assert [s.delay for s in scale_steps(iter(steps), 25)] == [4.0, 0.6, 0.32]
    assert [s.color for s in scale_steps(iter(steps), 50)] == [s.color for s in steps]


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
