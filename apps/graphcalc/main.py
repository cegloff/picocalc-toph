"""Graph Calculator - TI-89 style. App shell: lifecycle, state, UI chrome."""

from micropython import const
from gc import collect

PLUGIN_NAME = "Graph Calc"

# View states
_ST_HOME = const(0)
_ST_YEDIT = const(1)
_ST_WINDOW = const(2)
_ST_GRAPH = const(3)
_ST_TABLE = const(4)
_ST_TBLSET = const(5)
_ST_MODE = const(6)

# Layout
_SB_H = const(10)
_CONTENT_Y = const(10)
_CONTENT_H = const(274)
_ENTRY_Y = const(284)
_ENTRY_H = const(18)
_TB_Y = const(302)
_TB_H = const(18)

# State dict
_S = None
# Cached module refs
_mod = None
_ctx = None
# Status message + timer
_status_msg = None
_status_t = 0
# Entry line editing context
_editing = False
_edit_label = ""


def _init_state():
    return {
        "angle": "RAD", "gtype": "FUNC", "nfmt": "AUTO",
        "view": _ST_HOME, "prev": _ST_HOME,
        "entry": [], "cur": 0, "escr": 0, "eactive": True,
        "dd": False, "ddi": [], "dds": 0, "ddf": -1,
        "ffunc": [["", False] for _ in range(6)],
        "fpar": [["", "", False] for _ in range(3)],
        "fpol": [["", False] for _ in range(6)],
        "xmin": -10.0, "xmax": 10.0, "ymin": -7.0, "ymax": 7.0,
        "xscl": 1.0, "yscl": 1.0,
        "tmin": 0.0, "tmax": 6.283, "tstep": 0.1,
        "thmin": 0.0, "thmax": 6.283, "thstep": 0.1,
        "tstart": -5.0, "tstep_t": 1.0, "tscroll": 0,
        "vars": {}, "ans": 0, "hist": [], "hscr": 0,
        "trace": False, "tx": 0.0, "tfi": 0,
        "_ye_sel": 0, "_win_sel": 0, "_tblset_sel": 0,
        "_mode_sel": 0,
        "dirty": True,
    }


# --- Module loading ---

def _load_mod(name):
    global _mod
    _unload_mod()
    if name == "home":
        import _home
        _mod = _home
    elif name == "graph":
        import _graph
        _mod = _graph
    elif name == "table":
        import _table
        _mod = _table
    collect()


def _unload_mod():
    global _mod
    _mod = None
    collect()


# --- Drawing: Status bar, Entry line, Toolbar, Dropdown ---

def _draw_statusbar(d):
    from picoware.core.display import FONT_8
    d.fill_rect(0, 0, 320, _SB_H, d.fg)
    # Angle mode
    d.text(2, 1, _S["angle"], d.bg, FONT_8)
    # Graph type
    d.text(30, 1, _S["gtype"], d.bg, FONT_8)
    # Number format
    nf = _S.get("nfmt", "AUTO")
    tw = len(nf) * 5
    d.text(320 - tw - 2, 1, nf, d.bg, FONT_8)


def _draw_entry(d):
    from picoware.core.display import FONT_12, GRAY

    d.fill_rect(0, _ENTRY_Y, 320, _ENTRY_H, d.bg)
    d.hline(0, _ENTRY_Y, 320, d.fg)

    entry = _S["entry"]
    cur = _S["cur"]
    escr = _S["escr"]

    # Visible chars: FONT_12 cw=7, max ~44 chars with prompt
    cw = 7
    prompt = "> " if not _editing else _edit_label
    pw = len(prompt) * cw
    max_vis = (316 - pw) // cw

    # Auto-scroll
    if cur - escr > max_vis - 2:
        _S["escr"] = cur - max_vis + 2
    if cur - escr < 2 and escr > 0:
        _S["escr"] = max(0, cur - 2)
    escr = _S["escr"]

    vis = entry[escr:escr + max_vis]
    text = "".join(vis)

    d.text(2, _ENTRY_Y + 3, prompt, GRAY, FONT_12)
    d.text(2 + pw, _ENTRY_Y + 3, text, d.fg, FONT_12)

    # Cursor
    cx = 2 + pw + (cur - escr) * cw
    if 0 <= cx < 318:
        d.fill_rect(cx, _ENTRY_Y + 2, 2, _ENTRY_H - 4, d.fg)


