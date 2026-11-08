"""Data models for The Lampster."""

from dataclasses import dataclass


@dataclass
class RGBColor:
    """RGB color representation (0-100 per channel).

    Based on protocol from: https://github.com/Noki/the-lampster
    """

    red: int
    green: int
    blue: int

    def __post_init__(self):
        """Validate color values are in range."""
        for name, value in [("red", self.red), ("green", self.green), ("blue", self.blue)]:
            if not 0 <= value <= 100:
                raise ValueError(f"{name} value must be 0-100, got {value}")

    def to_bytes(self) -> bytes:
        """Convert to BLE command format (3 bytes: RR GG BB)."""
        return bytes([self.red, self.green, self.blue])

    def __str__(self) -> str:
        return f"RGB({self.red}, {self.green}, {self.blue})"


@dataclass
class WhiteColor:
    """White color representation (warm/cold, 0-100 each).

    Based on protocol from: https://github.com/Noki/the-lampster
    """

    warm: int
    cold: int

    def __post_init__(self):
        """Validate color values are in range."""
        for name, value in [("warm", self.warm), ("cold", self.cold)]:
            if not 0 <= value <= 100:
                raise ValueError(f"{name} value must be 0-100, got {value}")

    def to_bytes(self) -> bytes:
        """Convert to BLE command format (2 bytes: WW CC)."""
        return bytes([self.warm, self.cold])

    def __str__(self) -> str:
        return f"White(warm={self.warm}, cold={self.cold})"


@dataclass
class LampState:
    """Current lamp state.

    Note: The Lampster does not support reading state from the device,
    so this is maintained locally by the client.
    """

    is_on: bool
    mode: str  # 'rgb', 'white', or 'off'
    rgb_color: RGBColor | None = None
    white_color: WhiteColor | None = None

    def __str__(self) -> str:
        if not self.is_on:
            return "State(off)"
        if self.mode == "rgb" and self.rgb_color:
            return f"State(on, rgb, {self.rgb_color})"
        if self.mode == "white" and self.white_color:
            return f"State(on, white, {self.white_color})"
        return f"State(on, {self.mode})"
