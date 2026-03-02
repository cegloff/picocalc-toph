from picoware_lcd import (
    init,
    deinit,
    clear_framebuffer,
    draw_circle,
    fill_circle,
    fill_rect,
    fill_round_rectangle,
    fill_triangle,
    draw_line,
    draw_line_custom,
    draw_pixel,
    swap as _lcd_swap,
    draw_text,
    draw_char,
    set_mode,
    draw_image_bytearray as _draw_image,
    FONT_DEFAULT,
)
from picoware_keyboard import set_background_poll

# RGB565 color constants
BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
CYAN = 0x07FF
MAGENTA = 0xF81F
YELLOW = 0xFFE0
ORANGE = 0xFD20
GRAY = 0x8410
DARK_GRAY = 0x4208
LIGHT_GRAY = 0xC618

# Font size indices (maps to C font module)
FONT_8 = 0
FONT_12 = 1
FONT_16 = 2
FONT_20 = 3
FONT_24 = 4

# Font pixel dimensions: (char_width, char_height) for each font index
_FONT_DIMS = (
    (5, 8),    # FONT_8
    (7, 12),   # FONT_12
    (11, 16),  # FONT_16
    (14, 20),  # FONT_20
    (17, 24),  # FONT_24
)


def _rgb565_to_rgb332(c):
    return ((c & 0xE000) >> 8) | ((c & 0x0700) >> 6) | ((c & 0x0018) >> 3)


class Display:
    __slots__ = ('fg', 'bg', '_font')

    W = 320
    H = 320

    def __init__(self, fg=WHITE, bg=BLACK, mode=0):
        self.fg = fg
        self.bg = bg
        self._font = FONT_DEFAULT
        init(bg, mode)
        clear_framebuffer(_rgb565_to_rgb332(bg))

    def deinit(self):
        deinit()

    # -- Buffer management --

    def clear(self, color=None):
        clear_framebuffer(_rgb565_to_rgb332(color if color is not None else self.bg))

    def swap(self):
        set_background_poll(False)
        _lcd_swap()
        set_background_poll(True)

    def set_mode(self, mode):
        set_mode(mode)

    # -- Drawing primitives --

    def pixel(self, x, y, color=None):
        draw_pixel(x, y, color if color is not None else self.fg)

    def line(self, x1, y1, x2, y2, color=None):
        draw_line_custom(x1, y1, x2, y2, color if color is not None else self.fg)

    def hline(self, x, y, w, color=None):
        draw_line(x, y, w, color if color is not None else self.fg)

    def rect(self, x, y, w, h, color=None):
        c = color if color is not None else self.fg
        draw_line(x, y, w, c)
        draw_line(x, y + h - 1, w, c)
        draw_line_custom(x, y, x, y + h - 1, c)
        draw_line_custom(x + w - 1, y, x + w - 1, y + h - 1, c)

    def fill_rect(self, x, y, w, h, color=None):
        fill_rect(x, y, w, h, color if color is not None else self.fg)

    def fill_round_rect(self, x, y, w, h, r, color=None):
        if w > 0 and h > 0 and r > 0:
            fill_round_rectangle(x, y, w, h, r, color if color is not None else self.fg)

    def circle(self, x, y, r, color=None):
        draw_circle(x, y, r, color if color is not None else self.fg)

    def fill_circle(self, x, y, r, color=None):
        fill_circle(x, y, r, color if color is not None else self.fg)

    def triangle(self, x1, y1, x2, y2, x3, y3, color=None):
        c = color if color is not None else self.fg
        draw_line_custom(x1, y1, x2, y2, c)
        draw_line_custom(x2, y2, x3, y3, c)
        draw_line_custom(x3, y3, x1, y1, c)

    def fill_triangle(self, x1, y1, x2, y2, x3, y3, color=None):
        fill_triangle(x1, y1, x2, y2, x3, y3, color if color is not None else self.fg)

    # -- Image --

    def draw_image(self, x, y, w, h, data, invert=False):
        _draw_image(x, y, w, h, data, invert)

    # -- Text --

    def text(self, x, y, s, color=None, font=None):
        draw_text(
            x, y, s,
            color if color is not None else self.fg,
            font if font is not None else self._font,
        )

    def char(self, x, y, c, color=None, font=None):
        draw_char(
            x, y, ord(c) if isinstance(c, str) else c,
            color if color is not None else self.fg,
            font if font is not None else self._font,
        )

    def text_width(self, s, font=None):
        f = font if font is not None else self._font
        w, _ = _FONT_DIMS[f] if f < len(_FONT_DIMS) else _FONT_DIMS[0]
        return len(s) * w

    def font_height(self, font=None):
        f = font if font is not None else self._font
        _, h = _FONT_DIMS[f] if f < len(_FONT_DIMS) else _FONT_DIMS[0]
        return h

    def char_width(self, font=None):
        f = font if font is not None else self._font
        w, _ = _FONT_DIMS[f] if f < len(_FONT_DIMS) else _FONT_DIMS[0]
        return w

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, f):
        self._font = f
