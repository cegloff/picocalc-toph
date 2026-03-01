from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE, KEY_ESC


class Menu:
    __slots__ = (
        '_display', '_items', '_selected', '_scroll', '_visible',
        '_title', '_x', '_y', '_w', '_h', '_item_h', '_dirty',
    )

    def __init__(self, display, items, title="", x=0, y=0, w=320, h=320):
        self._display = display
        self._items = items
        self._selected = 0
        self._scroll = 0
        self._title = title
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._item_h = display.font_height() + 8
        title_h = (display.font_height() + 12) if title else 0
        self._visible = (h - title_h) // self._item_h
        self._dirty = True

    @property
    def selected(self):
        return self._selected

    @property
    def selected_item(self):
        if 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, value):
        self._items = value
        self._selected = 0
        self._scroll = 0
        self._dirty = True

    def handle_input(self, key):
        if key == KEY_UP:
            if self._selected > 0:
                self._selected -= 1
                if self._selected < self._scroll:
                    self._scroll = self._selected
                self._dirty = True
            return None

        if key == KEY_DOWN:
            if self._selected < len(self._items) - 1:
                self._selected += 1
                if self._selected >= self._scroll + self._visible:
                    self._scroll = self._selected - self._visible + 1
                self._dirty = True
            return None

        if key == KEY_ENTER:
            return self._selected

        if key == KEY_BACKSPACE or key == KEY_ESC:
            return -1

        return None

    def draw(self, force=False):
        if not self._dirty and not force:
            return

        d = self._display
        d.clear()

        y = self._y

        if self._title:
            d.fill_rect(self._x, y, self._w, d.font_height() + 10, d.fg)
            d.text(self._x + 4, y + 5, self._title, d.bg)
            y += d.font_height() + 12

        end = min(self._scroll + self._visible, len(self._items))
        for i in range(self._scroll, end):
            item = self._items[i]
            label = item if isinstance(item, str) else item.get("label", str(item))

            if i == self._selected:
                d.fill_rect(self._x, y, self._w, self._item_h, d.fg)
                d.text(self._x + 8, y + 4, label, d.bg)
            else:
                d.text(self._x + 8, y + 4, label, d.fg)

            y += self._item_h

        # scroll indicator
        if len(self._items) > self._visible:
            bar_h = max(10, self._h * self._visible // len(self._items))
            bar_y = self._y + (self._h - bar_h) * self._scroll // max(1, len(self._items) - self._visible)
            d.fill_rect(self._w - 3, bar_y, 3, bar_h, d.fg)

        d.swap()
        self._dirty = False
