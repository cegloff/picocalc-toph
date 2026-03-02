"""Y= editor, Window editor, Graph view: plotting, trace, zoom, math analysis."""

import math
from gc import collect

# Layout
_SB_H = 10
_CONTENT_Y = 10
_CONTENT_H = 274
_ENTRY_Y = 284

# Colors (loaded lazily)
_COLORS = None


def _get_colors():
    global _COLORS
    if _COLORS is None:
        from picoware.core.display import GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE
        _COLORS = (GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE)
    return _COLORS


# --- Coordinate mapping ---

def _x_to_px(x, S):
    xmin, xmax = S["xmin"], S["xmax"]
    return int((x - xmin) / (xmax - xmin) * 319)


def _y_to_py(y, S):
    ymin, ymax = S["ymin"], S["ymax"]
    return _CONTENT_Y + int((ymax - y) / (ymax - ymin) * (_CONTENT_H - 1))


def _px_to_x(px, S):
    xmin, xmax = S["xmin"], S["xmax"]
    return xmin + px * (xmax - xmin) / 319


# --- Y= Editor ---

def draw_yedit(d, S):
    from picoware.core.display import FONT_12, FONT_8, GRAY

    colors = _get_colors()
    gtype = S.get("gtype", "FUNC")
    fh = 12
    y = _CONTENT_Y + 2
    sel = S.get("_ye_sel", 0)

    if gtype == "FUNC":
        funcs = S["ffunc"]
        for i in range(len(funcs)):
            expr, enabled = funcs[i]
            check = "[x]" if enabled else "[ ]"
            label = "%s y%d=%s" % (check, i + 1, expr)
            _draw_slot(d, y, label, i == sel, colors[i] if enabled else GRAY, fh)
            y += fh + 6
    elif gtype == "PAR":
        funcs = S["fpar"]
        for i in range(len(funcs)):
            xt, yt, enabled = funcs[i]
            check = "[x]" if enabled else "[ ]"
            l1 = "%s xt%d=%s" % (check, i + 1, xt)
            l2 = "   yt%d=%s" % (i + 1, yt)
            si = i * 2
            _draw_slot(d, y, l1, sel == si, colors[i] if enabled else GRAY, fh)
            y += fh + 3
            _draw_slot(d, y, l2, sel == si + 1, colors[i] if enabled else GRAY, fh)
            y += fh + 6
    elif gtype == "POL":
        funcs = S["fpol"]
        for i in range(len(funcs)):
            expr, enabled = funcs[i]
            check = "[x]" if enabled else "[ ]"
            label = "%s r%d=%s" % (check, i + 1, expr)
            _draw_slot(d, y, label, i == sel, colors[i] if enabled else GRAY, fh)
            y += fh + 6


def _draw_slot(d, y, label, selected, color, fh):
    from picoware.core.display import FONT_12
    cw = 7
    max_c = 310 // cw
    if len(label) > max_c:
        label = label[:max_c - 1] + "~"
    if selected:
        d.fill_rect(0, y, 320, fh + 4, d.fg)
        d.text(4, y + 2, label, d.bg, FONT_12)
    else:
        d.text(4, y + 2, label, color, FONT_12)


def handle_yedit_key(k, S):
    """Handle Y= editor keys. Returns action string or None."""
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_SPACE, KEY_DEL, KEY_ENTER

    gtype = S.get("gtype", "FUNC")
    sel = S.get("_ye_sel", 0)

    if gtype == "FUNC":
        n = len(S["ffunc"])
    elif gtype == "PAR":
        n = len(S["fpar"]) * 2
    elif gtype == "POL":
        n = len(S["fpol"])
    else:
        n = 6

    if k == KEY_UP and sel > 0:
        S["_ye_sel"] = sel - 1
        S["dirty"] = True
        return None
    elif k == KEY_DOWN and sel < n - 1:
        S["_ye_sel"] = sel + 1
        S["dirty"] = True
        return None
    elif k == KEY_SPACE:
        _toggle_func(S)
        S["dirty"] = True
        return None
    elif k == KEY_DEL:
        _clear_func(S)
        S["dirty"] = True
        return None
    elif k == KEY_ENTER:
        return "__EDIT__"
    return None


