"""Meshtastic client — LoRa mesh chat + node list.

Target device: LilyGO T-Deck Plus (tophyGo firmware). Relies on ctx.lora
providing the Meshtastic-compatible API defined in tophyGo:

    ctx.lora.send_text(channel, text) -> bool
    ctx.lora.poll() -> [{'channel','from','text','rssi','snr','time'}]
    ctx.lora.set_channel(name, psk)
    ctx.lora.my_id  (optional; hex string node id)
    ctx.lora.my_short_name  (optional; 4-char name)

If the Meshtastic protocol layer isn't yet wired up in the firmware (the
method raises NotImplementedError), the app still runs — it shows an
informative status in place of send/receive and everything else works.

Filtered off non-LoRa platforms via app.json `platforms: ["tdeck"]`.
"""

PLUGIN_NAME = "Meshtastic"

from micropython import const
from gc import collect
from picoware.core.input import (
    KEY_ENTER, KEY_ESC, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_BACKSPACE, KEY_F1, KEY_F2, KEY_F10,
)
from picoware.core.display import WHITE, CYAN, GREEN, ORANGE, DARK_GRAY, LIGHT_GRAY

_ST_CHAT = const(0)
_ST_NODES = const(1)
_ST_CHANNELS = const(2)
_ST_SETTINGS = const(3)
_ST_NOLORA = const(4)

_DATA_DIR = "picoware/data/meshtastic"
_MAX_CHARS = const(63)       # characters per line at FONT_8
_MSG_Y0 = const(10)          # top of message area (below header)
_MSG_LINES = const(33)       # number of visible message lines
_INPUT_Y = const(276)
_HINT_Y = const(290)
_FONT = const(0)             # FONT_8

_MAX_MSG_HISTORY = const(200)
_NODE_STALE_S = const(3600)  # drop nodes unseen for 1 hour


_state = _ST_CHAT
_cfg = None
_channels = []
_current_channel = 0         # index into _channels
_msgs = []                   # per-channel ring: [{ch, from, text, rssi, snr, t, mine}]
_nodes = {}                  # {id_hex: {short, long, last_seen, rssi, snr, lat, lon}}
_menu = None
_scroll = 0
_dirty = True
_input_buf = []
_input_cur = 0
_last_gps_share_ticks = 0


# ── storage ─────────────────────────────────────────────────────────

def _dirs(ctx):
    ctx.storage.mkdir("picoware/data")
    ctx.storage.mkdir(_DATA_DIR)


def _default_cfg():
    return {
        "short_name": "USER",
        "long_name": "tophyGo user",
        "channels": [{"name": "LongFast", "psk": ""}],
        "gps_share_interval_s": 0,  # 0 = off
    }


def _load_cfg(ctx):
    global _cfg, _channels
    d = ctx.storage.read_json(_DATA_DIR + "/settings.json")
    base = _default_cfg()
    base.update(d or {})
    _cfg = base
    _channels = _cfg.get("channels") or [{"name": "LongFast", "psk": ""}]


def _save_cfg(ctx):
    _dirs(ctx)
    ctx.storage.write_json(_DATA_DIR + "/settings.json", _cfg)


def _load_history(ctx):
    global _msgs
    d = ctx.storage.read_json(_DATA_DIR + "/history.json")
    _msgs = d if isinstance(d, list) else []
    if len(_msgs) > _MAX_MSG_HISTORY:
        _msgs = _msgs[-_MAX_MSG_HISTORY:]


def _save_history(ctx):
    _dirs(ctx)
    ctx.storage.write_json(_DATA_DIR + "/history.json", _msgs[-_MAX_MSG_HISTORY:])


# ── radio helpers ───────────────────────────────────────────────────

def _radio_available(ctx):
    return getattr(ctx, "lora", None) is not None


def _current_channel_name():
    if not _channels:
        return "LongFast"
    return _channels[_current_channel % len(_channels)]["name"]


def _apply_channel(ctx):
    """Tell the radio which channel we're on."""
    if not _radio_available(ctx):
        return
    ch = _channels[_current_channel % len(_channels)]
    try:
        ctx.lora.set_channel(ch["name"], ch.get("psk", ""))
    except Exception as e:
        print("LoRa set_channel error:", e)


