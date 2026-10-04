"""Software effects and transitions for The Lampster.

The Lampster has no built-in effects or fades, so Home Assistant sends each
step over the Bluetooth connection. Each effect or transition is a sequence
of Steps: a color for one mode (RGB or white) and how long to hold it.
"""
from __future__ import annotations

from collections.abc import Iterator
import colorsys
from dataclasses import dataclass
import math
import random

from homeassistant.components.light import EFFECT_COLORLOOP, EFFECT_RANDOM

from .lampster.models import LampState, RGBColor, WhiteColor

EFFECT_CANDLE = "candle"
EFFECT_FIREPLACE = "fireplace"
EFFECT_BREATHE = "breathe"
EFFECT_SPIN_CW = "spin_cw"
EFFECT_SPIN_CCW = "spin_ccw"
EFFECT_SPIN_ALTERNATING = "spin_alternating"
EFFECTS = (
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    EFFECT_CANDLE,
    EFFECT_FIREPLACE,
    EFFECT_BREATHE,
    EFFECT_SPIN_CW,
    EFFECT_SPIN_CCW,
    EFFECT_SPIN_ALTERNATING,
)

MODE_RGB = "rgb"
MODE_WHITE = "white"

# Color loop: hue step every COLORLOOP_STEP seconds (full cycle in 60 s)
COLORLOOP_STEP = 1.0
COLORLOOP_HUE_STEP = 6
# Random: a new color every RANDOM_STEP seconds
RANDOM_STEP = 5.0
# Breathe: one full breath every BREATHE_PERIOD seconds
BREATHE_PERIOD = 5.0
BREATHE_STEP = 0.2
BREATHE_MIN = 0.1
# Spin: each LED package has its red, blue and green parts side by side, all
# turned the same way around the ring. Lighting one part at a time moves the
# light in every package a little, so the ring appears to turn. Going
# counterclockwise the order is red, blue, green; reversed it turns clockwise.
SPIN_CCW_ORDER = ((1, 0, 0), (0, 0, 1), (0, 1, 0))
SPIN_STEP = 0.15
# Spin Alternating: change direction after this many seconds
SPIN_ALTERNATE_AFTER = 4.0
# Shortest time between transition steps
TRANSITION_MIN_STEP = 0.25

Color = RGBColor | WhiteColor


@dataclass(frozen=True)
class Step:
    """One color to show, and for how long."""

    color: Color
    delay: float


def _pct(value: float) -> int:
    """Clamp to the device's 0-100 range."""
    return max(0, min(100, round(value)))


def color_values(color: Color) -> tuple[int, ...]:
    """Return the channel values of a color."""
    if isinstance(color, RGBColor):
        return (color.red, color.green, color.blue)
    return (color.warm, color.cold)


def make_color(mode: str, values: tuple[float, ...]) -> Color:
    """Build a color for a mode from channel values."""
    if mode == MODE_RGB:
        return RGBColor(*(_pct(v) for v in values))
    return WhiteColor(*(_pct(v) for v in values))


def zero_color(mode: str) -> Color:
    """Return the darkest color for a mode."""
    return RGBColor(0, 0, 0) if mode == MODE_RGB else WhiteColor(0, 0)


def current_color(state: LampState | None, mode: str) -> Color:
    """Return the color the lamp shows in a mode, or dark if it is not showing it."""
    if state and state.is_on and state.mode == mode:
        color = state.rgb_color if mode == MODE_RGB else state.white_color
        if color is not None:
            return color
    return zero_color(mode)


def effect_mode(effect: str, state: LampState | None) -> str:
    """Return the mode an effect runs in."""
    if effect == EFFECT_CANDLE:
        return MODE_WHITE
    if effect == EFFECT_BREATHE and state and state.is_on and state.mode == MODE_WHITE:
        return MODE_WHITE
    return MODE_RGB


def effect_steps(effect: str, brightness: int, state: LampState | None) -> Iterator[Step]:
    """Yield the steps of an effect forever, at a brightness of 0-255."""
    level = brightness / 255 * 100
    if effect == EFFECT_COLORLOOP:
        hue = random.random()
        while True:
            hue = (hue + COLORLOOP_HUE_STEP / 360) % 1
            yield Step(_hue_color(hue, level), COLORLOOP_STEP)
    elif effect == EFFECT_RANDOM:
        hue = random.random()
        while True:
            # A clearly different color each time
            hue = (hue + random.uniform(0.2, 0.8)) % 1
            yield Step(_hue_color(hue, level), RANDOM_STEP)
    elif effect == EFFECT_CANDLE:
        while True:
            # Warm white with a quick, irregular flicker
            yield Step(
                WhiteColor(_pct(level * random.uniform(0.55, 1.0)), 0),
                random.uniform(0.08, 0.25),
            )
    elif effect == EFFECT_FIREPLACE:
        while True:
            # Red-orange embers that flare and fade
            flame = level * random.uniform(0.5, 1.0)
            yield Step(
                RGBColor(_pct(flame), _pct(flame * random.uniform(0.12, 0.4)), 0),
                random.uniform(0.1, 0.35),
            )
    elif effect == EFFECT_BREATHE:
        mode = effect_mode(effect, state)
        peak = color_values(current_color(state, mode))
        if max(peak) == 0:
            # Nothing showing yet: breathe in warm white or white light
            peak = (level, 0) if mode == MODE_WHITE else (level, level, level)
        t = 0.0
        while True:
            factor = BREATHE_MIN + (1 - BREATHE_MIN) * (
                0.5 - 0.5 * math.cos(2 * math.pi * t / BREATHE_PERIOD)
            )
            yield Step(make_color(mode, tuple(v * factor for v in peak)), BREATHE_STEP)
            t += BREATHE_STEP
    elif effect in (EFFECT_SPIN_CW, EFFECT_SPIN_CCW, EFFECT_SPIN_ALTERNATING):
        clockwise = effect == EFFECT_SPIN_CW
        steps_per_direction = max(1, round(SPIN_ALTERNATE_AFTER / SPIN_STEP))
        index = 0
        count = 0
        while True:
            red, green, blue = SPIN_CCW_ORDER[index]
            yield Step(
                RGBColor(_pct(red * level), _pct(green * level), _pct(blue * level)), SPIN_STEP
            )
            index = (index + (-1 if clockwise else 1)) % len(SPIN_CCW_ORDER)
            count += 1
            if effect == EFFECT_SPIN_ALTERNATING and count % steps_per_direction == 0:
                clockwise = not clockwise
    else:
        raise ValueError(f"Unknown effect: {effect}")


def _hue_color(hue: float, level: float) -> RGBColor:
    """Fully saturated color of a hue at a level of 0-100."""
    r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
    return RGBColor(_pct(r * level), _pct(g * level), _pct(b * level))


def transition_steps(start: Color, target: Color, duration: float) -> list[Step]:
    """Return evenly spaced steps from start to target over duration seconds.

    The device has 1% resolution, so there is no point in more steps than the
    largest channel change.
    """
    mode = MODE_RGB if isinstance(target, RGBColor) else MODE_WHITE
    begin = color_values(start)
    end = color_values(target)
    largest_change = max(abs(e - b) for b, e in zip(begin, end))
    count = max(1, min(largest_change, int(duration / TRANSITION_MIN_STEP)))
    delay = duration / count
    return [
        Step(
            make_color(mode, tuple(b + (e - b) * i / count for b, e in zip(begin, end))),
            delay,
        )
        for i in range(1, count + 1)
    ]