def yedit_get_field(S):
    """Get current Y= field for entry line editing. Returns (label, current_value)."""
    gtype = S.get("gtype", "FUNC")
    sel = S.get("_ye_sel", 0)

    if gtype == "FUNC":
        i = sel
        return ("y%d=" % (i + 1), S["ffunc"][i][0])
    elif gtype == "PAR":
        fi = sel // 2
        sub = sel % 2
        if sub == 0:
            return ("xt%d=" % (fi + 1), S["fpar"][fi][0])
        else:
            return ("yt%d=" % (fi + 1), S["fpar"][fi][1])
    elif gtype == "POL":
        i = sel
        return ("r%d=" % (i + 1), S["fpol"][i][0])
    return ("?=", "")


def yedit_set_field(S, val):
    """Set current Y= field from entry line."""
    gtype = S.get("gtype", "FUNC")
    sel = S.get("_ye_sel", 0)

    if gtype == "FUNC":
        S["ffunc"][sel][0] = val
        S["ffunc"][sel][1] = bool(val)
    elif gtype == "PAR":
        fi = sel // 2
        sub = sel % 2
        if sub == 0:
            S["fpar"][fi][0] = val
        else:
            S["fpar"][fi][1] = val
        S["fpar"][fi][2] = bool(S["fpar"][fi][0]) and bool(S["fpar"][fi][1])
    elif gtype == "POL":
        S["fpol"][sel][0] = val
        S["fpol"][sel][1] = bool(val)
    S["dirty"] = True


def _toggle_func(S):
    gtype = S.get("gtype", "FUNC")
    sel = S.get("_ye_sel", 0)
    if gtype == "FUNC":
        if S["ffunc"][sel][0]:
            S["ffunc"][sel][1] = not S["ffunc"][sel][1]
    elif gtype == "PAR":
        fi = sel // 2
        if S["fpar"][fi][0] or S["fpar"][fi][1]:
            S["fpar"][fi][2] = not S["fpar"][fi][2]
    elif gtype == "POL":
        if S["fpol"][sel][0]:
            S["fpol"][sel][1] = not S["fpol"][sel][1]


def _clear_func(S):
    gtype = S.get("gtype", "FUNC")
    sel = S.get("_ye_sel", 0)
    if gtype == "FUNC":
        S["ffunc"][sel] = ["", False]
    elif gtype == "PAR":
        fi = sel // 2
        S["fpar"][fi] = ["", "", False]
    elif gtype == "POL":
        S["fpol"][sel] = ["", False]


# --- Window Editor ---

def draw_window(d, S):
    from picoware.core.display import FONT_12, GRAY

    fh = 12
    y = _CONTENT_Y + 2
    sel = S.get("_win_sel", 0)

    fields = _get_win_fields(S)

    for i, (label, key) in enumerate(fields):
        val = S.get(key, 0)
        line = "%s = %s" % (label, _fmt(val))
        if i == sel:
            d.fill_rect(0, y, 320, fh + 4, d.fg)
            d.text(4, y + 2, line, d.bg, FONT_12)
        else:
            d.text(4, y + 2, line, d.fg, FONT_12)
        y += fh + 6


def _get_win_fields(S):
    gtype = S.get("gtype", "FUNC")
    fields = [
        ("xmin", "xmin"), ("xmax", "xmax"), ("xscl", "xscl"),
        ("ymin", "ymin"), ("ymax", "ymax"), ("yscl", "yscl"),
    ]
    if gtype == "PAR":
        fields.extend([("tmin", "tmin"), ("tmax", "tmax"), ("tstep", "tstep")])
    elif gtype == "POL":
        fields.extend([("thmin", "thmin"), ("thmax", "thmax"), ("thstep", "thstep")])
    return fields