def _draw_toolbar(d):
    from picoware.core.display import FONT_8, GRAY, DARK_GRAY

    d.fill_rect(0, _TB_Y, 320, _TB_H, d.bg)
    d.hline(0, _TB_Y, 320, d.fg)

    tb = _get_toolbar()
    if not tb:
        return
    bw = 64
    for i in range(5):
        x = i * bw
        label = tb[i] if i < len(tb) else ""
        if not label:
            continue
        flabel = "F%d:%s" % (i + 1, label)
        # Truncate
        if len(flabel) > 9:
            flabel = flabel[:9]
        d.text(x + 2, _TB_Y + 5, flabel, d.fg, FONT_8)


def _draw_dropdown(d):
    from picoware.core.display import FONT_12, GRAY

    if not _S["dd"] or not _S["ddi"]:
        return

    items = _S["ddi"]
    sel = _S["dds"]
    fi = _S["ddf"]

    fh = 12
    cw = 7
    # Calculate popup width
    max_w = max(len(it) for it in items) * cw + 16
    if max_w < 80:
        max_w = 80
    if max_w > 200:
        max_w = 200
    h = len(items) * (fh + 4) + 4

    # Position: align to F-key
    bw = 64
    x = fi * bw
    if x + max_w > 320:
        x = 320 - max_w
    y = _TB_Y - h
    if y < _CONTENT_Y:
        y = _CONTENT_Y

    # Background
    d.fill_rect(x, y, max_w, h, d.bg)
    d.rect(x, y, max_w, h, d.fg)

    # Items
    iy = y + 2
    for i, item in enumerate(items):
        if i == sel:
            d.fill_rect(x + 1, iy, max_w - 2, fh + 3, d.fg)
            d.text(x + 6, iy + 1, item, d.bg, FONT_12)
        else:
            d.text(x + 6, iy + 1, item, d.fg, FONT_12)
        iy += fh + 4


def _get_toolbar():
    v = _S["view"]
    if v == _ST_HOME:
        return ("Tools", "Algebra", "Calc", "Funcs", "Clear")
    elif v == _ST_YEDIT:
        return ("Define", "Style", "", "", "Graph")
    elif v == _ST_WINDOW:
        return ("", "", "", "", "Graph")
    elif v == _ST_GRAPH:
        return ("Zoom", "Trace", "Math", "", "Y=")
    elif v == _ST_TABLE:
        return ("TblSet", "", "", "", "Graph")
    elif v == _ST_TBLSET:
        return ("", "", "", "", "Table")
    elif v == _ST_MODE:
        return ("", "", "", "", "OK")
    return None


# --- Full redraw ---

def _redraw():
    global _status_t
    d = _ctx.display
    d.clear()
    _draw_statusbar(d)

    v = _S["view"]
    if v == _ST_HOME:
        _ensure_mod("home")
        _mod.draw(d, _S)
    elif v == _ST_YEDIT:
        _ensure_mod("graph")
        _mod.draw_yedit(d, _S)
    elif v == _ST_WINDOW:
        _ensure_mod("graph")
        _mod.draw_window(d, _S)
    elif v == _ST_GRAPH:
        _ensure_mod("graph")
        collect()
        _mod.draw_graph(d, _S)
    elif v == _ST_TABLE:
        _ensure_mod("table")
        _mod.draw(d, _S)
    elif v == _ST_TBLSET:
        _ensure_mod("table")
        _mod.draw_setup(d, _S)
    elif v == _ST_MODE:
        _draw_mode(d)

    _draw_entry(d)

    # Status message overlay
    if _status_msg and _status_t > 0:
        from picoware.core.display import FONT_8, GRAY
        d.text(4, _ENTRY_Y - 12, _status_msg, GRAY, FONT_8)
        _status_t -= 1

    _draw_toolbar(d)

    if _S["dd"]:
        _draw_dropdown(d)

    d.swap()
    _S["dirty"] = False


