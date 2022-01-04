import colorsys
from dataclasses import dataclass


@dataclass
class Color:
    red: int
    green: int
    blue: int

    alpha: int
    """Alpha channel (0 = fully transparent, 255 = fully opaque)."""

    @property
    def hsv(self):
        return colorsys.rgb_to_hsv(self.red, self.green, self.blue)

    @property
    def hue(self):
        return self.hsv[0]

    @property
    def brightness(self):
        return self.hsv[2]

    @classmethod
    def parse(cls, s: str):
        def h(i: int):
            return int(s[i:(i + 2)], 16)
        return Color(h(1), h(3), h(5), h(7))