def handle_window_key(k, S):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER

    fields = _get_win_fields(S)
    sel = S.get("_win_sel", 0)

    if k == KEY_UP and sel > 0:
        S["_win_sel"] = sel - 1
        S["dirty"] = True
        return None
    elif k == KEY_DOWN and sel < len(fields) - 1:
        S["_win_sel"] = sel + 1
        S["dirty"] = True
        return None
    elif k == KEY_ENTER:
        return "__EDIT__"
    return None


def window_get_field(S):
    fields = _get_win_fields(S)
    sel = S.get("_win_sel", 0)
    label, key = fields[sel]
    return key, S.get(key, 0)


def window_set_field(S, val_str):
    fields = _get_win_fields(S)
    sel = S.get("_win_sel", 0)
    _, key = fields[sel]
    try:
        S[key] = float(val_str)
    except ValueError:
        pass
    S["dirty"] = True


# --- Graph View ---

def draw_graph(d, S):
    from picoware.core.display import FONT_8, FONT_12, GRAY, DARK_GRAY

    colors = _get_colors()
    xmin, xmax = S["xmin"], S["xmax"]
    ymin, ymax = S["ymin"], S["ymax"]
    gtype = S.get("gtype", "FUNC")

    # Draw grid/axes
    _draw_axes(d, S)

    # Build eval env
    env = _build_env(S)

    # Plot functions
    if gtype == "FUNC":
        _plot_func(d, S, env, colors)
    elif gtype == "PAR":
        _plot_par(d, S, env, colors)
    elif gtype == "POL":
        _plot_pol(d, S, env, colors)

    # Trace cursor
    if S.get("trace"):
        _draw_trace(d, S, env, colors)
    else:
        # Show coordinate range
        info = "x:[%.3g,%.3g]" % (xmin, xmax)
        d.text(4, _ENTRY_Y - 12, info, GRAY, FONT_8)

    collect()


def _draw_axes(d, S):
    from picoware.core.display import DARK_GRAY, GRAY

    xmin, xmax = S["xmin"], S["xmax"]
    ymin, ymax = S["ymin"], S["ymax"]

    # X axis
    if ymin <= 0 <= ymax:
        ay = _y_to_py(0, S)
        if _CONTENT_Y <= ay < _CONTENT_Y + _CONTENT_H:
            d.hline(0, ay, 320, GRAY)
    # Y axis
    if xmin <= 0 <= xmax:
        ax = _x_to_px(0, S)
        if 0 <= ax < 320:
            d.line(ax, _CONTENT_Y, ax, _CONTENT_Y + _CONTENT_H - 1, GRAY)

    # Tick marks
    xscl = S.get("xscl", 1.0)
    yscl = S.get("yscl", 1.0)

    if ymin <= 0 <= ymax and xscl > 0:
        ay = _y_to_py(0, S)
        tx = math.ceil(xmin / xscl) * xscl
        while tx <= xmax:
            px = _x_to_px(tx, S)
            if 0 <= px < 320:
                d.line(px, ay - 2, px, ay + 2, GRAY)
            tx += xscl

    if xmin <= 0 <= xmax and yscl > 0:
        ax = _x_to_px(0, S)
        ty = math.ceil(ymin / yscl) * yscl
        while ty <= ymax:
            py = _y_to_py(ty, S)
            if _CONTENT_Y <= py < _CONTENT_Y + _CONTENT_H:
                d.line(ax - 2, py, ax + 2, py, GRAY)
            ty += yscl


