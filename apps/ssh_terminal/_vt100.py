"""
VT100 Terminal Emulator for PicoCalcOS
Compact screen buffer with 16-color ANSI support, parser state machine,
scrollback, alternate screen buffer, and dirty-row rendering.
"""

from micropython import const
from gc import collect

# Parser states
_GROUND = const(0)
_ESC = const(1)
_CSI = const(2)
_OSC = const(3)
_ESC_HASH = const(4)

# ANSI color index -> RGB565
_PALETTE = None

def _get_palette():
    global _PALETTE
    if _PALETTE is None:
        from picoware.core.display import (
            BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, LIGHT_GRAY,
            DARK_GRAY, ORANGE, WHITE,
        )
        _PALETTE = (
            BLACK,      # 0
            RED,        # 1
            GREEN,      # 2
            YELLOW,     # 3
            BLUE,       # 4
            MAGENTA,    # 5
            CYAN,       # 6
            LIGHT_GRAY, # 7
            DARK_GRAY,  # 8
            ORANGE,     # 9  (bright red -> orange)
            GREEN,      # 10 (bright green)
            YELLOW,     # 11 (bright yellow)
            BLUE,       # 12 (bright blue)
            MAGENTA,    # 13 (bright magenta)
            CYAN,       # 14 (bright cyan)
            WHITE,      # 15
        )
    return _PALETTE