def _ensure_mod(name):
    global _mod
    if _mod is None:
        _load_mod(name)
    elif name == "home" and not hasattr(_mod, 'evaluate'):
        _load_mod(name)
    elif name == "graph" and not hasattr(_mod, 'draw_graph'):
        _load_mod(name)
    elif name == "table" and not hasattr(_mod, 'draw_setup'):
        _load_mod(name)


# --- Mode dialog ---

def _draw_mode(d):
    from picoware.core.display import FONT_12

    fh = 12
    y = _CONTENT_Y + 10
    sel = _S.get("_mode_sel", 0)

    modes = [
        ("Angle", "angle", ["RAD", "DEG"]),
        ("Graph", "gtype", ["FUNC", "PAR", "POL"]),
        ("Format", "nfmt", ["AUTO", "FIX3", "FIX6"]),
    ]

    for i, (label, key, opts) in enumerate(modes):
        cur = _S.get(key, opts[0])
        line = "%s: %s" % (label, cur)
        if i == sel:
            d.fill_rect(0, y, 320, fh + 4, d.fg)
            d.text(8, y + 2, line, d.bg, FONT_12)
        else:
            d.text(8, y + 2, line, d.fg, FONT_12)
        y += fh + 8


def _handle_mode_key(k):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC

    modes = [
        ("angle", ["RAD", "DEG"]),
        ("gtype", ["FUNC", "PAR", "POL"]),
        ("nfmt", ["AUTO", "FIX3", "FIX6"]),
    ]

    sel = _S.get("_mode_sel", 0)

    if k == KEY_UP and sel > 0:
        _S["_mode_sel"] = sel - 1
        _S["dirty"] = True
    elif k == KEY_DOWN and sel < len(modes) - 1:
        _S["_mode_sel"] = sel + 1
        _S["dirty"] = True
    elif k == KEY_LEFT or k == KEY_RIGHT:
        key, opts = modes[sel]
        cur = _S.get(key, opts[0])
        idx = opts.index(cur) if cur in opts else 0
        if k == KEY_RIGHT:
            idx = (idx + 1) % len(opts)
        else:
            idx = (idx - 1) % len(opts)
        _S[key] = opts[idx]
        _S["dirty"] = True
    elif k == KEY_ENTER or k == KEY_ESC:
        _switch_view(_S["prev"])


# --- Entry line handling ---

def _entry_key(k, ch):
    global _editing
    from picoware.core.input import KEY_BACKSPACE, KEY_DEL, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC

    entry = _S["entry"]
    cur = _S["cur"]

    if k == KEY_BACKSPACE:
        if cur > 0:
            _S["cur"] = cur - 1
            entry.pop(cur - 1)
            _S["dirty"] = True
    elif k == KEY_DEL:
        if cur < len(entry):
            entry.pop(cur)
            _S["dirty"] = True
    elif k == KEY_LEFT:
        if cur > 0:
            _S["cur"] = cur - 1
            _S["dirty"] = True
    elif k == KEY_RIGHT:
        if cur < len(entry):
            _S["cur"] = cur + 1
            _S["dirty"] = True
    elif k == KEY_ENTER:
        text = "".join(entry)
        _commit_entry(text)
        _S["entry"] = []
        _S["cur"] = 0
        _S["escr"] = 0
        _editing = False
        _S["dirty"] = True
    elif k == KEY_ESC:
        if entry:
            _S["entry"] = []
            _S["cur"] = 0
            _S["escr"] = 0
            _editing = False
            _S["dirty"] = True
            return True  # consumed
        return False  # let view handle ESC
    elif ch and ch not in ('\n', '\t'):
        entry.insert(cur, ch)
        _S["cur"] = cur + 1
        _S["dirty"] = True
    return True