def _plot_func(d, S, env, colors):
    for fi in range(len(S["ffunc"])):
        expr, enabled = S["ffunc"][fi]
        if not expr or not enabled:
            continue
        try:
            code = compile(expr, "<e>", "eval")
        except Exception:
            continue
        color = colors[fi % len(colors)]
        prev_py = None
        for px in range(320):
            x = _px_to_x(px, S)
            env["x"] = x
            try:
                y = eval(code, {"__builtins__": {}}, env)
            except Exception:
                prev_py = None
                continue
            if not isinstance(y, (int, float)) or math.isnan(y) or math.isinf(y):
                prev_py = None
                continue
            py = _y_to_py(y, S)
            if _CONTENT_Y <= py < _CONTENT_Y + _CONTENT_H:
                if prev_py is not None and _CONTENT_Y <= prev_py < _CONTENT_Y + _CONTENT_H:
                    if abs(py - prev_py) < _CONTENT_H // 2:
                        d.line(px - 1, prev_py, px, py, color)
                    else:
                        d.pixel(px, py, color)
                else:
                    d.pixel(px, py, color)
                prev_py = py
            else:
                prev_py = None


def _plot_par(d, S, env, colors):
    tmin = S.get("tmin", 0.0)
    tmax = S.get("tmax", 6.283)
    tstep = S.get("tstep", 0.1)

    for fi in range(len(S["fpar"])):
        xt_expr, yt_expr, enabled = S["fpar"][fi]
        if not xt_expr or not yt_expr or not enabled:
            continue
        try:
            xt_code = compile(xt_expr, "<e>", "eval")
            yt_code = compile(yt_expr, "<e>", "eval")
        except Exception:
            continue
        color = colors[fi % len(colors)]
        prev_px = prev_py = None
        t = tmin
        while t <= tmax:
            env["t"] = t
            try:
                x = eval(xt_code, {"__builtins__": {}}, env)
                y = eval(yt_code, {"__builtins__": {}}, env)
            except Exception:
                prev_px = prev_py = None
                t += tstep
                continue
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                prev_px = prev_py = None
                t += tstep
                continue
            if math.isnan(x) or math.isinf(x) or math.isnan(y) or math.isinf(y):
                prev_px = prev_py = None
                t += tstep
                continue
            spx = _x_to_px(x, S)
            spy = _y_to_py(y, S)
            if 0 <= spx < 320 and _CONTENT_Y <= spy < _CONTENT_Y + _CONTENT_H:
                if prev_px is not None:
                    d.line(prev_px, prev_py, spx, spy, color)
                else:
                    d.pixel(spx, spy, color)
                prev_px, prev_py = spx, spy
            else:
                prev_px = prev_py = None
            t += tstep


def _plot_pol(d, S, env, colors):
    thmin = S.get("thmin", 0.0)
    thmax = S.get("thmax", 6.283)
    thstep = S.get("thstep", 0.1)

    for fi in range(len(S["fpol"])):
        expr, enabled = S["fpol"][fi]
        if not expr or not enabled:
            continue
        try:
            code = compile(expr, "<e>", "eval")
        except Exception:
            continue
        color = colors[fi % len(colors)]
        prev_px = prev_py = None
        th = thmin
        while th <= thmax:
            env["theta"] = th
            env["th"] = th
            try:
                r = eval(code, {"__builtins__": {}}, env)
            except Exception:
                prev_px = prev_py = None
                th += thstep
                continue
            if not isinstance(r, (int, float)) or math.isnan(r) or math.isinf(r):
                prev_px = prev_py = None
                th += thstep
                continue
            x = r * math.cos(th)
            y = r * math.sin(th)
            spx = _x_to_px(x, S)
            spy = _y_to_py(y, S)
            if 0 <= spx < 320 and _CONTENT_Y <= spy < _CONTENT_Y + _CONTENT_H:
                if prev_px is not None:
                    d.line(prev_px, prev_py, spx, spy, color)
                else:
                    d.pixel(spx, spy, color)
                prev_px, prev_py = spx, spy
            else:
                prev_px = prev_py = None
            th += thstep


