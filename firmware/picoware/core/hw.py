from picoware_southbridge import (
    get_battery_percentage,
    read_lcd_backlight,
    write_lcd_backlight,
    read_keyboard_backlight,
    write_keyboard_backlight,
    write_power_off_delay,
)


class Hardware:
    __slots__ = ()

    @staticmethod
    def battery_percent():
        return get_battery_percentage()

    @staticmethod
    def set_lcd_backlight(value):
        write_lcd_backlight(value)

    @staticmethod
    def get_lcd_backlight():
        return read_lcd_backlight()

    @staticmethod
    def set_kb_backlight(value):
        write_keyboard_backlight(value)

    @staticmethod
    def get_kb_backlight():
        return read_keyboard_backlight()

    @staticmethod
    def power_off(delay=0):
        write_power_off_delay(delay)