def _drain_incoming(ctx):
    """Pull new messages from the radio, append to history, update nodes."""
    global _dirty
    if not _radio_available(ctx):
        return
    try:
        received = ctx.lora.poll()
    except NotImplementedError:
        return
    except Exception as e:
        print("LoRa poll error:", e)
        return

    if not received:
        return

    from utime import time
    now = time()
    chname = _current_channel_name()
    for pkt in received:
        # pkt: {'channel', 'from', 'text', 'rssi', 'snr', optional 'lat','lon','short','long'}
        frm = pkt.get("from", "?")
        text = pkt.get("text", "")
        ch = pkt.get("channel", chname)
        rssi = pkt.get("rssi", 0)
        snr = pkt.get("snr", 0)

        if text:
            _msgs.append({
                "ch": ch, "from": frm, "text": text,
                "rssi": rssi, "snr": snr, "t": now, "mine": False,
            })
            if len(_msgs) > _MAX_MSG_HISTORY:
                del _msgs[0]

        # node telemetry
        node = _nodes.get(frm) or {}
        node["last_seen"] = now
        node["rssi"] = rssi
        node["snr"] = snr
        if "short" in pkt:
            node["short"] = pkt["short"]
        if "long" in pkt:
            node["long"] = pkt["long"]
        if "lat" in pkt and "lon" in pkt:
            node["lat"] = pkt["lat"]
            node["lon"] = pkt["lon"]
        _nodes[frm] = node

    _dirty = True


def _prune_nodes():
    from utime import time
    now = time()
    stale = [k for k, v in _nodes.items() if now - v.get("last_seen", 0) > _NODE_STALE_S]
    for k in stale:
        del _nodes[k]


def _send_current(ctx, text):
    """Send text on the current channel. Returns a user-facing status string."""
    if not _radio_available(ctx):
        return "no LoRa"
    ch = _current_channel_name()
    try:
        ok = ctx.lora.send_text(ch, text)
    except NotImplementedError:
        return "Meshtastic layer pending"
    except Exception as e:
        return "err: " + str(e)[:30]
    return "" if ok else "send failed"


def _maybe_share_gps(ctx):
    """If configured, periodically broadcast our GPS fix as a text beacon."""
    global _last_gps_share_ticks
    interval = int(_cfg.get("gps_share_interval_s", 0) or 0)
    if interval <= 0:
        return
    gps = getattr(ctx, "gps", None)
    if gps is None:
        return
    from utime import ticks_ms, ticks_diff
    now = ticks_ms()
    if ticks_diff(now, _last_gps_share_ticks) < interval * 1000:
        return
    _last_gps_share_ticks = now
    try:
        gps.poll()
        fx = gps.fix()
    except Exception:
        fx = None
    if not fx or not fx.get("valid"):
        return
    msg = "pos {:.4f},{:.4f}".format(fx["lat"], fx["lon"])
    _send_current(ctx, msg)


# ── rendering ───────────────────────────────────────────────────────

def _wrap(text, w):
    out = []
    for para in text.split('\n'):
        while len(para) > w:
            brk = para.rfind(' ', 0, w + 1)
            if brk <= 0:
                brk = w
            out.append(para[:brk])
            para = para[brk:].lstrip()
        out.append(para)
    return out


def _draw_chat(ctx):
    global _dirty
    _dirty = False
    d = ctx.display
    d.clear()

    # header: channel + node count
    d.fill_rect(0, 0, d.w if hasattr(d, 'w') else 320, _MSG_Y0, DARK_GRAY)
    header = "#{} {}  nodes:{}".format(
        _current_channel, _current_channel_name(), len(_nodes),
    )
    d.text(2, 1, header[:_MAX_CHARS], LIGHT_GRAY, _FONT)

    # message list (only messages on current channel)
    chname = _current_channel_name()
    lines = []
    for m in _msgs:
        if m.get("ch") != chname:
            continue
        frm = m.get("from", "?")
        if m.get("mine"):
            pfx = "me: "
            color = WHITE
        else:
            short = _nodes.get(frm, {}).get("short")
            label = short if short else str(frm)[-4:]
            pfx = label + ": "
            color = CYAN
        for ln in _wrap(pfx + m.get("text", ""), _MAX_CHARS):
            lines.append((ln, color))

    total = len(lines)
    if total <= _MSG_LINES:
        start = 0
    else:
        start = max(0, total - _MSG_LINES - _scroll)
    end = min(start + _MSG_LINES, total)

    y = _MSG_Y0
    for i in range(start, end):
        t, c = lines[i]
        if t:
            d.text(2, y, t, c, _FONT)
        y += 8

    # input bar
    d.fill_rect(0, _INPUT_Y, d.w if hasattr(d, 'w') else 320, 12, DARK_GRAY)
    inp = "> " + "".join(_input_buf)
    d.text(2, _INPUT_Y + 2, inp[:_MAX_CHARS], WHITE, _FONT)
    cx = 2 + (_input_cur + 2) * 5
    if cx < (d.w if hasattr(d, 'w') else 320) - 2:
        d.fill_rect(cx, _INPUT_Y + 2, 1, 8, WHITE)

    # hint bar
    d.fill_rect(0, _HINT_Y, d.w if hasattr(d, 'w') else 320, 30, DARK_GRAY)
    d.text(2, _HINT_Y + 2, "ENTER:send F1:chan F2:nodes F10:cfg ESC:exit",
           LIGHT_GRAY, _FONT)
    d.swap()