def _draw_trace(d, S, env, colors):
    from picoware.core.display import FONT_8

    gtype = S.get("gtype", "FUNC")
    tx = S.get("tx", 0.0)
    tfi = S.get("tfi", 0)

    if gtype == "FUNC":
        funcs = S["ffunc"]
        if tfi >= len(funcs) or not funcs[tfi][0] or not funcs[tfi][1]:
            return
        env["x"] = tx
        try:
            code = compile(funcs[tfi][0], "<e>", "eval")
            yv = eval(code, {"__builtins__": {}}, env)
        except Exception:
            return
        if not isinstance(yv, (int, float)) or math.isnan(yv) or math.isinf(yv):
            return
        spx = _x_to_px(tx, S)
        spy = _y_to_py(yv, S)
        if 0 <= spx < 320 and _CONTENT_Y <= spy < _CONTENT_Y + _CONTENT_H:
            color = colors[tfi % len(colors)]
            d.circle(spx, spy, 3, color)
            d.circle(spx, spy, 4, color)
        coord = "y%d x=%.4g y=%.4g" % (tfi + 1, tx, yv)
        d.text(4, _ENTRY_Y - 12, coord, d.fg, FONT_8)
    # Parametric/polar trace would be similar but iterate t/theta


def handle_graph_key(k, S):
    """Handle graph view keys. Returns action string or None."""
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER

    gtype = S.get("gtype", "FUNC")
    dx = (S["xmax"] - S["xmin"]) * 0.05

    if S.get("trace"):
        if k == KEY_LEFT:
            S["tx"] -= dx
            S["dirty"] = True
            return None
        elif k == KEY_RIGHT:
            S["tx"] += dx
            S["dirty"] = True
            return None
        elif k == KEY_UP:
            _cycle_trace_func(S, 1)
            S["dirty"] = True
            return None
        elif k == KEY_DOWN:
            _cycle_trace_func(S, -1)
            S["dirty"] = True
            return None
        elif k == KEY_ENTER:
            S["trace"] = False
            S["dirty"] = True
            return None
    else:
        dx2 = (S["xmax"] - S["xmin"]) * 0.1
        dy2 = (S["ymax"] - S["ymin"]) * 0.1
        if k == KEY_LEFT:
            S["xmin"] -= dx2
            S["xmax"] -= dx2
            S["dirty"] = True
            return None
        elif k == KEY_RIGHT:
            S["xmin"] += dx2
            S["xmax"] += dx2
            S["dirty"] = True
            return None
        elif k == KEY_UP:
            S["ymin"] += dy2
            S["ymax"] += dy2
            S["dirty"] = True
            return None
        elif k == KEY_DOWN:
            S["ymin"] -= dy2
            S["ymax"] -= dy2
            S["dirty"] = True
            return None
    return None


def _cycle_trace_func(S, direction):
    gtype = S.get("gtype", "FUNC")
    tfi = S.get("tfi", 0)
    if gtype == "FUNC":
        funcs = S["ffunc"]
        n = len(funcs)
        for i in range(1, n):
            nf = (tfi + i * direction) % n
            if funcs[nf][0] and funcs[nf][1]:
                S["tfi"] = nf
                return


# --- Zoom operations ---

def zoom_in(S):
    cx = (S["xmin"] + S["xmax"]) / 2
    cy = (S["ymin"] + S["ymax"]) / 2
    rx = (S["xmax"] - S["xmin"]) * 0.25
    ry = (S["ymax"] - S["ymin"]) * 0.25
    S["xmin"] = cx - rx
    S["xmax"] = cx + rx
    S["ymin"] = cy - ry
    S["ymax"] = cy + ry
    S["dirty"] = True