def _commit_entry(text):
    global _status_msg, _status_t
    v = _S["view"]

    if v == _ST_HOME:
        _ensure_mod("home")
        result = _mod.evaluate(text, _S)
        if result:
            _status_msg = str(result)
            _status_t = 30
    elif v == _ST_YEDIT:
        _ensure_mod("graph")
        _mod.yedit_set_field(_S, text)
    elif v == _ST_WINDOW:
        _ensure_mod("graph")
        _mod.window_set_field(_S, text)
    elif v == _ST_TBLSET:
        _ensure_mod("table")
        _mod.setup_set_field(_S, text)
    _S["dirty"] = True


def _insert_text(text):
    """Insert text at cursor in entry line."""
    for ch in text:
        _S["entry"].insert(_S["cur"], ch)
        _S["cur"] += 1
    _S["dirty"] = True


# --- Dropdown menu ---

def _open_dropdown(fi):
    v = _S["view"]
    items = None

    if v == _ST_HOME:
        _ensure_mod("home")
        items = _mod.get_dropdown(fi)
    elif v == _ST_GRAPH:
        _ensure_mod("graph")
        items = _mod.get_graph_dropdown(fi)

    if items:
        _S["dd"] = True
        _S["ddi"] = items
        _S["dds"] = 0
        _S["ddf"] = fi
        _S["dirty"] = True
    else:
        # Direct action
        _handle_fkey_direct(fi)


def _close_dropdown():
    _S["dd"] = False
    _S["ddi"] = []
    _S["dds"] = 0
    _S["ddf"] = -1
    _S["dirty"] = True


def _dd_key(k):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC

    items = _S["ddi"]
    sel = _S["dds"]

    if k == KEY_UP and sel > 0:
        _S["dds"] = sel - 1
        _S["dirty"] = True
    elif k == KEY_DOWN and sel < len(items) - 1:
        _S["dds"] = sel + 1
        _S["dirty"] = True
    elif k == KEY_ENTER:
        item = items[_S["dds"]]
        _close_dropdown()
        _handle_dd_select(item)
    elif k == KEY_ESC:
        _close_dropdown()


def _handle_dd_select(item):
    global _status_msg, _status_t
    v = _S["view"]

    if v == _ST_HOME:
        _ensure_mod("home")
        result = _mod.handle_dropdown(item, _S)
        if result == "__MODE__":
            _switch_view(_ST_MODE)
        elif result:
            _insert_text(result)
    elif v == _ST_GRAPH:
        _ensure_mod("graph")
        result = _mod.handle_graph_dropdown(item, _S)
        if result:
            _status_msg = result
            _status_t = 30
            _S["dirty"] = True


def _handle_fkey_direct(fi):
    """Handle F-key presses that don't open dropdowns."""
    global _status_msg, _status_t
    v = _S["view"]

    if v == _ST_HOME and fi == 4:
        # F5: Clear history
        _S["hist"] = []
        _S["hscr"] = 0
        _S["dirty"] = True
    elif v == _ST_YEDIT and fi == 4:
        # F5: Graph
        _switch_view(_ST_GRAPH)
    elif v == _ST_GRAPH and fi == 1:
        # F2: Trace toggle
        _ensure_mod("graph")
        if _S.get("trace"):
            _S["trace"] = False
        else:
            _mod.start_trace(_S)
        _S["dirty"] = True
    elif v == _ST_GRAPH and fi == 4:
        # F5: Y=
        _switch_view(_ST_YEDIT)
    elif v == _ST_WINDOW and fi == 4:
        _switch_view(_ST_GRAPH)
    elif v == _ST_TABLE and fi == 0:
        # F1: TblSet
        _S["_tblset_sel"] = 0
        _switch_view(_ST_TBLSET)
    elif v == _ST_TABLE and fi == 4:
        _switch_view(_ST_GRAPH)
    elif v == _ST_TBLSET and fi == 4:
        _switch_view(_ST_TABLE)
    elif v == _ST_MODE and fi == 4:
        _switch_view(_S["prev"])


# --- View switching ---

