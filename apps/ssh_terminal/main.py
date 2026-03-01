"""
SSH Terminal Plugin for PicoCalcOS
Interactive SSH terminal with VT100 emulation, persistent shell sessions,
saved session management, and configurable fonts.
"""

PLUGIN_NAME = "SSH Terminal"

from micropython import const
from gc import collect

# App states
_ST_SESSION_LIST = const(0)
_ST_SESSION_EDIT = const(1)
_ST_CONNECTING = const(2)
_ST_TERMINAL = const(3)
_ST_SETTINGS = const(4)
_ST_DISCONNECTED = const(5)

# Font table: (font_const, char_width, char_height, cols, rows)
_FONTS = (
    (0, 5, 8, 64, 40),    # FONT_8
    (1, 7, 12, 45, 26),   # FONT_12
    (2, 11, 16, 29, 20),  # FONT_16
    (3, 14, 20, 22, 16),  # FONT_20
    (4, 17, 24, 18, 13),  # FONT_24
)
_FONT_LABELS = ("5x8 (64x40)", "7x12 (45x26)", "11x16 (29x20)", "14x20 (22x16)", "17x24 (18x13)")

# Data paths
_SESSIONS_PATH = "picoware/data/ssh/sessions.json"
_SETTINGS_PATH = "picoware/data/ssh/settings.json"

# State
_state = _ST_SESSION_LIST
_ssh = None
_term = None
_menu = None
_sessions = []
_cur_session = None  # index into _sessions
_app_settings = {"font": 1, "scrollback": 100}
_need_draw = True
_edit_session = None  # dict being edited


def _ensure_dirs(ctx):
    ctx.storage.mkdir("picoware/data")
    ctx.storage.mkdir("picoware/data/ssh")


def _load_sessions(ctx):
    global _sessions
    data = ctx.storage.read_json(_SESSIONS_PATH)
    if isinstance(data, list):
        _sessions = data
    else:
        _sessions = []
        # Migrate old single-session format
        old = ctx.storage.read_json("picoware/data/ssh/session.json")
        if old and old.get("host"):
            _sessions.append({
                "name": old.get("host", ""),
                "host": old.get("host", ""),
                "port": old.get("port", "22"),
                "user": old.get("user", ""),
                "pass": old.get("pass", ""),
            })
            _save_sessions(ctx)


def _save_sessions(ctx):
    _ensure_dirs(ctx)
    ctx.storage.write_json(_SESSIONS_PATH, _sessions)


def _load_app_settings(ctx):
    global _app_settings
    data = ctx.storage.read_json(_SETTINGS_PATH)
    if data:
        _app_settings["font"] = data.get("font", 1)
        _app_settings["scrollback"] = data.get("scrollback", 100)


def _save_app_settings(ctx):
    _ensure_dirs(ctx)
    ctx.storage.write_json(_SETTINGS_PATH, _app_settings)


def _get_font_info():
    idx = _app_settings["font"]
    if idx < 0 or idx >= len(_FONTS):
        idx = 1
    return _FONTS[idx]