def zoom_out(S):
    cx = (S["xmin"] + S["xmax"]) / 2
    cy = (S["ymin"] + S["ymax"]) / 2
    rx = (S["xmax"] - S["xmin"])
    ry = (S["ymax"] - S["ymin"])
    S["xmin"] = cx - rx
    S["xmax"] = cx + rx
    S["ymin"] = cy - ry
    S["ymax"] = cy + ry
    S["dirty"] = True


def zoom_std(S):
    S["xmin"] = -10.0
    S["xmax"] = 10.0
    S["ymin"] = -7.0
    S["ymax"] = 7.0
    S["xscl"] = 1.0
    S["yscl"] = 1.0
    S["dirty"] = True


def zoom_fit(S):
    """Adjust ymin/ymax to fit all active functions."""
    gtype = S.get("gtype", "FUNC")
    if gtype != "FUNC":
        return
    env = _build_env(S)
    ylo = float('inf')
    yhi = float('-inf')
    for fi in range(len(S["ffunc"])):
        expr, enabled = S["ffunc"][fi]
        if not expr or not enabled:
            continue
        try:
            code = compile(expr, "<e>", "eval")
        except Exception:
            continue
        for px in range(0, 320, 4):
            x = _px_to_x(px, S)
            env["x"] = x
            try:
                y = eval(code, {"__builtins__": {}}, env)
                if isinstance(y, (int, float)) and not math.isnan(y) and not math.isinf(y):
                    if y < ylo:
                        ylo = y
                    if y > yhi:
                        yhi = y
            except Exception:
                pass
    if ylo < yhi:
        margin = (yhi - ylo) * 0.1
        if margin < 0.1:
            margin = 0.1
        S["ymin"] = ylo - margin
        S["ymax"] = yhi + margin
        S["dirty"] = True


def zoom_sqr(S):
    """Make axes square (equal scaling)."""
    xr = S["xmax"] - S["xmin"]
    yr = S["ymax"] - S["ymin"]
    # Adjust to make pixel aspect ratio 1:1
    # content area is 320 wide x _CONTENT_H tall
    aspect = 320 / _CONTENT_H
    if xr / yr > aspect:
        # x range too wide, expand y
        new_yr = xr / aspect
        cy = (S["ymin"] + S["ymax"]) / 2
        S["ymin"] = cy - new_yr / 2
        S["ymax"] = cy + new_yr / 2
    else:
        new_xr = yr * aspect
        cx = (S["xmin"] + S["xmax"]) / 2
        S["xmin"] = cx - new_xr / 2
        S["xmax"] = cx + new_xr / 2
    S["dirty"] = True


# --- Graph Math Analysis ---

def math_zero(S):
    """Find zero near trace position."""
    return _math_find(S, "zero")


def math_minimum(S):
    return _math_find(S, "min")


def math_maximum(S):
    return _math_find(S, "max")


def math_dydx(S):
    """Evaluate dy/dx at trace position."""
    gtype = S.get("gtype", "FUNC")
    if gtype != "FUNC":
        return "FUNC mode only"
    tfi = S.get("tfi", 0)
    funcs = S["ffunc"]
    if tfi >= len(funcs) or not funcs[tfi][0] or not funcs[tfi][1]:
        return "no function"
    tx = S.get("tx", 0.0)
    env = _build_env(S)
    try:
        code = compile(funcs[tfi][0], "<e>", "eval")
    except Exception:
        return "error"
    h = 1e-8

    def f(xv):
        env["x"] = xv
        return eval(code, {"__builtins__": {}}, env)

    try:
        dy = (f(tx + h) - f(tx - h)) / (2 * h)
        return "dy/dx=%.6g at x=%.4g" % (dy, tx)
    except Exception:
        return "error"