class TermScreen:
    def __init__(self, cols, rows, send_func=None, scrollback_max=100):
        self.cols = cols
        self.rows = rows
        self._send = send_func
        self.scrollback_max = scrollback_max

        # Screen buffer: 2 bytes per cell (char, attr)
        self.buf = bytearray(cols * rows * 2)
        self._clear_buf(self.buf)

        # Cursor
        self.cx = 0
        self.cy = 0
        self.attr = 0x70  # fg=7 (white), bg=0 (black)
        self._bold = False
        self._reverse = False

        # Scroll region
        self.scroll_top = 0
        self.scroll_bot = rows - 1

        # Saved cursor
        self._saved_cx = 0
        self._saved_cy = 0
        self._saved_attr = 0x70

        # Alt screen
        self.in_alt = False
        self.alt_buf = None
        self._alt_cx = 0
        self._alt_cy = 0
        self._alt_attr = 0x70

        # Scrollback (main screen only)
        self.scrollback = []
        self.scroll_offset = 0

        # Application cursor keys mode
        self.app_cursor_keys = False
        # Cursor visible
        self.cursor_visible = True
        # Wrap pending (auto-wrap at right margin)
        self._wrap_next = False

        # Parser state
        self._state = _GROUND
        self._csi_params = []
        self._csi_private = False
        self._csi_buf = bytearray()
        self._osc_buf = bytearray()

        # Dirty tracking
        self.dirty = True
        self._dirty_rows = set()
        self._mark_all_dirty()

    def _clear_buf(self, buf):
        for i in range(0, len(buf), 2):
            buf[i] = 0x20      # space
            buf[i + 1] = 0x70  # fg=7, bg=0

    def _mark_all_dirty(self):
        self._dirty_rows = set(range(self.rows))
        self.dirty = True

    def _mark_dirty(self, row):
        if 0 <= row < self.rows:
            self._dirty_rows.add(row)
            self.dirty = True

    # --- Buffer access ---

    def _cell_offset(self, x, y):
        return (y * self.cols + x) * 2

    def _put_char(self, ch):
        if self._wrap_next:
            self.cx = 0
            self._linefeed()
            self._wrap_next = False

        if 0 <= self.cx < self.cols and 0 <= self.cy < self.rows:
            off = self._cell_offset(self.cx, self.cy)
            self.buf[off] = ch if ch >= 0x20 else 0x20
            self.buf[off + 1] = self._effective_attr()
            self._mark_dirty(self.cy)

        self.cx += 1
        if self.cx >= self.cols:
            self.cx = self.cols - 1
            self._wrap_next = True

    def _effective_attr(self):
        fg = (self.attr >> 4) & 0x0F
        bg = self.attr & 0x0F
        if self._bold and fg < 8:
            fg += 8
        if self._reverse:
            fg, bg = bg, fg
        return (fg << 4) | bg

    # --- Scrolling ---

    def _scroll_up(self, n=1):
        cols2 = self.cols * 2
        top = self.scroll_top
        bot = self.scroll_bot
        for _ in range(n):
            if not self.in_alt and top == 0:
                # Save departing row to scrollback
                row_off = 0
                row_data = bytearray(self.buf[row_off:row_off + cols2])
                self.scrollback.append(row_data)
                if len(self.scrollback) > self.scrollback_max:
                    self.scrollback.pop(0)
            # Shift rows up within scroll region
            for r in range(top, bot):
                dst = r * cols2
                src = (r + 1) * cols2
                self.buf[dst:dst + cols2] = self.buf[src:src + cols2]
            # Clear bottom row
            bot_off = bot * cols2
            for i in range(bot_off, bot_off + cols2, 2):
                self.buf[i] = 0x20
                self.buf[i + 1] = 0x70
        for r in range(top, bot + 1):
            self._mark_dirty(r)

    def _scroll_down(self, n=1):
        cols2 = self.cols * 2
        top = self.scroll_top
        bot = self.scroll_bot
        for _ in range(n):
            for r in range(bot, top, -1):
                dst = r * cols2
                src = (r - 1) * cols2
                self.buf[dst:dst + cols2] = self.buf[src:src + cols2]
            # Clear top row
            top_off = top * cols2
            for i in range(top_off, top_off + cols2, 2):
                self.buf[i] = 0x20
                self.buf[i + 1] = 0x70
        for r in range(top, bot + 1):
            self._mark_dirty(r)

    def _linefeed(self):
        if self.cy == self.scroll_bot:
            self._scroll_up(1)
        elif self.cy < self.rows - 1:
            self.cy += 1

    def _reverse_index(self):
        if self.cy == self.scroll_top:
            self._scroll_down(1)
        elif self.cy > 0:
            self.cy -= 1

    # --- Erase operations ---

    def _erase_display(self, mode):
        cols2 = self.cols * 2
        if mode == 0:  # below
            # Current position to end of line
            off = self._cell_offset(self.cx, self.cy)
            end = (self.cy + 1) * cols2
            for i in range(off, end, 2):
                self.buf[i] = 0x20
                self.buf[i + 1] = 0x70
            # All lines below
            for r in range(self.cy + 1, self.rows):
                row_off = r * cols2
                for i in range(row_off, row_off + cols2, 2):
                    self.buf[i] = 0x20
                    self.buf[i + 1] = 0x70
            for r in range(self.cy, self.rows):
                self._mark_dirty(r)
        elif mode == 1:  # above
            for r in range(0, self.cy):
                row_off = r * cols2
                for i in range(row_off, row_off + cols2, 2):
                    self.buf[i] = 0x20
                    self.buf[i + 1] = 0x70
            off = self.cy * cols2
            end = self._cell_offset(self.cx + 1, self.cy)
            for i in range(off, min(end, (self.cy + 1) * cols2), 2):
                self.buf[i] = 0x20
                self.buf[i + 1] = 0x70
            for r in range(0, self.cy + 1):
                self._mark_dirty(r)
        elif mode == 2 or mode == 3:  # all
            self._clear_buf(self.buf)
            self._mark_all_dirty()

    def _erase_line(self, mode):
        cols2 = self.cols * 2
        row_off = self.cy * cols2
        if mode == 0:  # right
            start = self._cell_offset(self.cx, self.cy)
            end = row_off + cols2
        elif mode == 1:  # left
            start = row_off
            end = self._cell_offset(self.cx + 1, self.cy)
            end = min(end, row_off + cols2)
        else:  # all
            start = row_off
            end = row_off + cols2
        for i in range(start, end, 2):
            self.buf[i] = 0x20
            self.buf[i + 1] = 0x70
        self._mark_dirty(self.cy)

    # --- Insert/Delete ---

    def _insert_lines(self, n):
        if self.cy < self.scroll_top or self.cy > self.scroll_bot:
            return
        old_top = self.scroll_top
        self.scroll_top = self.cy
        self._scroll_down(n)
        self.scroll_top = old_top

    def _delete_lines(self, n):
        if self.cy < self.scroll_top or self.cy > self.scroll_bot:
            return
        old_top = self.scroll_top
        self.scroll_top = self.cy
        self._scroll_up(n)
        self.scroll_top = old_top

    def _delete_chars(self, n):
        cols2 = self.cols * 2
        row_off = self.cy * cols2
        for x in range(self.cx, self.cols):
            src_x = x + n
            off = row_off + x * 2
            if src_x < self.cols:
                src_off = row_off + src_x * 2
                self.buf[off] = self.buf[src_off]
                self.buf[off + 1] = self.buf[src_off + 1]
            else:
                self.buf[off] = 0x20
                self.buf[off + 1] = 0x70
        self._mark_dirty(self.cy)

    def _insert_chars(self, n):
        cols2 = self.cols * 2
        row_off = self.cy * cols2
        for x in range(self.cols - 1, self.cx - 1, -1):
            src_x = x - n
            off = row_off + x * 2
            if src_x >= self.cx:
                src_off = row_off + src_x * 2
                self.buf[off] = self.buf[src_off]
                self.buf[off + 1] = self.buf[src_off + 1]
            else:
                self.buf[off] = 0x20
                self.buf[off + 1] = 0x70
        self._mark_dirty(self.cy)

    def _erase_chars(self, n):
        for i in range(n):
            x = self.cx + i
            if x >= self.cols:
                break
            off = self._cell_offset(x, self.cy)
            self.buf[off] = 0x20
            self.buf[off + 1] = 0x70
        self._mark_dirty(self.cy)

    # --- Alternate screen ---

    def _enter_alt_screen(self):
        if self.in_alt:
            return
        self.in_alt = True
        # Save main cursor
        self._alt_cx = self.cx
        self._alt_cy = self.cy
        self._alt_attr = self.attr
        # Swap buffers
        self.alt_buf = self.buf
        self.buf = bytearray(self.cols * self.rows * 2)
        self._clear_buf(self.buf)
        self.cx = 0
        self.cy = 0
        self.scroll_top = 0
        self.scroll_bot = self.rows - 1
        self._mark_all_dirty()

    def _exit_alt_screen(self):
        if not self.in_alt:
            return
        self.in_alt = False
        # Restore main buffer
        self.buf = self.alt_buf
        self.alt_buf = None
        self.cx = self._alt_cx
        self.cy = self._alt_cy
        self.attr = self._alt_attr
        self.scroll_top = 0
        self.scroll_bot = self.rows - 1
        self._mark_all_dirty()
        collect()

    # --- Save/Restore cursor ---

    def _save_cursor(self):
        self._saved_cx = self.cx
        self._saved_cy = self.cy
        self._saved_attr = self.attr

    def _restore_cursor(self):
        self.cx = self._saved_cx
        self.cy = self._saved_cy
        self.attr = self._saved_attr
        self._wrap_next = False

    # --- SGR (Select Graphic Rendition) ---

    def _handle_sgr(self, params):
        if not params:
            params = [0]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self.attr = 0x70
                self._bold = False
                self._reverse = False
            elif p == 1:
                self._bold = True
            elif p == 7:
                self._reverse = True
            elif p == 22:
                self._bold = False
            elif p == 27:
                self._reverse = False
            elif 30 <= p <= 37:
                fg = p - 30
                self.attr = (fg << 4) | (self.attr & 0x0F)
            elif p == 38:
                # 256-color or truecolor - skip gracefully
                if i + 1 < len(params):
                    if params[i + 1] == 5 and i + 2 < len(params):
                        # 38;5;N - map to nearest
                        n = params[i + 2]
                        if n < 16:
                            self.attr = (n << 4) | (self.attr & 0x0F)
                        i += 2
                    elif params[i + 1] == 2 and i + 4 < len(params):
                        i += 4  # skip R,G,B
                    else:
                        i += 1
            elif p == 39:
                self.attr = (7 << 4) | (self.attr & 0x0F)  # default fg
            elif 40 <= p <= 47:
                bg = p - 40
                self.attr = (self.attr & 0xF0) | bg
            elif p == 48:
                # 256-color or truecolor bg
                if i + 1 < len(params):
                    if params[i + 1] == 5 and i + 2 < len(params):
                        n = params[i + 2]
                        if n < 16:
                            self.attr = (self.attr & 0xF0) | n
                        i += 2
                    elif params[i + 1] == 2 and i + 4 < len(params):
                        i += 4
                    else:
                        i += 1
            elif p == 49:
                self.attr = (self.attr & 0xF0) | 0  # default bg
            elif 90 <= p <= 97:
                fg = p - 90 + 8
                self.attr = (fg << 4) | (self.attr & 0x0F)
            elif 100 <= p <= 107:
                bg = p - 100 + 8
                self.attr = (self.attr & 0xF0) | bg
            i += 1

    # --- CSI dispatch ---

    def _parse_csi_params(self):
        params = []
        current = 0
        has_digit = False
        for b in self._csi_buf:
            if 0x30 <= b <= 0x39:
                current = current * 10 + (b - 0x30)
                has_digit = True
            elif b == 0x3B:  # ;
                params.append(current if has_digit else 0)
                current = 0
                has_digit = False
        params.append(current if has_digit else 0)
        return params

    def _dispatch_csi(self, final):
        params = self._parse_csi_params()
        private = self._csi_private

        if private:
            self._dispatch_csi_private(final, params)
            return

        if final == 0x41:  # A - CUU
            n = max(params[0], 1) if params else 1
            self.cy = max(self.cy - n, self.scroll_top)
            self._wrap_next = False
        elif final == 0x42:  # B - CUD
            n = max(params[0], 1) if params else 1
            self.cy = min(self.cy + n, self.scroll_bot)
            self._wrap_next = False
        elif final == 0x43:  # C - CUF
            n = max(params[0], 1) if params else 1
            self.cx = min(self.cx + n, self.cols - 1)
            self._wrap_next = False
        elif final == 0x44:  # D - CUB
            n = max(params[0], 1) if params else 1
            self.cx = max(self.cx - n, 0)
            self._wrap_next = False
        elif final == 0x47:  # G - CHA
            col = max(params[0], 1) if params else 1
            self.cx = min(col - 1, self.cols - 1)
            self._wrap_next = False
        elif final == 0x48 or final == 0x66:  # H/f - CUP
            row = max(params[0], 1) if params else 1
            col = params[1] if len(params) > 1 else 1
            col = max(col, 1)
            self.cy = min(row - 1, self.rows - 1)
            self.cx = min(col - 1, self.cols - 1)
            self._wrap_next = False
        elif final == 0x4A:  # J - ED
            mode = params[0] if params else 0
            self._erase_display(mode)
        elif final == 0x4B:  # K - EL
            mode = params[0] if params else 0
            self._erase_line(mode)
        elif final == 0x4C:  # L - IL
            n = max(params[0], 1) if params else 1
            self._insert_lines(n)
        elif final == 0x4D:  # M - DL
            n = max(params[0], 1) if params else 1
            self._delete_lines(n)
        elif final == 0x50:  # P - DCH
            n = max(params[0], 1) if params else 1
            self._delete_chars(n)
        elif final == 0x40:  # @ - ICH
            n = max(params[0], 1) if params else 1
            self._insert_chars(n)
        elif final == 0x58:  # X - ECH
            n = max(params[0], 1) if params else 1
            self._erase_chars(n)
        elif final == 0x53:  # S - SU (scroll up)
            n = max(params[0], 1) if params else 1
            self._scroll_up(n)
        elif final == 0x54:  # T - SD (scroll down)
            n = max(params[0], 1) if params else 1
            self._scroll_down(n)
        elif final == 0x64:  # d - VPA
            row = max(params[0], 1) if params else 1
            self.cy = min(row - 1, self.rows - 1)
            self._wrap_next = False
        elif final == 0x6D:  # m - SGR
            self._handle_sgr(params)
        elif final == 0x72:  # r - DECSTBM
            top = max(params[0], 1) if params else 1
            bot = params[1] if len(params) > 1 and params[1] > 0 else self.rows
            self.scroll_top = max(top - 1, 0)
            self.scroll_bot = min(bot - 1, self.rows - 1)
            self.cx = 0
            self.cy = 0
            self._wrap_next = False
        elif final == 0x68:  # h - SM
            pass  # standard modes - ignore
        elif final == 0x6C:  # l - RM
            pass
        elif final == 0x6E:  # n - DSR
            if params and params[0] == 6:
                # Report cursor position
                resp = "\x1b[%d;%dR" % (self.cy + 1, self.cx + 1)
                if self._send:
                    self._send(resp.encode())
        elif final == 0x63:  # c - DA
            if self._send:
                self._send(b"\x1b[?1;2c")  # VT100 with AVO
        elif final == 0x73:  # s - save cursor
            self._save_cursor()
        elif final == 0x75:  # u - restore cursor
            self._restore_cursor()

    def _dispatch_csi_private(self, final, params):
        if final == 0x68:  # ?h - DECSET
            for p in params:
                if p == 1:
                    self.app_cursor_keys = True
                elif p == 25:
                    self.cursor_visible = True
                elif p == 1049:
                    self._save_cursor()
                    self._enter_alt_screen()
                elif p == 47 or p == 1047:
                    self._enter_alt_screen()
        elif final == 0x6C:  # ?l - DECRST
            for p in params:
                if p == 1:
                    self.app_cursor_keys = False
                elif p == 25:
                    self.cursor_visible = False
                elif p == 1049:
                    self._exit_alt_screen()
                    self._restore_cursor()
                elif p == 47 or p == 1047:
                    self._exit_alt_screen()

    # --- Parser ---

    def feed(self, data):
        # Reset scroll offset on new output
        if self.scroll_offset > 0:
            self.scroll_offset = 0
            self._mark_all_dirty()

        for b in data:
            state = self._state

            if state == _GROUND:
                if b == 0x1B:  # ESC
                    self._state = _ESC
                elif b == 0x08:  # BS
                    if self.cx > 0:
                        self.cx -= 1
                        self._wrap_next = False
                elif b == 0x09:  # TAB
                    self.cx = min((self.cx + 8) & ~7, self.cols - 1)
                    self._wrap_next = False
                elif b == 0x0A or b == 0x0B or b == 0x0C:  # LF/VT/FF
                    self._linefeed()
                    self._wrap_next = False
                elif b == 0x0D:  # CR
                    self.cx = 0
                    self._wrap_next = False
                elif b == 0x07:  # BEL
                    pass
                elif b >= 0x20:
                    self._put_char(b)

            elif state == _ESC:
                if b == 0x5B:  # [
                    self._state = _CSI
                    self._csi_params = []
                    self._csi_private = False
                    self._csi_buf = bytearray()
                elif b == 0x5D:  # ]
                    self._state = _OSC
                    self._osc_buf = bytearray()
                elif b == 0x44:  # D - Index (move down, scroll if needed)
                    self._linefeed()
                    self._state = _GROUND
                elif b == 0x4D:  # M - Reverse Index
                    self._reverse_index()
                    self._state = _GROUND
                elif b == 0x45:  # E - Next Line
                    self.cx = 0
                    self._linefeed()
                    self._state = _GROUND
                elif b == 0x37:  # 7 - Save cursor
                    self._save_cursor()
                    self._state = _GROUND
                elif b == 0x38:  # 8 - Restore cursor
                    self._restore_cursor()
                    self._state = _GROUND
                elif b == 0x63:  # c - Reset
                    self._reset()
                    self._state = _GROUND
                elif b == 0x23:  # # - ESC_HASH
                    self._state = _ESC_HASH
                elif b == 0x28 or b == 0x29:  # ( or ) - charset designation, ignore next byte
                    self._state = _GROUND  # simplified: just ignore
                else:
                    self._state = _GROUND

            elif state == _CSI:
                if b == 0x3F:  # ?
                    self._csi_private = True
                elif 0x30 <= b <= 0x39 or b == 0x3B:  # digit or ;
                    self._csi_buf.append(b)
                elif 0x40 <= b <= 0x7E:  # final byte
                    self._dispatch_csi(b)
                    self._state = _GROUND
                else:
                    # Unexpected byte - abort CSI
                    self._state = _GROUND

            elif state == _OSC:
                if b == 0x07:  # BEL - terminates OSC
                    self._state = _GROUND
                elif b == 0x1B:  # ESC (might be ST = ESC \)
                    self._state = _GROUND  # simplified
                elif b == 0x9C:  # ST
                    self._state = _GROUND
                # else accumulate (ignored)

            elif state == _ESC_HASH:
                # ESC # 8 = DECALN (fill screen with 'E' for testing)
                if b == 0x38:
                    ea = self._effective_attr()
                    for i in range(0, len(self.buf), 2):
                        self.buf[i] = 0x45  # 'E'
                        self.buf[i + 1] = ea
                    self._mark_all_dirty()
                self._state = _GROUND

    def _reset(self):
        self._clear_buf(self.buf)
        self.cx = 0
        self.cy = 0
        self.attr = 0x70
        self._bold = False
        self._reverse = False
        self.scroll_top = 0
        self.scroll_bot = self.rows - 1
        self.app_cursor_keys = False
        self.cursor_visible = True
        self._wrap_next = False
        self._state = _GROUND
        if self.in_alt:
            self._exit_alt_screen()
        self._mark_all_dirty()

    # --- Scrollback ---

    def scroll_back(self, lines):
        max_off = len(self.scrollback)
        old = self.scroll_offset
        self.scroll_offset = min(self.scroll_offset + lines, max_off)
        if self.scroll_offset != old:
            self._mark_all_dirty()

    def scroll_forward(self, lines):
        old = self.scroll_offset
        self.scroll_offset = max(self.scroll_offset - lines, 0)
        if self.scroll_offset != old:
            self._mark_all_dirty()

    # --- Resize ---

    def resize(self, new_cols, new_rows):
        old_buf = self.buf
        old_cols = self.cols
        old_rows = self.rows

        self.cols = new_cols
        self.rows = new_rows
        self.buf = bytearray(new_cols * new_rows * 2)
        self._clear_buf(self.buf)

        # Copy fitting content
        copy_rows = min(old_rows, new_rows)
        copy_cols = min(old_cols, new_cols)
        for r in range(copy_rows):
            for c in range(copy_cols):
                src = (r * old_cols + c) * 2
                dst = (r * new_cols + c) * 2
                self.buf[dst] = old_buf[src]
                self.buf[dst + 1] = old_buf[src + 1]

        # Clamp cursor
        self.cx = min(self.cx, new_cols - 1)
        self.cy = min(self.cy, new_rows - 1)
        self.scroll_top = 0
        self.scroll_bot = new_rows - 1

        # Handle alt buffer
        if self.in_alt and self.alt_buf:
            old_alt = self.alt_buf
            self.alt_buf = bytearray(new_cols * new_rows * 2)
            self._clear_buf(self.alt_buf)
            for r in range(min(old_rows, new_rows)):
                for c in range(min(old_cols, new_cols)):
                    src = (r * old_cols + c) * 2
                    dst = (r * new_cols + c) * 2
                    self.alt_buf[dst] = old_alt[src]
                    self.alt_buf[dst + 1] = old_alt[src + 1]
            del old_alt

        del old_buf
        self._wrap_next = False
        self._mark_all_dirty()
        collect()

    # --- Rendering ---

    def render(self, display, font):
        palette = _get_palette()
        cw = display.char_width(font)
        ch = display.font_height(font)

        if not self._dirty_rows:
            self.dirty = False
            return

        rows_to_draw = sorted(self._dirty_rows)
        self._dirty_rows = set()
        self.dirty = False

        cols = self.cols
        cols2 = cols * 2

        if self.scroll_offset > 0:
            # Drawing from scrollback + screen buffer
            sb_len = len(self.scrollback)
            sb_start = sb_len - self.scroll_offset
            if sb_start < 0:
                sb_start = 0

            for row in rows_to_draw:
                y = row * ch
                sb_row = sb_start + row
                if sb_row < sb_len:
                    # Row from scrollback
                    row_data = self.scrollback[sb_row]
                    self._render_row_data(display, font, row_data, cols, y, cw, ch, palette)
                else:
                    # Row from screen buffer
                    buf_row = sb_row - sb_len
                    if 0 <= buf_row < self.rows:
                        off = buf_row * cols2
                        self._render_row_data(display, font, self.buf[off:off + cols2], cols, y, cw, ch, palette)
                    else:
                        display.fill_rect(0, y, cols * cw, ch, palette[0])
        else:
            for row in rows_to_draw:
                y = row * ch
                off = row * cols2
                self._render_row_data(display, font, self.buf[off:off + cols2], cols, y, cw, ch, palette)

            # Draw cursor
            if self.cursor_visible and 0 <= self.cx < cols and 0 <= self.cy < self.rows:
                cur_y = self.cy * ch
                cur_x = self.cx * cw
                cur_off = self._cell_offset(self.cx, self.cy)
                cur_ch = self.buf[cur_off]
                cur_attr = self.buf[cur_off + 1]
                # Invert cursor cell
                fg_idx = (cur_attr >> 4) & 0x0F
                bg_idx = cur_attr & 0x0F
                display.fill_rect(cur_x, cur_y, cw, ch, palette[fg_idx])
                if cur_ch >= 0x20:
                    display.char(cur_x, cur_y, cur_ch, palette[bg_idx], font)

    def _render_row_data(self, display, font, row_data, cols, y, cw, ch, palette):
        # Batch consecutive cells with same attribute for efficiency
        x = 0
        i = 0
        while i < cols:
            attr = row_data[i * 2 + 1]
            fg_idx = (attr >> 4) & 0x0F
            bg_idx = attr & 0x0F
            fg_c = palette[fg_idx]
            bg_c = palette[bg_idx]

            # Gather run of same-attr cells
            run_start = i
            run_chars = bytearray()
            while i < cols and row_data[i * 2 + 1] == attr:
                run_chars.append(row_data[i * 2])
                i += 1

            run_x = run_start * cw
            run_w = len(run_chars) * cw

            # Draw background if non-default
            if bg_idx != 0:
                display.fill_rect(run_x, y, run_w, ch, bg_c)
            else:
                display.fill_rect(run_x, y, run_w, ch, palette[0])

            # Draw text - skip if all spaces with default bg
            has_text = False
            for c in run_chars:
                if c != 0x20:
                    has_text = True
                    break

            if has_text:
                # Convert bytearray to string for display.text()
                text_str = ""
                for c in run_chars:
                    text_str += chr(c) if c >= 0x20 else " "
                display.text(run_x, y, text_str, fg_c, font)
