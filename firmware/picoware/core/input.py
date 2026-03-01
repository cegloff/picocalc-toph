from picoware_keyboard import (
    init as _kb_init,
    poll as _kb_poll,
    get_key_nonblocking as _kb_get_key,
    key_available as _kb_available,
)

# Navigation keys (from keyboard.h)
KEY_UP = 0xB5
KEY_DOWN = 0xB6
KEY_LEFT = 0xB4
KEY_RIGHT = 0xB7
KEY_ESC = 0xB1
KEY_HOME = 0xD2
KEY_DEL = 0xD4
KEY_INSERT = 0xD1
KEY_PAGE_UP = 0xD3
KEY_PAGE_DOWN = 0xD6

# Standard keys
KEY_ENTER = 0x0D
KEY_BACKSPACE = 0x08
KEY_TAB = 0x09
KEY_SPACE = 0x20

# Function keys
KEY_F1 = 0x81
KEY_F2 = 0x82
KEY_F3 = 0x83
KEY_F4 = 0x84
KEY_F5 = 0x85
KEY_F6 = 0x86
KEY_F7 = 0x87
KEY_F8 = 0x88
KEY_F9 = 0x89
KEY_F10 = 0x8A

# Modifier keys
KEY_ALT = 0xE2
KEY_SHIFT_L = 0xE1
KEY_SHIFT_R = 0xE5
KEY_CTRL = 0xE0
KEY_SYM = 0xF1
KEY_BREAK = 0xAB


class Input:
    __slots__ = ('_key', '_was_cap')

    def __init__(self):
        _kb_init()
        self._key = -1
        self._was_cap = False

    def poll(self):
        _kb_poll()
        if _kb_available():
            raw = _kb_get_key()
            if raw:
                self._was_cap = 65 <= raw <= 90
                self._key = raw
            else:
                self._key = -1
        else:
            self._key = -1

    @property
    def key(self):
        return self._key

    @property
    def char(self):
        k = self._key
        if 32 <= k <= 126:
            return chr(k)
        if k == KEY_ENTER:
            return '\n'
        if k == KEY_TAB:
            return '\t'
        return ''

    @property
    def was_capitalized(self):
        return self._was_cap

    def reset(self):
        self._key = -1
        self._was_cap = False