def _switch_view(new_view):
    global _editing, _edit_label
    _S["prev"] = _S["view"]
    _S["view"] = new_view
    _S["dd"] = False
    _S["entry"] = []
    _S["cur"] = 0
    _S["escr"] = 0
    _editing = False
    _edit_label = ""
    _S["dirty"] = True
    _close_dropdown()

    # Pre-load appropriate module
    if new_view in (_ST_YEDIT, _ST_WINDOW, _ST_GRAPH):
        _load_mod("graph")
    elif new_view in (_ST_TABLE, _ST_TBLSET):
        _load_mod("table")
    elif new_view == _ST_HOME:
        _load_mod("home")


# --- Persistence ---

_DATA_DIR = "/sd/picoware/data/graphcalc"


def _save_state():
    s = _ctx.storage
    try:
        if not s.exists("/sd/picoware/data"):
            s.mkdir("/sd/picoware/data")
        if not s.exists(_DATA_DIR):
            s.mkdir(_DATA_DIR)
    except Exception:
        return

    # Save state
    try:
        state = {
            "angle": _S["angle"], "gtype": _S["gtype"], "nfmt": _S["nfmt"],
            "ffunc": _S["ffunc"], "fpar": _S["fpar"], "fpol": _S["fpol"],
            "xmin": _S["xmin"], "xmax": _S["xmax"],
            "ymin": _S["ymin"], "ymax": _S["ymax"],
            "xscl": _S["xscl"], "yscl": _S["yscl"],
            "tmin": _S["tmin"], "tmax": _S["tmax"], "tstep": _S["tstep"],
            "thmin": _S["thmin"], "thmax": _S["thmax"], "thstep": _S["thstep"],
            "tstart": _S["tstart"], "tstep_t": _S["tstep_t"],
        }
        s.write_json(_DATA_DIR + "/state.json", state)
    except Exception:
        pass

    try:
        if _S["vars"]:
            s.write_json(_DATA_DIR + "/vars.json", _S["vars"])
    except Exception:
        pass

    try:
        if _S["hist"]:
            s.write_json(_DATA_DIR + "/history.json", _S["hist"])
    except Exception:
        pass


def _load_state():
    s = _ctx.storage
    try:
        state = s.read_json(_DATA_DIR + "/state.json")
        if state:
            for k in ("angle", "gtype", "nfmt", "xmin", "xmax", "ymin", "ymax",
                       "xscl", "yscl", "tmin", "tmax", "tstep",
                       "thmin", "thmax", "thstep", "tstart", "tstep_t"):
                if k in state:
                    _S[k] = state[k]
            for k in ("ffunc", "fpar", "fpol"):
                if k in state:
                    _S[k] = state[k]
    except Exception:
        pass

    try:
        v = s.read_json(_DATA_DIR + "/vars.json")
        if v:
            _S["vars"] = v
    except Exception:
        pass

    try:
        h = s.read_json(_DATA_DIR + "/history.json")
        if isinstance(h, list):
            _S["hist"] = h[-20:]
    except Exception:
        pass


# --- Plugin API ---

def start(ctx):
    global _S, _ctx, _mod, _status_msg, _status_t, _editing, _edit_label
    _ctx = ctx
    _S = _init_state()
    _mod = None
    _status_msg = None
    _status_t = 0
    _editing = False
    _edit_label = ""
    _load_state()
    collect()
    return True


