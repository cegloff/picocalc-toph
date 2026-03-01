"""
SSH Terminal Plugin for PicoCalcOS
Connect to remote servers via SSH-2 and execute commands
"""

PLUGIN_NAME = "SSH Terminal"

from micropython import const
from gc import collect

# States
_ST_MENU_DISC = const(0)
_ST_MENU_CONN = const(1)
_ST_OUTPUT = const(2)

# Menu items (disconnected)
_DISC_ITEMS = ["Connect", "Set Host", "Set Port", "Set Username", "Set Password"]
# Menu items (connected)
_CONN_ITEMS = ["Run Command", "View Output", "Disconnect"]

# State
_state = _ST_MENU_DISC
_menu_sel = 0
_ssh = None
_scroll = 0
_need_draw = True
_host = ""
_port = "22"
_user = ""
_pw = ""
_CRED_PATH = "picoware/data/ssh/session.json"


def _load_creds(ctx):
    global _host, _port, _user, _pw
    data = ctx.storage.read_json(_CRED_PATH)
    if data:
        _host = data.get("host", "")
        _port = data.get("port", "22")
        _user = data.get("user", "")
        _pw = data.get("pass", "")


def _save_creds(ctx):
    ctx.storage.mkdir("picoware/data")
    ctx.storage.mkdir("picoware/data/ssh")
    ctx.storage.write_json(_CRED_PATH, {
        "host": _host, "port": _port, "user": _user, "pass": _pw,
    })


def _draw_menu(ctx, items, title, status=""):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    item_h = fh + 8

    # title bar
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, title, d.bg)

    # status line
    y = fh + 14
    if status:
        d.text(8, y, status, d.fg)
        y += fh + 4

    # menu items
    for i, label in enumerate(items):
        if i == _menu_sel:
            d.fill_rect(0, y, 320, item_h, d.fg)
            d.text(8, y + 4, label, d.bg)
        else:
            d.text(8, y + 4, label, d.fg)
        y += item_h

    # credentials summary at bottom
    y = 320 - fh * 3 - 8
    d.text(8, y, "Host: " + (_host or "-"), d.fg)
    d.text(8, y + fh + 2, "User: " + (_user or "-"), d.fg)
    d.text(8, y + fh * 2 + 4, "Port: " + _port, d.fg)

    d.swap()


