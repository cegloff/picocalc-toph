from picoware.core.input import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_ENTER, KEY_BACKSPACE, KEY_ESC,
)
from picoware.core.display import FONT_8, FONT_20


COLS = 4
CELL_W = 80
CELL_H = 68
ICON_SIZE = 48
ICON_PAD_TOP = 4
ICON_X_OFF = 16  # (80 - 48) / 2
LABEL_GAP = 4
LABEL_FONT = FONT_8
LABEL_CHAR_W = 5
LABEL_MAX = 16  # 80 / 5


class IconGrid:
    __slots__ = (
        '_d', '_items', '_title', '_x', '_y', '_w', '_h',
        '_sel', '_scroll', '_rows_vis', '_dirty', '_grid_y',
    )

    def __init__(self, display, items, title="", x=0, y=0, w=320, h=320):
        self._d = display
        self._items = items
        self._title = title
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._sel = 0
        self._scroll = 0
        self._dirty = True
        title_h = (display.font_height() + 12) if title else 0
        self._grid_y = y + title_h
        grid_h = h - title_h
        self._rows_vis = grid_h // CELL_H
        if self._rows_vis < 1:
            self._rows_vis = 1

    @property
    def selected(self):
        return self._sel

    def handle_input(self, key):
        n = len(self._items)
        if n == 0:
            return None

        old = self._sel

        if key == KEY_LEFT:
            if self._sel > 0:
                self._sel -= 1
        elif key == KEY_RIGHT:
            if self._sel < n - 1:
                self._sel += 1
        elif key == KEY_UP:
            if self._sel >= COLS:
                self._sel -= COLS
        elif key == KEY_DOWN:
            nxt = self._sel + COLS
            if nxt < n:
                self._sel = nxt
            else:
                # clamp to last item if partial row
                last_row_start = (n - 1) // COLS * COLS
                if self._sel < last_row_start:
                    self._sel = min(n - 1, last_row_start + self._sel % COLS)
        elif key == KEY_ENTER:
            return self._sel
        elif key == KEY_BACKSPACE or key == KEY_ESC:
            return -1

        if self._sel != old:
            self._dirty = True
            # scroll to keep selection visible
            sel_row = self._sel // COLS
            if sel_row < self._scroll:
                self._scroll = sel_row
            elif sel_row >= self._scroll + self._rows_vis:
                self._scroll = sel_row - self._rows_vis + 1

        return None

    def draw(self, force=False):
        if not self._dirty and not force:
            return

        d = self._d
        d.fill_rect(self._x, self._y, self._w, self._h, d.bg)

        y = self._y
        if self._title:
            d.fill_rect(self._x, y, self._w, d.font_height() + 10, d.fg)
            d.text(self._x + 4, y + 5, self._title, d.bg)

        n = len(self._items)
        start = self._scroll * COLS
        end = min(start + self._rows_vis * COLS, n)

        for idx in range(start, end):
            row = idx // COLS - self._scroll
            col = idx % COLS
            cx = self._x + col * CELL_W
            cy = self._grid_y + row * CELL_H

            item = self._items[idx]
            name = item["name"]
            icon = item.get("icon")
            selected = idx == self._sel

            if selected:
                d.fill_round_rect(cx + 2, cy + 1, CELL_W - 4, CELL_H - 2, 6, d.fg)

            # icon
            ix = cx + ICON_X_OFF
            iy = cy + ICON_PAD_TOP
            if icon:
                d.draw_image(ix, iy, ICON_SIZE, ICON_SIZE, icon, selected)
            else:
                self._draw_default_icon(d, ix, iy, name, selected)

            # label
            label = name[:LABEL_MAX]
            tw = len(label) * LABEL_CHAR_W
            lx = cx + (CELL_W - tw) // 2
            ly = iy + ICON_SIZE + LABEL_GAP
            lc = d.bg if selected else d.fg
            d.text(lx, ly, label, lc, LABEL_FONT)

        # scroll indicator
        total_rows = (n + COLS - 1) // COLS
        if total_rows > self._rows_vis:
            grid_h = self._rows_vis * CELL_H
            bar_h = max(10, grid_h * self._rows_vis // total_rows)
            max_scroll = total_rows - self._rows_vis
            bar_y = self._grid_y + (grid_h - bar_h) * self._scroll // max(1, max_scroll)
            d.fill_rect(self._x + self._w - 3, bar_y, 3, bar_h, d.fg)

        d.swap()
        self._dirty = False

    def _draw_default_icon(self, d, x, y, name, selected):
        if selected:
            bg_c = d.fg
            fg_c = d.bg
        else:
            from picoware.core.display import DARK_GRAY
            bg_c = DARK_GRAY
            fg_c = 0xFFFF if d.bg == 0x0000 else 0x0000

        d.fill_round_rect(x, y, ICON_SIZE, ICON_SIZE, 8, bg_c)
        letter = name[0].upper() if name else "?"
        # FONT_20 is 14px wide, 20px tall — center in 48x48
        lx = x + (ICON_SIZE - 14) // 2
        ly = y + (ICON_SIZE - 20) // 2
        d.text(lx, ly, letter, fg_c, FONT_20)