def run(ctx):
    global _editing, _edit_label, _status_msg, _status_t

    from picoware.core.input import (
        KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER,
        KEY_BACKSPACE, KEY_ESC, KEY_DEL, KEY_SPACE,
        KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5,
        KEY_F6, KEY_F7, KEY_F8, KEY_F9, KEY_F10,
    )

    k = ctx.input.key
    ch = ctx.input.char

    if k == -1:
        if _S["dirty"]:
            _redraw()
        return

    v = _S["view"]

    # Dropdown menu active?
    if _S["dd"]:
        _dd_key(k)
        if _S["dirty"]:
            _redraw()
        return

    # F6-F10: Direct view switching (always available)
    if k == KEY_F6:
        _switch_view(_ST_HOME)
    elif k == KEY_F7:
        _switch_view(_ST_YEDIT)
    elif k == KEY_F8:
        _switch_view(_ST_WINDOW)
    elif k == KEY_F9:
        _switch_view(_ST_GRAPH)
    elif k == KEY_F10:
        _switch_view(_ST_TABLE)
    # F1-F5: Context toolbar
    elif k == KEY_F1:
        _open_dropdown(0)
    elif k == KEY_F2:
        _open_dropdown(1)
    elif k == KEY_F3:
        _open_dropdown(2)
    elif k == KEY_F4:
        _open_dropdown(3)
    elif k == KEY_F5:
        _handle_fkey_direct(4)
    # ESC handling
    elif k == KEY_ESC:
        if _S["entry"]:
            _S["entry"] = []
            _S["cur"] = 0
            _S["escr"] = 0
            _editing = False
            _edit_label = ""
            _S["dirty"] = True
        elif v == _ST_HOME:
            _save_state()
            ctx.back()
            return
        elif v == _ST_MODE:
            _switch_view(_S["prev"])
        elif v == _ST_TBLSET:
            _switch_view(_ST_TABLE)
        elif v == _ST_GRAPH and _S.get("trace"):
            _S["trace"] = False
            _S["dirty"] = True
        else:
            _switch_view(_ST_HOME)
    # Mode dialog
    elif v == _ST_MODE:
        _handle_mode_key(k)
    # View-specific key handling for ENTER on editors
    elif v == _ST_YEDIT and k == KEY_ENTER and not _editing:
        _ensure_mod("graph")
        action = _mod.handle_yedit_key(k, _S)
        if action == "__EDIT__":
            label, val = _mod.yedit_get_field(_S)
            _editing = True
            _edit_label = label
            _S["entry"] = list(val)
            _S["cur"] = len(val)
            _S["escr"] = 0
            _S["dirty"] = True
    elif v == _ST_WINDOW and k == KEY_ENTER and not _editing:
        _ensure_mod("graph")
        action = _mod.handle_window_key(k, _S)
        if action == "__EDIT__":
            key, val = _mod.window_get_field(_S)
            _editing = True
            _edit_label = key + "="
            _S["entry"] = list(str(val))
            _S["cur"] = len(str(val))
            _S["escr"] = 0
            _S["dirty"] = True
    elif v == _ST_TBLSET and k == KEY_ENTER and not _editing:
        _ensure_mod("table")
        key, val = _mod.setup_get_field(_S)
        _editing = True
        _edit_label = key + "="
        _S["entry"] = list(str(val))
        _S["cur"] = len(str(val))
        _S["escr"] = 0
        _S["dirty"] = True
    # Entry line gets printable chars, backspace, del, arrows, enter
    elif _editing or (v == _ST_HOME and (ch or k in (KEY_BACKSPACE, KEY_DEL, KEY_ENTER))):
        if v == _ST_HOME and not _editing and ch and ch not in ('\n', '\t'):
            _editing = True
            _edit_label = ""
        consumed = _entry_key(k, ch)
        if not consumed and k == KEY_ESC:
            pass  # already handled above
    # View-specific navigation keys
    elif v == _ST_HOME:
        _ensure_mod("home")
        _mod.handle_key(k, _S)
    elif v == _ST_YEDIT:
        _ensure_mod("graph")
        _mod.handle_yedit_key(k, _S)
    elif v == _ST_WINDOW:
        _ensure_mod("graph")
        _mod.handle_window_key(k, _S)
    elif v == _ST_GRAPH:
        _ensure_mod("graph")
        _mod.handle_graph_key(k, _S)
    elif v == _ST_TABLE:
        _ensure_mod("table")
        _mod.handle_key(k, _S)
    elif v == _ST_TBLSET:
        _ensure_mod("table")
        action = _mod.handle_setup_key(k, _S)
        if action == "__BACK__":
            _switch_view(_ST_TABLE)

    if _S["dirty"]:
        _redraw()


def stop(ctx):
    global _S, _mod, _ctx, _status_msg
    _save_state()
    _S = None
    _mod = None
    _ctx = None
    _status_msg = None
    collect()
