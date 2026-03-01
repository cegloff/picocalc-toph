class StatusBar:
    __slots__ = ('_display', '_hw', '_settings', '_wifi', '_h')

    def __init__(self, display, hw, settings, wifi=None):
        self._display = display
        self._hw = hw
        self._settings = settings
        self._wifi = wifi
        self._h = display.font_height() + 4

    @property
    def height(self):
        return self._h

    def draw(self):
        d = self._display
        h = self._h

        # background
        d.fill_rect(0, 0, d.W, h, d.fg)

        # WiFi status (left)
        if self._wifi:
            if self._wifi.is_connected:
                ip = self._wifi.ip or ""
                d.text(4, 2, "W:" + ip, d.bg)
            else:
                d.text(4, 2, "W:--", d.bg)
        else:
            d.text(4, 2, "W:off", d.bg)

        # Battery (right)
        batt = self._hw.battery_percent()
        batt_str = str(batt) + "%"
        bw = d.text_width(batt_str)
        d.text(d.W - bw - 4, 2, batt_str, d.bg)
