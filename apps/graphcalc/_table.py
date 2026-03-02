"""Table view + Table Setup."""

import math

# Layout
_SB_H = 10
_CONTENT_Y = 10
_CONTENT_H = 274
_ENTRY_Y = 284


def draw(d, S):
    """Draw table content area."""
    from picoware.core.display import FONT_8, FONT_12, GRAY
    from picoware.core.display import GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE

    colors = (GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE)
    gtype = S.get("gtype", "FUNC")

    # Get active functions
    active = []
    if gtype == "FUNC":
        for i, f in enumerate(S["ffunc"]):
            if f[0] and f[1]:
                active.append((i, "y%d" % (i + 1), f[0]))
    elif gtype == "PAR":
        for i, f in enumerate(S["fpar"]):
            if f[0] and f[1] and f[2]:
                active.append((i, "xt%d" % (i + 1), f[0]))
                active.append((i + 100, "yt%d" % (i + 1), f[1]))
    elif gtype == "POL":
        for i, f in enumerate(S["fpol"]):
            if f[0] and f[1]:
                active.append((i, "r%d" % (i + 1), f[0]))

    if not active:
        d.text(60, _CONTENT_Y + 120, "No active functions", GRAY, FONT_12)
        return

    n_cols = 1 + len(active)
    col_w = 320 // n_cols
    fh = 12

    # Header
    hy = _CONTENT_Y
    d.fill_rect(0, hy, 320, fh + 2, d.fg)
    var_name = "x" if gtype == "FUNC" else ("t" if gtype == "PAR" else "th")
    d.text(4, hy + 1, var_name, d.bg, FONT_12)
    for ci, (fi, label, _) in enumerate(active):
        d.text((ci + 1) * col_w + 2, hy + 1, label, d.bg, FONT_12)

    # Data rows
    row_y = hy + fh + 4
    row_h = fh + 3
    rows_vis = (_ENTRY_Y - row_y) // row_h

    tstart = S.get("tstart", -5.0)
    tstep = S.get("tstep_t", 1.0)
    tscroll = S.get("tscroll", 0)

    env = _build_env(S)

    for r in range(rows_vis):
        xv = tstart + (tscroll + r) * tstep
        yp = row_y + r * row_h

        x_str = _fmt(xv)
        d.text(4, yp, x_str, d.fg, FONT_12)

        for ci, (fi, label, expr) in enumerate(active):
            env_key = "x" if gtype == "FUNC" else ("t" if gtype == "PAR" else "theta")
            env[env_key] = xv
            if gtype == "POL":
                env["th"] = xv
            try:
                code = compile(expr, "<e>", "eval")
                val = eval(code, {"__builtins__": {}}, env)
                vs = _fmt(val)
            except Exception:
                vs = "err"
            color_i = fi if fi < 100 else fi - 100
            c = colors[color_i % len(colors)]
            d.text((ci + 1) * col_w + 2, yp, vs, c, FONT_12)


def draw_setup(d, S):
    """Draw table setup screen."""
    from picoware.core.display import FONT_12, GRAY

    fh = 12
    y = _CONTENT_Y + 10

    items = [
        ("tblStart", "tstart"),
        ("tblStep", "tstep_t"),
    ]

    sel = S.get("_tblset_sel", 0)

    for i, (label, key) in enumerate(items):
        val = S.get(key, 0)
        line = "%s = %s" % (label, _fmt(val))
        if i == sel:
            d.fill_rect(0, y, 320, fh + 4, d.fg)
            d.text(8, y + 2, line, d.bg, FONT_12)
        else:
            d.text(8, y + 2, line, d.fg, FONT_12)
        y += fh + 8

    d.text(8, _ENTRY_Y - 20, "ENTER to edit, ESC to return", GRAY, FONT_12)


def handle_key(k, S):
    """Handle Table view keys. Returns True if handled."""
    from picoware.core.input import KEY_UP, KEY_DOWN

    if k == KEY_UP:
        S["tscroll"] = max(0, S.get("tscroll", 0) - 1)
        S["dirty"] = True
        return True
    elif k == KEY_DOWN:
        S["tscroll"] = S.get("tscroll", 0) + 1
        S["dirty"] = True
        return True
    return False


def handle_setup_key(k, S):
    """Handle Table Setup keys. Returns: None=handled, '__BACK__'=exit setup."""
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ESC

    items = ["tstart", "tstep_t"]
    sel = S.get("_tblset_sel", 0)

    if k == KEY_UP and sel > 0:
        S["_tblset_sel"] = sel - 1
        S["dirty"] = True
        return None
    elif k == KEY_DOWN and sel < len(items) - 1:
        S["_tblset_sel"] = sel + 1
        S["dirty"] = True
        return None
    elif k == KEY_ESC:
        return "__BACK__"
    return None


def setup_get_field(S):
    """Get the currently selected field name and value for entry line editing."""
    items = ["tstart", "tstep_t"]
    sel = S.get("_tblset_sel", 0)
    key = items[sel]
    return key, S.get(key, 0)


def setup_set_field(S, val_str):
    """Set the currently selected field from entry line text."""
    items = ["tstart", "tstep_t"]
    sel = S.get("_tblset_sel", 0)
    key = items[sel]
    try:
        v = float(val_str)
        if key == "tstep_t" and v <= 0:
            v = 1.0
        S[key] = v
    except ValueError:
        pass
    S["dirty"] = True


def get_toolbar():
    return ("TblSet", "", "", "", "Graph")


def get_setup_toolbar():
    return ("", "", "", "", "Table")


def get_dropdown(fi):
    return None


def _build_env(S):
    env = {
        "abs": abs, "min": min, "max": max, "pow": pow,
        "round": round, "int": int, "float": float,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
        "floor": math.floor, "ceil": math.ceil,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "ln": math.log,
    }
    if S.get("angle") == "DEG":
        env["sin"] = lambda x: math.sin(math.radians(x))
        env["cos"] = lambda x: math.cos(math.radians(x))
        env["tan"] = lambda x: math.tan(math.radians(x))
    for k, v in S.get("vars", {}).items():
        env[k] = v
    return env


def _fmt(v):
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e12:
            return str(int(v))
        return "%.6g" % v
    return str(v)