def _draw_nodes(ctx):
    global _dirty
    _dirty = False
    d = ctx.display
    d.clear()
    w = d.w if hasattr(d, 'w') else 320
    h = d.h if hasattr(d, 'h') else 320

    d.fill_rect(0, 0, w, _MSG_Y0, DARK_GRAY)
    d.text(2, 1, "Nodes ({})   F2:back".format(len(_nodes)), LIGHT_GRAY, _FONT)

    from utime import time
    now = time()
    y = _MSG_Y0 + 2
    if not _nodes:
        d.text(4, y, "No nodes seen yet.", LIGHT_GRAY, _FONT)
    else:
        items = sorted(_nodes.items(), key=lambda kv: -kv[1].get("last_seen", 0))
        for nid, info in items:
            if y > h - 10:
                break
            age = now - info.get("last_seen", now)
            short = info.get("short") or str(nid)[-4:]
            rssi = info.get("rssi", 0)
            snr = info.get("snr", 0)
            age_s = "{}s".format(age) if age < 3600 else "{}m".format(age // 60)
            line = "{:<8s} {:>4d}dBm {:>4d}snr  {}".format(
                short[:8], rssi, snr, age_s,
            )
            color = GREEN if age < 300 else ORANGE if age < 1800 else LIGHT_GRAY
            d.text(4, y, line[:_MAX_CHARS], color, _FONT)
            y += 10
    d.swap()


def _show_status(ctx, title, message):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    d.fill_rect(0, 0, d.w if hasattr(d, 'w') else 320, fh + 10, d.fg)
    d.text(4, 5, title, d.bg)
    d.text(10, fh + 30, message, d.fg)
    d.text(10, fh + 50, "Press ESC to return", d.fg)
    d.swap()


# ── lifecycle ───────────────────────────────────────────────────────

def start(ctx):
    global _state, _dirty, _menu, _msgs, _nodes, _current_channel
    _load_cfg(ctx)
    _load_history(ctx)
    _nodes = {}
    _current_channel = 0
    _menu = None
    _dirty = True

    if not _radio_available(ctx):
        _state = _ST_NOLORA
    else:
        _apply_channel(ctx)
        _state = _ST_CHAT
    return True


def run(ctx):
    global _state, _menu, _dirty, _scroll, _input_buf, _input_cur
    global _current_channel, _cfg, _msgs, _nodes

    # background tasks every frame
    _drain_incoming(ctx)
    _maybe_share_gps(ctx)
    _prune_nodes()

    k = ctx.input.key

    # ── no-lora fallback ──
    if _state == _ST_NOLORA:
        _show_status(ctx, "Meshtastic",
                     "LoRa hardware not available on this device.")
        if k == KEY_ESC or k == KEY_BACKSPACE:
            ctx.back()
        return

    # ── chat view ──
    if _state == _ST_CHAT:
        if k == KEY_ENTER:
            text = "".join(_input_buf).strip()
            if text:
                _input_buf.clear()
                _input_cur = 0
                status = _send_current(ctx, text)
                from utime import time
                entry = {
                    "ch": _current_channel_name(),
                    "from": "me", "text": text,
                    "rssi": 0, "snr": 0, "t": time(), "mine": True,
                }
                if status:
                    entry["text"] = text + "  [" + status + "]"
                _msgs.append(entry)
                if len(_msgs) > _MAX_MSG_HISTORY:
                    del _msgs[0]
                _save_history(ctx)
            _dirty = True
            return
        if k == KEY_BACKSPACE:
            if _input_cur > 0:
                _input_buf.pop(_input_cur - 1)
                _input_cur -= 1
                _dirty = True
            return
        if k == KEY_LEFT:
            if _input_cur > 0:
                _input_cur -= 1
                _dirty = True
            return
        if k == KEY_RIGHT:
            if _input_cur < len(_input_buf):
                _input_cur += 1
                _dirty = True
            return
        if k == KEY_UP:
            _scroll += 3
            _dirty = True
            return
        if k == KEY_DOWN:
            _scroll = max(0, _scroll - 3)
            _dirty = True
            return
        if k == KEY_F1:
            # cycle to next channel
            if _channels:
                _current_channel = (_current_channel + 1) % len(_channels)
                _apply_channel(ctx)
                _scroll = 0
                _dirty = True
            return
        if k == KEY_F2:
            _state = _ST_NODES
            _dirty = True
            return
        if k == KEY_F10:
            _save_history(ctx)
            _state = _ST_SETTINGS
            _menu = None
            _dirty = True
            return
        if k == KEY_ESC:
            _save_history(ctx)
            ctx.back()
            return
        c = ctx.input.char
        if c and c != '\n' and c != '\t':
            _input_buf.insert(_input_cur, c)
            _input_cur += 1
            _dirty = True
            return
        if _dirty:
            _draw_chat(ctx)
        return

    # ── node list ──
    if _state == _ST_NODES:
        if k == KEY_F2 or k == KEY_ESC or k == KEY_BACKSPACE:
            _state = _ST_CHAT
            _dirty = True
            return
        if _dirty:
            _draw_nodes(ctx)
        return

    # ── settings ──
    if _state == _ST_SETTINGS:
        if _menu is None:
            from picoware.ui.menu import Menu
            items = [
                "Short name: " + _cfg.get("short_name", ""),
                "Long name: " + _cfg.get("long_name", ""),
                "Add channel",
                "GPS share: " + (
                    "{}s".format(_cfg.get("gps_share_interval_s"))
                    if _cfg.get("gps_share_interval_s") else "off"
                ),
                "Clear history",
                "Back",
            ]
            _menu = Menu(ctx.display, items, title="Meshtastic Settings")
            _dirty = True
        if k != -1:
            r = _menu.handle_input(k)
            if r == -1 or r == 5:
                _state = _ST_CHAT
                _menu = None
                _dirty = True
                return
            if r == 0:
                from picoware.ui.dialog import text_input
                v = text_input(ctx.display, ctx.input, "Short name (max 4)",
                               _cfg.get("short_name", ""))
                if v is not None:
                    _cfg["short_name"] = v[:4]
                    _save_cfg(ctx)
                _menu = None
                _dirty = True
                return
            if r == 1:
                from picoware.ui.dialog import text_input
                v = text_input(ctx.display, ctx.input, "Long name",
                               _cfg.get("long_name", ""))
                if v is not None:
                    _cfg["long_name"] = v[:32]
                    _save_cfg(ctx)
                _menu = None
                _dirty = True
                return
            if r == 2:
                from picoware.ui.dialog import text_input
                name = text_input(ctx.display, ctx.input, "Channel name", "")
                if name:
                    psk = text_input(ctx.display, ctx.input,
                                     "PSK (hex, blank=default)", "")
                    _channels.append({"name": name, "psk": psk or ""})
                    _cfg["channels"] = _channels
                    _save_cfg(ctx)
                _menu = None
                _dirty = True
                return
            if r == 3:
                from picoware.ui.dialog import text_input
                v = text_input(ctx.display, ctx.input,
                               "GPS share seconds (0=off)",
                               str(_cfg.get("gps_share_interval_s", 0)))
                if v is not None:
                    try:
                        _cfg["gps_share_interval_s"] = max(0, int(v))
                    except ValueError:
                        pass
                    _save_cfg(ctx)
                _menu = None
                _dirty = True
                return
            if r == 4:
                from picoware.ui.dialog import confirm
                if confirm(ctx.display, ctx.input, "Delete all messages?"):
                    _msgs.clear()
                    _save_history(ctx)
                _menu = None
                _dirty = True
                return
            _dirty = True
        if _dirty:
            _menu.draw(force=True)
            _dirty = False
        return


def stop(ctx):
    global _state, _cfg, _channels, _current_channel, _msgs, _nodes, _menu
    global _scroll, _dirty, _input_buf, _input_cur, _last_gps_share_ticks
    if _radio_available(ctx) and _msgs:
        try:
            _save_history(ctx)
        except Exception:
            pass
    _state = _ST_CHAT
    _cfg = None
    _channels = []
    _current_channel = 0
    _msgs = []
    _nodes = {}
    _menu = None
    _scroll = 0
    _dirty = True
    _input_buf = []
    _input_cur = 0
    _last_gps_share_ticks = 0
    collect()