def _show_status(ctx, msg):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, "SSH Terminal", d.bg)
    tw = d.text_width(msg)
    d.text((320 - tw) // 2, 150, msg, d.fg)
    d.swap()


def _build_session_menu_items():
    items = []
    for s in _sessions:
        label = s.get("name", s.get("host", "?"))
        host = s.get("host", "")
        if host and host != label:
            label += " (" + host + ")"
        items.append(label)
    items.append("+ New Session")
    items.append("Settings")
    return items


def _enter_session_list(ctx):
    global _state, _menu, _need_draw
    from picoware.ui.menu import Menu
    _state = _ST_SESSION_LIST
    items = _build_session_menu_items()
    _menu = Menu(ctx.display, items, title="SSH Sessions")
    _need_draw = True


def _enter_settings(ctx):
    global _state, _menu, _need_draw
    from picoware.ui.menu import Menu
    _state = _ST_SETTINGS
    items = []
    for i, label in enumerate(_FONT_LABELS):
        prefix = "> " if i == _app_settings["font"] else "  "
        items.append(prefix + label)
    _menu = Menu(ctx.display, items, title="Font Size")
    _need_draw = True


def _start_edit_session(ctx, session_dict):
    global _state, _edit_session, _need_draw
    _state = _ST_SESSION_EDIT
    _edit_session = dict(session_dict)  # work on a copy
    _need_draw = True


def _connect_session(ctx, idx):
    global _state, _ssh, _term, _cur_session, _need_draw
    s = _sessions[idx]
    _cur_session = idx

    host = s.get("host", "")
    port = int(s.get("port", "22"))
    user = s.get("user", "")
    pw = s.get("pass", "")

    if not host or not user:
        from picoware.ui.dialog import alert
        alert(ctx.display, ctx.input, "Set host and username first", "SSH")
        _enter_session_list(ctx)
        return

    _show_status(ctx, "Connecting to " + host + "...")
    _state = _ST_CONNECTING
    _need_draw = False

    from _ssh_protocol import SSHClient
    _ssh = SSHClient()

    if not _ssh.connect(host, port, user, pw):
        err = _ssh.error or "Connection failed"
        _ssh = None
        collect()
        from picoware.ui.dialog import alert
        alert(ctx.display, ctx.input, err[:60], "SSH Error")
        _enter_session_list(ctx)
        return

    # Open PTY shell
    fi = _get_font_info()
    cols, rows = fi[3], fi[4]
    try:
        _ssh.open_shell(cols, rows)
    except Exception as e:
        err = str(e)
        _ssh.disconnect()
        _ssh = None
        collect()
        from picoware.ui.dialog import alert
        alert(ctx.display, ctx.input, "Shell: " + err[:50], "SSH Error")
        _enter_session_list(ctx)
        return

    # Create terminal emulator
    from _vt100 import TermScreen
    _term = TermScreen(
        cols, rows,
        send_func=_ssh.send_data,
        scrollback_max=_app_settings["scrollback"],
    )

    _state = _ST_TERMINAL
    _need_draw = True
    # Clear display for terminal
    ctx.display.clear()
    ctx.display.swap()


def _disconnect(ctx):
    global _ssh, _term
    if _ssh:
        try:
            _ssh.disconnect()
        except Exception:
            pass
        _ssh = None
    _term = None
    collect()


def _enter_disconnected(ctx):
    global _state, _menu, _need_draw
    from picoware.ui.menu import Menu
    _state = _ST_DISCONNECTED
    _menu = Menu(ctx.display, ["Reconnect", "Back to Sessions"], title="Disconnected")
    _need_draw = True


# --- Key mapping for terminal ---

# VT100 escape sequences for function/special keys
_KEY_SEQS = None

def _get_key_seqs():
    global _KEY_SEQS
    if _KEY_SEQS is None:
        from picoware.core.input import (
            KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5,
            KEY_F6, KEY_F7, KEY_F8, KEY_F9,
            KEY_DEL, KEY_INSERT, KEY_TAB,
            KEY_ENTER, KEY_BACKSPACE, KEY_ESC,
        )
        _KEY_SEQS = {
            KEY_F1: b"\x1bOP",
            KEY_F2: b"\x1bOQ",
            KEY_F3: b"\x1bOR",
            KEY_F4: b"\x1bOS",
            KEY_F5: b"\x1b[15~",
            KEY_F6: b"\x1b[17~",
            KEY_F7: b"\x1b[18~",
            KEY_F8: b"\x1b[19~",
            KEY_F9: b"\x1b[20~",
            KEY_DEL: b"\x1b[3~",
            KEY_INSERT: b"\x1b[2~",
            KEY_TAB: b"\t",
            KEY_ENTER: b"\r",
            KEY_BACKSPACE: b"\x7f",
            KEY_ESC: b"\x1b",
        }
    return _KEY_SEQS


def _handle_terminal_key(ctx):
    from picoware.core.input import (
        KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
        KEY_F10, KEY_PAGE_UP, KEY_PAGE_DOWN,
    )

    k = ctx.input.key
    if k == -1:
        return

    # F10 = open settings overlay
    if k == KEY_F10:
        _enter_settings(ctx)
        return

    # Page Up/Down: scrollback in main screen, send escape in alt screen
    if k == KEY_PAGE_UP:
        if _term and not _term.in_alt:
            _term.scroll_back(_term.rows // 2)
        elif _ssh:
            _ssh.send_data(b"\x1b[5~")
        return
    if k == KEY_PAGE_DOWN:
        if _term and not _term.in_alt:
            _term.scroll_forward(_term.rows // 2)
        elif _ssh:
            _ssh.send_data(b"\x1b[6~")
        return

    # Arrow keys
    if k == KEY_UP:
        if _term and _term.app_cursor_keys:
            _ssh.send_data(b"\x1bOA")
        else:
            _ssh.send_data(b"\x1b[A")
        return
    if k == KEY_DOWN:
        if _term and _term.app_cursor_keys:
            _ssh.send_data(b"\x1bOB")
        else:
            _ssh.send_data(b"\x1b[B")
        return
    if k == KEY_RIGHT:
        if _term and _term.app_cursor_keys:
            _ssh.send_data(b"\x1bOC")
        else:
            _ssh.send_data(b"\x1b[C")
        return
    if k == KEY_LEFT:
        if _term and _term.app_cursor_keys:
            _ssh.send_data(b"\x1bOD")
        else:
            _ssh.send_data(b"\x1b[D")
        return

    # Special keys from lookup table
    key_seqs = _get_key_seqs()
    seq = key_seqs.get(k)
    if seq:
        _ssh.send_data(seq)
        return

    # Control characters (key values 1-26 = Ctrl+A through Ctrl+Z)
    if 1 <= k <= 26:
        _ssh.send_data(bytes([k]))
        return

    # Printable characters
    ch = ctx.input.char
    if ch and isinstance(ch, str) and len(ch) == 1:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            _ssh.send_data(ch.encode())


# --- App lifecycle ---

def start(ctx):
    global _state, _ssh, _term, _menu, _sessions, _cur_session
    global _app_settings, _need_draw, _edit_session

    if not ctx.wifi or not ctx.wifi.is_connected:
        from picoware.ui.dialog import alert
        alert(ctx.display, ctx.input, "WiFi not connected", "SSH Terminal")
        return False

    _ssh = None
    _term = None
    _menu = None
    _cur_session = None
    _edit_session = None
    _need_draw = True

    _load_app_settings(ctx)
    _load_sessions(ctx)
    _enter_session_list(ctx)
    return True


def run(ctx):
    global _state, _ssh, _term, _menu, _need_draw
    global _sessions, _cur_session, _edit_session, _app_settings

    k = ctx.input.key

    # --- Session List ---
    if _state == _ST_SESSION_LIST:
        if _menu:
            result = _menu.handle_input(k)
            if result is not None and result >= 0:
                n_sessions = len(_sessions)
                if result < n_sessions:
                    _connect_session(ctx, result)
                    return
                elif result == n_sessions:
                    # "+ New Session"
                    _cur_session = None
                    _start_edit_session(ctx, {
                        "name": "", "host": "", "port": "22",
                        "user": "", "pass": "",
                    })
                    return
                elif result == n_sessions + 1:
                    # "Settings"
                    _enter_settings(ctx)
                    return
            elif result == -1:
                ctx.back()
                return

            # Handle 'e' to edit, DEL to delete
            if k == KEY_DEL_VAL:
                idx = _menu.selected
                if idx < len(_sessions):
                    from picoware.ui.dialog import confirm
                    name = _sessions[idx].get("name", _sessions[idx].get("host", "?"))
                    if confirm(ctx.display, ctx.input, "Delete '" + name + "'?", "Confirm"):
                        _sessions.pop(idx)
                        _save_sessions(ctx)
                        _menu.items = _build_session_menu_items()
                    _need_draw = True
            elif k == ord('e') or k == ord('E'):
                idx = _menu.selected
                if idx < len(_sessions):
                    _start_edit_session(ctx, _sessions[idx])
                    _cur_session = idx
                    return

            _menu.draw()

    # --- Session Edit ---
    elif _state == _ST_SESSION_EDIT:
        from picoware.ui.dialog import text_input
        d = ctx.display

        fields = [
            ("Name", "name", _edit_session.get("name", "")),
            ("Host", "host", _edit_session.get("host", "")),
            ("Port", "port", _edit_session.get("port", "22")),
            ("Username", "user", _edit_session.get("user", "")),
            ("Password", "pass", _edit_session.get("pass", "")),
        ]

        cancelled = False
        for label, key, initial in fields:
            result = text_input(d, ctx.input, label, initial)
            if result is None:
                cancelled = True
                break
            _edit_session[key] = result

        if not cancelled and _edit_session.get("host"):
            if not _edit_session.get("name"):
                _edit_session["name"] = _edit_session["host"]
            if _cur_session is not None and _cur_session < len(_sessions):
                # Editing existing
                _sessions[_cur_session] = _edit_session
            else:
                # New session
                _sessions.append(_edit_session)
            _save_sessions(ctx)

        _cur_session = None
        _edit_session = None
        _enter_session_list(ctx)

    # --- Connecting (handled inline by _connect_session) ---
    elif _state == _ST_CONNECTING:
        pass

    # --- Terminal ---
    elif _state == _ST_TERMINAL:
        if not _ssh or not _ssh._connected:
            _disconnect(ctx)
            _enter_disconnected(ctx)
            return

        # Poll SSH data
        try:
            data = _ssh.poll_data()
            if data:
                _term.feed(data)
        except Exception:
            _disconnect(ctx)
            _enter_disconnected(ctx)
            return

        # Check disconnect
        if _ssh._channel_closed:
            _disconnect(ctx)
            _enter_disconnected(ctx)
            return

        # Handle keyboard
        if k != -1:
            _handle_terminal_key(ctx)
            # If state changed (e.g. F10 pressed), return
            if _state != _ST_TERMINAL:
                return

        # Render
        if _term and _term.dirty:
            fi = _get_font_info()
            _term.render(ctx.display, fi[0])
            ctx.display.swap()

    # --- Settings ---
    elif _state == _ST_SETTINGS:
        if _menu:
            result = _menu.handle_input(k)
            if result is not None and result >= 0 and result < len(_FONTS):
                _app_settings["font"] = result
                _save_app_settings(ctx)
                # If in a live session, resize terminal
                if _term and _ssh and _ssh._connected:
                    fi = _FONTS[result]
                    new_cols, new_rows = fi[3], fi[4]
                    _term.resize(new_cols, new_rows)
                    try:
                        _ssh.send_window_change(new_cols, new_rows)
                    except Exception:
                        pass
                    ctx.display.clear()
                    _term._mark_all_dirty()
                    _state = _ST_TERMINAL
                    _need_draw = True
                    _menu = None
                else:
                    _enter_session_list(ctx)
                return
            elif result == -1:
                if _term and _ssh and _ssh._connected:
                    _state = _ST_TERMINAL
                    _need_draw = True
                    _term._mark_all_dirty()
                    _menu = None
                else:
                    _enter_session_list(ctx)
                return
            _menu.draw()

    # --- Disconnected ---
    elif _state == _ST_DISCONNECTED:
        if _menu:
            result = _menu.handle_input(k)
            if result == 0:
                # Reconnect
                if _cur_session is not None and _cur_session < len(_sessions):
                    _menu = None
                    _connect_session(ctx, _cur_session)
                else:
                    _enter_session_list(ctx)
                return
            elif result == 1 or result == -1:
                _enter_session_list(ctx)
                return
            _menu.draw()


# Resolve KEY_DEL value once
try:
    from picoware.core.input import KEY_DEL
    KEY_DEL_VAL = KEY_DEL
except Exception:
    KEY_DEL_VAL = 0xD4


def stop(ctx):
    global _ssh, _term, _menu, _state, _need_draw
    global _sessions, _cur_session, _edit_session, _app_settings

    _disconnect(ctx)
    _menu = None
    _state = _ST_SESSION_LIST
    _need_draw = True
    _sessions = []
    _cur_session = None
    _edit_session = None
    collect()
