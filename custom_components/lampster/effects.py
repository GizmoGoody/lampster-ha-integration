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
EFFECT_FIREWORKS = "fireworks"
EFFECT_PURSUIT = "pursuit"
EFFECTS = (
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    EFFECT_CANDLE,
    EFFECT_FIREPLACE,
    EFFECT_BREATHE,
    EFFECT_FIREWORKS,
    EFFECT_PURSUIT,
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
# Fireworks: each shell launches as a dim orange trail that slowly brightens,
# then bursts at full brightness in a firework color (red, orange, gold,
# green, blue, purple, white) and fades: quickly (peony), changing to a second
# color (color changer), slowly in gold (willow) or with a crackling flicker.
# The launch is a gradual rise, so only the burst flashes, and bursts are at
# least FIREWORKS_MIN_LAUNCH + FIREWORKS_MIN_FADE + one step apart (about a
# second): well under the usual limit of three flashes in a second.
FIREWORKS_COLORS = (
    (100, 0, 0),
    (100, 35, 0),
    (100, 70, 5),
    (0, 100, 10),
    (0, 25, 100),
    (60, 0, 100),
    (100, 100, 100),
)
FIREWORKS_GOLD = (100, 55, 0)
FIREWORKS_TRAIL = (100, 40, 0)
FIREWORKS_STEP = 0.1
FIREWORKS_MIN_LAUNCH = 0.6
FIREWORKS_LAUNCH = (FIREWORKS_MIN_LAUNCH, 2.5)  # some shells climb fast, some slowly
FIREWORKS_TRAIL_LEVEL = 0.2  # share of full brightness the trail rises to from dark
FIREWORKS_MIN_FADE = 0.6
FIREWORKS_FADE = (FIREWORKS_MIN_FADE, 1.1)
FIREWORKS_WILLOW_FADE = (1.5, 2.2)
# Fully dark before every shell, now and then for a longer lull
FIREWORKS_DARK = (0.5, 3.0)
FIREWORKS_LULL_CHANCE = 0.2
FIREWORKS_LULL = (3.0, 7.0)
FIREWORKS_FINALE_CHANCE = 0.3
FIREWORKS_FINALE_DARK = (0.2, 0.5)
# Pursuit: red and blue like police lights, but slow enough to be safe: each
# color fades in, holds and fades out over half a second, so the color changes
# twice a second (under the usual limit of three flashes in a second)
PURSUIT_COLORS = ((100, 0, 0), (0, 0, 100))
PURSUIT_STEPS = ((0.5, 0.1), (1.0, 0.3), (0.5, 0.1))  # (level, seconds)
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
    elif effect == EFFECT_FIREWORKS:
        yield from _fireworks(level)
    elif effect == EFFECT_PURSUIT:
        first = True
        while True:
            for color in PURSUIT_COLORS:
                for factor, delay in PURSUIT_STEPS:
                    if first and factor < 1:
                        continue  # start straight on full red, without a fade-in
                    first = False
                    yield Step(RGBColor(*(_pct(c / 100 * level * factor) for c in color)), delay)
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
    else:
        raise ValueError(f"Unknown effect: {effect}")


def _fireworks(level: float) -> Iterator[Step]:
    """Shells that launch as a dim rising trail, then burst and fade."""
    dark = RGBColor(0, 0, 0)

    def color_at(color: tuple[int, ...], share: float) -> RGBColor:
        return RGBColor(*(_pct(c / 100 * level * share) for c in color))

    while True:
        lull = random.random() < FIREWORKS_LULL_CHANCE
        yield Step(dark, random.uniform(*(FIREWORKS_LULL if lull else FIREWORKS_DARK)))
        # Now and then a finale: two to four shells in quick succession
        shells = random.randint(2, 4) if random.random() < FIREWORKS_FINALE_CHANCE else 1
        for shell in range(shells):
            # Launch: a dim orange trail that fades up from dark as it climbs,
            # slowly at first, then faster
            launch = max(2, round(random.uniform(*FIREWORKS_LAUNCH) / FIREWORKS_STEP))
            for i in range(launch):
                share = FIREWORKS_TRAIL_LEVEL * ((i + 1) / launch) ** 1.5
                yield Step(color_at(FIREWORKS_TRAIL, share), FIREWORKS_STEP)
            # Burst, then fade in one of four styles
            kind = random.choice(("peony", "peony", "changer", "willow", "crackle"))
            color = FIREWORKS_GOLD if kind == "willow" else random.choice(FIREWORKS_COLORS)
            second = random.choice([c for c in FIREWORKS_COLORS if c != color])
            fade = FIREWORKS_WILLOW_FADE if kind == "willow" else FIREWORKS_FADE
            steps = max(2, round(random.uniform(*fade) / FIREWORKS_STEP))
            peak = random.uniform(0.8, 1.0)
            for i in range(steps):
                remaining = 1 - i / steps
                share = peak * remaining ** (1.2 if kind == "willow" else 2)
                # The flicker stays small (a few percent of full brightness),
                # so it is not a flash
                if kind == "crackle" and i > 2 * steps / 3:
                    share *= random.uniform(0.5, 1.0)
                elif i > steps / 2:
                    share *= random.uniform(0.8, 1.0)
                shown = second if kind == "changer" and i >= steps / 2 else color
                yield Step(color_at(shown, share), FIREWORKS_STEP)
            if shell < shells - 1:
                yield Step(dark, random.uniform(*FIREWORKS_FINALE_DARK))


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