def math_integral(S):
    """Compute definite integral between xmin and trace x."""
    gtype = S.get("gtype", "FUNC")
    if gtype != "FUNC":
        return "FUNC mode only"
    tfi = S.get("tfi", 0)
    funcs = S["ffunc"]
    if tfi >= len(funcs) or not funcs[tfi][0] or not funcs[tfi][1]:
        return "no function"
    env = _build_env(S)
    try:
        code = compile(funcs[tfi][0], "<e>", "eval")
    except Exception:
        return "error"

    def f(xv):
        env["x"] = xv
        return eval(code, {"__builtins__": {}}, env)

    a = S["xmin"]
    b = S.get("tx", 0.0)
    try:
        import _cas
        r = _cas.integrate(f, a, b)
        collect()
        return "integral=%.6g [%.3g,%.3g]" % (r, a, b)
    except Exception:
        return "error"


def _math_find(S, mode):
    gtype = S.get("gtype", "FUNC")
    if gtype != "FUNC":
        return "FUNC mode only"
    tfi = S.get("tfi", 0)
    funcs = S["ffunc"]
    if tfi >= len(funcs) or not funcs[tfi][0] or not funcs[tfi][1]:
        return "no function"
    env = _build_env(S)
    try:
        code = compile(funcs[tfi][0], "<e>", "eval")
    except Exception:
        return "error"

    def f(xv):
        env["x"] = xv
        return eval(code, {"__builtins__": {}}, env)

    # search around trace position
    tx = S.get("tx", 0.0)
    span = (S["xmax"] - S["xmin"]) * 0.3
    a = tx - span
    b = tx + span

    try:
        import _cas
        if mode == "zero":
            r = _cas.find_zero(f, a, b)
            collect()
            if r is not None:
                S["tx"] = r
                S["dirty"] = True
                yv = f(r)
                return "zero: x=%.6g y=%.6g" % (r, yv)
            return "no zero found"
        elif mode == "min":
            r = _cas.find_min(f, a, b)
            collect()
            S["tx"] = r
            S["dirty"] = True
            return "min: x=%.6g y=%.6g" % (r, f(r))
        elif mode == "max":
            r = _cas.find_max(f, a, b)
            collect()
            S["tx"] = r
            S["dirty"] = True
            return "max: x=%.6g y=%.6g" % (r, f(r))
    except Exception:
        return "error"
    return "error"


# --- Toolbar menus ---

def get_yedit_toolbar():
    return ("Define", "Style", "", "", "Graph")


def get_graph_toolbar():
    return ("Zoom", "Trace", "Math", "", "Y=")


def get_window_toolbar():
    return ("", "", "", "", "Graph")


def get_graph_dropdown(fi):
    if fi == 0:
        return ["ZoomIn", "ZoomOut", "ZoomStd", "ZoomFit", "ZoomSqr"]
    if fi == 1:
        return None  # Trace is direct toggle
    if fi == 2:
        return ["Zero", "Minimum", "Maximum", "dy/dx", "Integral"]
    return None


def get_yedit_dropdown(fi):
    return None


def handle_graph_dropdown(item, S):
    """Handle graph dropdown selection. Returns status message or None."""
    if item == "ZoomIn":
        zoom_in(S)
        return None
    elif item == "ZoomOut":
        zoom_out(S)
        return None
    elif item == "ZoomStd":
        zoom_std(S)
        return None
    elif item == "ZoomFit":
        zoom_fit(S)
        return None
    elif item == "ZoomSqr":
        zoom_sqr(S)
        return None
    elif item == "Zero":
        return math_zero(S)
    elif item == "Minimum":
        return math_minimum(S)
    elif item == "Maximum":
        return math_maximum(S)
    elif item == "dy/dx":
        return math_dydx(S)
    elif item == "Integral":
        return math_integral(S)
    return None


def start_trace(S):
    S["trace"] = True
    S["tx"] = (S["xmin"] + S["xmax"]) / 2
    gtype = S.get("gtype", "FUNC")
    if gtype == "FUNC":
        for i in range(len(S["ffunc"])):
            if S["ffunc"][i][0] and S["ffunc"][i][1]:
                S["tfi"] = i
                break
    S["dirty"] = True


# --- Helpers ---

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