def _draw_output(ctx):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    cw = d.char_width()

    # title bar
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, "SSH Output", d.bg)

    if not _ssh or not _ssh.output:
        d.text(80, 150, "No output yet", d.fg)
        d.text(8, 320 - fh - 4, "ESC=back", d.fg)
        d.swap()
        return

    lines = _ssh.output
    max_chars = 320 // cw
    # wrap long lines
    wrapped = []
    for line in lines:
        line = line.rstrip('\r')
        if len(line) <= max_chars:
            wrapped.append(line)
        else:
            while len(line) > max_chars:
                wrapped.append(line[:max_chars])
                line = line[max_chars:]
            if line:
                wrapped.append(line)

    # visible area
    y_start = fh + 14
    visible = (320 - y_start - fh - 8) // (fh + 2)
    total = len(wrapped)

    # clamp scroll
    global _scroll
    max_scroll = max(0, total - visible)
    if _scroll > max_scroll:
        _scroll = max_scroll
    if _scroll < 0:
        _scroll = 0

    # draw lines
    y = y_start
    end = min(_scroll + visible, total)
    for i in range(_scroll, end):
        d.text(4, y, wrapped[i], d.fg)
        y += fh + 2

    # scroll indicator
    if total > visible:
        bar_h = max(10, (320 - y_start) * visible // total)
        bar_y = y_start + ((320 - y_start - bar_h) * _scroll // max(1, max_scroll))
        d.fill_rect(317, bar_y, 3, bar_h, d.fg)

    d.text(8, 320 - fh - 4, "UP/DN=scroll ESC=back", d.fg)
    d.swap()


def _show_status(ctx, msg):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, "SSH Terminal", d.bg)
    tw = d.text_width(msg)
    d.text((320 - tw) // 2, 150, msg, d.fg)
    d.swap()


def start(ctx):
    global _state, _menu_sel, _ssh, _scroll, _need_draw

    # check WiFi
    if not ctx.wifi or not ctx.wifi.is_connected:
        from picoware.ui.dialog import alert
        alert(ctx.display, ctx.input, "WiFi not connected", "SSH Terminal")
        return False

    _load_creds(ctx)

    _state = _ST_MENU_DISC
    _menu_sel = 0
    _scroll = 0
    _need_draw = True
    _ssh = None
    return True


def run(ctx):
    global _state, _menu_sel, _ssh, _scroll, _need_draw
    global _host, _port, _user, _pw

    from picoware.core.input import (
        KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE, KEY_ESC,
    )
    from picoware.ui.dialog import text_input, alert

    d = ctx.display
    k = ctx.input.key

    if _state == _ST_MENU_DISC:
        items = _DISC_ITEMS
        n = len(items)

        if k == KEY_UP and _menu_sel > 0:
            _menu_sel -= 1
            _need_draw = True
        elif k == KEY_DOWN and _menu_sel < n - 1:
            _menu_sel += 1
            _need_draw = True
        elif k == KEY_ESC or k == KEY_BACKSPACE:
            ctx.back()
            return
        elif k == KEY_ENTER:
            choice = items[_menu_sel]

            if choice == "Connect":
                if not _host or not _user:
                    alert(d, ctx.input, "Set host and username first", "SSH")
                    _need_draw = True
                else:
                    _show_status(ctx, "Connecting to " + _host + "...")
                    from _ssh_protocol import SSHClient
                    _ssh = SSHClient()
                    port_num = int(_port) if _port else 22
                    if _ssh.connect(_host, port_num, _user, _pw):
                        _state = _ST_MENU_CONN
                        _menu_sel = 0
                        _need_draw = True
                    else:
                        err = _ssh.error or "Connection failed"
                        alert(d, ctx.input, err[:60], "SSH Error")
                        _ssh = None
                        collect()
                        _need_draw = True

            elif choice == "Set Host":
                result = text_input(d, ctx.input, "SSH Host", _host)
                if result is not None:
                    _host = result
                    _save_creds(ctx)
                _need_draw = True

            elif choice == "Set Port":
                result = text_input(d, ctx.input, "SSH Port", _port)
                if result is not None:
                    _port = result
                    _save_creds(ctx)
                _need_draw = True

            elif choice == "Set Username":
                result = text_input(d, ctx.input, "Username", _user)
                if result is not None:
                    _user = result
                    _save_creds(ctx)
                _need_draw = True

            elif choice == "Set Password":
                result = text_input(d, ctx.input, "Password", _pw)
                if result is not None:
                    _pw = result
                    _save_creds(ctx)
                _need_draw = True

        if _need_draw:
            status = ""
            if _ssh and _ssh.is_connected:
                status = "Connected to " + _host
            _draw_menu(ctx, items, "SSH Terminal", status)
            _need_draw = False

    elif _state == _ST_MENU_CONN:
        items = _CONN_ITEMS
        n = len(items)

        if k == KEY_UP and _menu_sel > 0:
            _menu_sel -= 1
            _need_draw = True
        elif k == KEY_DOWN and _menu_sel < n - 1:
            _menu_sel += 1
            _need_draw = True
        elif k == KEY_ESC or k == KEY_BACKSPACE:
            ctx.back()
            return
        elif k == KEY_ENTER:
            choice = items[_menu_sel]

            if choice == "Run Command":
                cmd = text_input(d, ctx.input, "Command", "")
                if cmd is not None and cmd.strip():
                    _show_status(ctx, "Executing...")
                    _ssh.execute_command(cmd)
                    _state = _ST_OUTPUT
                    _scroll = 0
                    # auto-scroll to bottom
                    _scroll = max(0, len(_ssh.output) - 10)
                    _need_draw = True
                else:
                    _need_draw = True

            elif choice == "View Output":
                _state = _ST_OUTPUT
                _scroll = 0
                if _ssh and _ssh.output:
                    _scroll = max(0, len(_ssh.output) - 10)
                _need_draw = True

            elif choice == "Disconnect":
                if _ssh:
                    _ssh.disconnect()
                    _ssh = None
                    collect()
                _state = _ST_MENU_DISC
                _menu_sel = 0
                _need_draw = True

        if _need_draw:
            _draw_menu(ctx, items, "SSH: " + _host, "Connected")
            _need_draw = False

    elif _state == _ST_OUTPUT:
        if k == KEY_UP:
            _scroll -= 1
            _need_draw = True
        elif k == KEY_DOWN:
            _scroll += 1
            _need_draw = True
        elif k == KEY_ESC or k == KEY_BACKSPACE:
            _state = _ST_MENU_CONN
            _menu_sel = 0
            _need_draw = True
        elif k == KEY_ENTER:
            # quick command from output view
            cmd = text_input(d, ctx.input, "Command", "")
            if cmd is not None and cmd.strip():
                _show_status(ctx, "Executing...")
                _ssh.execute_command(cmd)
                _scroll = max(0, len(_ssh.output) - 10)
            _need_draw = True

        if _need_draw:
            _draw_output(ctx)
            _need_draw = False


def stop(ctx):
    global _ssh, _state, _menu_sel, _scroll, _need_draw
    global _host, _port, _user, _pw

    if _ssh:
        _ssh.disconnect()
        _ssh = None

    _state = _ST_MENU_DISC
    _menu_sel = 0
    _scroll = 0
    _need_draw = True
    _host = ""
    _port = "22"
    _user = ""
    _pw = ""
    collect()
