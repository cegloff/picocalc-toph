"""
Graphing Calculator Plugin for PicoCalcOS
TI-89-style interface: Y= editor, Graph, Table, Calculator
"""

PLUGIN_NAME = "Graph Calc"

from micropython import const
from gc import collect

# Views
_VIEW_YEDIT = const(0)
_VIEW_GRAPH = const(1)
_VIEW_TABLE = const(2)
_VIEW_CALC = const(3)

# Function slot count
_NUM_FUNCS = const(6)

# Graph area layout
_BAR_H = const(14)  # F-key bar height
_GRAPH_Y = const(14)
_GRAPH_H = const(290)  # 320 - 14 top - 16 bottom info
_INFO_Y = const(304)   # bottom info line

# State
_view = _VIEW_YEDIT
_funcs = None        # list of [expr, enabled]
_func_sel = 0
_xmin = -10.0
_xmax = 10.0
_ymin = -10.0
_ymax = 10.0
_table_start = -10.0
_table_step = 1.0
_table_scroll = 0
_trace_on = False
_trace_x = 0.0
_trace_func = 0
_calc_history = None
_need_draw = True
_COLORS = None


def _build_env():
    import math
    return {
        "abs": abs, "min": min, "max": max, "pow": pow,
        "round": round, "int": int, "float": float,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
        "floor": math.floor, "ceil": math.ceil,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "degrees": math.degrees, "radians": math.radians,
    }


def _safe_eval(expr, x_val=None):
    env = _build_env()
    if x_val is not None:
        env["x"] = x_val
    try:
        code = compile(expr, "<e>", "eval")
        return eval(code, env)
    except Exception:
        return None


# Coordinate mapping
def _x_to_px(x):
    return int((x - _xmin) / (_xmax - _xmin) * 319)


def _y_to_py(y):
    return _GRAPH_Y + int((_ymax - y) / (_ymax - _ymin) * (_GRAPH_H - 1))


def _px_to_x(px):
    return _xmin + px * (_xmax - _xmin) / 319


# --- Drawing ---

def _draw_fkeys(d, active):
    labels = ("F1:Y=", "F2:Grph", "F3:Tbl", "F4:Calc")
    bw = 80
    for i, lbl in enumerate(labels):
        x = i * bw
        if i == active:
            d.fill_rect(x, 0, bw, _BAR_H, d.fg)
            d.text(x + 2, 2, lbl, d.bg)
        else:
            d.text(x + 2, 2, lbl, d.fg)


def _draw_y_editor(ctx):
    d = ctx.display
    d.clear()
    _draw_fkeys(d, 0)

    fh = d.font_height()
    item_h = fh + 8
    y = _BAR_H + 4

    for i in range(_NUM_FUNCS):
        expr, enabled = _funcs[i]
        check = "[x]" if enabled else "[ ]"
        label = check + " y" + str(i + 1) + "=" + (expr if expr else "")
        color = _COLORS[i] if enabled else d.fg

        if i == _func_sel:
            d.fill_rect(0, y, 320, item_h, d.fg)
            d.text(8, y + 4, label, d.bg)
        else:
            d.text(8, y + 4, label, color)
        y += item_h

    d.text(4, 320 - fh - 2, "ENTER=edit SPC=toggle DEL=clear", d.fg)
    d.swap()


def _draw_graph(ctx):
    import math
    from picoware.core.display import BLUE

    d = ctx.display
    d.clear()
    _draw_fkeys(d, 1)

    # Axes
    if _ymin <= 0 <= _ymax:
        ay = _y_to_py(0)
        if _GRAPH_Y <= ay < _GRAPH_Y + _GRAPH_H:
            d.hline(0, ay, 320, BLUE)
    if _xmin <= 0 <= _xmax:
        ax = _x_to_px(0)
        if 0 <= ax < 320:
            d.line(ax, _GRAPH_Y, ax, _GRAPH_Y + _GRAPH_H - 1, BLUE)

    # Tick marks on axes
    import math
    x_range = _xmax - _xmin
    y_range = _ymax - _ymin
    # choose tick spacing: 1, 2, 5, 10, ...
    x_tick = 10 ** math.floor(math.log10(max(0.001, x_range / 5)))
    y_tick = 10 ** math.floor(math.log10(max(0.001, y_range / 5)))

    if _ymin <= 0 <= _ymax:
        ay = _y_to_py(0)
        tx = math.ceil(_xmin / x_tick) * x_tick
        while tx <= _xmax:
            px = _x_to_px(tx)
            if 0 <= px < 320 and _GRAPH_Y <= ay - 2 and ay + 2 < _GRAPH_Y + _GRAPH_H:
                d.line(px, ay - 2, px, ay + 2, BLUE)
            tx += x_tick

    if _xmin <= 0 <= _xmax:
        ax = _x_to_px(0)
        ty = math.ceil(_ymin / y_tick) * y_tick
        while ty <= _ymax:
            py = _y_to_py(ty)
            if _GRAPH_Y <= py < _GRAPH_Y + _GRAPH_H and 0 <= ax - 2 and ax + 2 < 320:
                d.line(ax - 2, py, ax + 2, py, BLUE)
            ty += y_tick

    # Plot functions
    env = _build_env()
    for fi in range(_NUM_FUNCS):
        expr, enabled = _funcs[fi]
        if not expr or not enabled:
            continue
        color = _COLORS[fi]
        try:
            code = compile(expr, "<e>", "eval")
        except Exception:
            continue

        prev_py = None
        for px in range(320):
            x = _px_to_x(px)
            env["x"] = x
            try:
                y = eval(code, env)
            except Exception:
                prev_py = None
                continue
            if not isinstance(y, (int, float)) or math.isnan(y) or math.isinf(y):
                prev_py = None
                continue
            py = _y_to_py(y)
            if _GRAPH_Y <= py < _GRAPH_Y + _GRAPH_H:
                if prev_py is not None and _GRAPH_Y <= prev_py < _GRAPH_Y + _GRAPH_H:
                    if abs(py - prev_py) < _GRAPH_H // 2:
                        d.line(px - 1, prev_py, px, py, color)
                    else:
                        d.pixel(px, py, color)
                else:
                    d.pixel(px, py, color)
                prev_py = py
            else:
                prev_py = None

    # Trace cursor
    if _trace_on:
        expr, enabled = _funcs[_trace_func]
        if expr and enabled:
            y_val = _safe_eval(expr, x_val=_trace_x)
            if y_val is not None:
                tx = _x_to_px(_trace_x)
                ty = _y_to_py(y_val)
                if _GRAPH_Y <= ty < _GRAPH_Y + _GRAPH_H and 0 <= tx < 320:
                    d.circle(tx, ty, 3, _COLORS[_trace_func])
                coord = "y%d x=%.4g y=%.4g" % (_trace_func + 1, _trace_x, y_val)
                d.text(4, _INFO_Y, coord, d.fg)
            else:
                d.text(4, _INFO_Y, "undefined", d.fg)
    else:
        info = "x:[%.2g,%.2g] y:[%.2g,%.2g]" % (_xmin, _xmax, _ymin, _ymax)
        d.text(4, _INFO_Y, info, d.fg)

    d.swap()


def _draw_table(ctx):
    d = ctx.display
    d.clear()
    _draw_fkeys(d, 2)

    fh = d.font_height()
    cw = d.char_width()

    active = []
    for i in range(_NUM_FUNCS):
        if _funcs[i][0] and _funcs[i][1]:
            active.append(i)

    if not active:
        d.text(60, 150, "No active functions", d.fg)
        d.text(4, 320 - fh - 2, "Press F1 to edit functions", d.fg)
        d.swap()
        return

    # Column layout
    n_cols = 1 + len(active)
    col_w = 320 // n_cols

    # Header
    header_y = _BAR_H + 2
    d.fill_rect(0, header_y, 320, fh + 4, d.fg)
    d.text(4, header_y + 2, "x", d.bg)
    for ci, fi in enumerate(active):
        d.text((ci + 1) * col_w + 4, header_y + 2, "y" + str(fi + 1), d.bg)

    # Data rows
    row_y = header_y + fh + 6
    row_h = fh + 4
    rows_visible = (320 - row_y - fh - 6) // row_h

    for r in range(rows_visible):
        x = _table_start + (_table_scroll + r) * _table_step
        yp = row_y + r * row_h

        x_str = "%.4g" % x
        d.text(4, yp, x_str, d.fg)

        for ci, fi in enumerate(active):
            y_val = _safe_eval(_funcs[fi][0], x_val=x)
            if y_val is not None:
                y_str = "%.4g" % y_val
            else:
                y_str = "err"
            d.text((ci + 1) * col_w + 4, yp, y_str, _COLORS[fi])

    info = "UP/DN=scroll ENTER=set range  start=%.4g step=%.4g" % (_table_start, _table_step)
    # truncate if too long
    max_c = 320 // cw
    if len(info) > max_c:
        info = info[:max_c]
    d.text(4, 320 - fh - 2, info, d.fg)
    d.swap()


def _draw_calc(ctx):
    d = ctx.display
    d.clear()
    _draw_fkeys(d, 3)

    fh = d.font_height()
    y = _BAR_H + 4

    if _calc_history:
        # show last entries that fit
        max_entries = (320 - _BAR_H - fh - 10) // (fh * 2 + 6)
        start = max(0, len(_calc_history) - max_entries)
        for expr, result in _calc_history[start:]:
            d.text(8, y, "> " + expr, d.fg)
            y += fh + 2
            d.text(16, y, str(result), d.fg)
            y += fh + 6
    else:
        d.text(60, 150, "Press ENTER to evaluate", d.fg)

    d.text(4, 320 - fh - 2, "ENTER=evaluate", d.fg)
    d.swap()


# --- Plugin API ---

def start(ctx):
    global _view, _funcs, _func_sel, _xmin, _xmax, _ymin, _ymax
    global _table_start, _table_step, _table_scroll
    global _trace_on, _trace_x, _trace_func, _calc_history
    global _need_draw, _COLORS

    from picoware.core.display import GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE
    _COLORS = (GREEN, RED, BLUE, CYAN, MAGENTA, ORANGE)

    _view = _VIEW_YEDIT
    _funcs = [
        ["sin(x)", True],
        ["", False],
        ["", False],
        ["", False],
        ["", False],
        ["", False],
    ]
    _func_sel = 0
    _xmin, _xmax = -10.0, 10.0
    _ymin, _ymax = -10.0, 10.0
    _table_start = -10.0
    _table_step = 1.0
    _table_scroll = 0
    _trace_on = False
    _trace_x = 0.0
    _trace_func = 0
    _calc_history = []
    _need_draw = True
    return True


def run(ctx):
    global _view, _func_sel, _xmin, _xmax, _ymin, _ymax
    global _table_scroll, _table_start, _table_step
    global _trace_on, _trace_x, _trace_func
    global _need_draw

    from picoware.core.input import (
        KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER,
        KEY_BACKSPACE, KEY_ESC, KEY_SPACE, KEY_DEL,
        KEY_F1, KEY_F2, KEY_F3, KEY_F4,
    )

    d = ctx.display
    k = ctx.input.key

    # F-key view switching
    if k == KEY_F1:
        _view = _VIEW_YEDIT
        _trace_on = False
        _need_draw = True
    elif k == KEY_F2:
        _view = _VIEW_GRAPH
        _need_draw = True
    elif k == KEY_F3:
        _view = _VIEW_TABLE
        _table_scroll = 0
        _need_draw = True
    elif k == KEY_F4:
        _view = _VIEW_CALC
        _need_draw = True
    elif k == KEY_ESC or k == KEY_BACKSPACE:
        if _trace_on:
            _trace_on = False
            _need_draw = True
        elif _view != _VIEW_YEDIT:
            _view = _VIEW_YEDIT
            _need_draw = True
        else:
            ctx.back()
            return

    # View-specific handling
    if _view == _VIEW_YEDIT:
        if k == KEY_UP and _func_sel > 0:
            _func_sel -= 1
            _need_draw = True
        elif k == KEY_DOWN and _func_sel < _NUM_FUNCS - 1:
            _func_sel += 1
            _need_draw = True
        elif k == KEY_ENTER:
            from picoware.ui.dialog import text_input
            expr = text_input(d, ctx.input, "y" + str(_func_sel + 1) + "=", _funcs[_func_sel][0])
            if expr is not None:
                _funcs[_func_sel][0] = expr
                _funcs[_func_sel][1] = bool(expr)
            _need_draw = True
        elif k == KEY_SPACE:
            if _funcs[_func_sel][0]:
                _funcs[_func_sel][1] = not _funcs[_func_sel][1]
                _need_draw = True
        elif k == KEY_DEL:
            _funcs[_func_sel][0] = ""
            _funcs[_func_sel][1] = False
            _need_draw = True

        if _need_draw:
            _draw_y_editor(ctx)
            _need_draw = False

    elif _view == _VIEW_GRAPH:
        dx = (_xmax - _xmin) * 0.1
        dy = (_ymax - _ymin) * 0.1

        if _trace_on:
            if k == KEY_LEFT:
                _trace_x -= dx * 0.2
                _need_draw = True
            elif k == KEY_RIGHT:
                _trace_x += dx * 0.2
                _need_draw = True
            elif k == KEY_UP:
                # cycle to next enabled function
                for i in range(1, _NUM_FUNCS):
                    nf = (_trace_func + i) % _NUM_FUNCS
                    if _funcs[nf][0] and _funcs[nf][1]:
                        _trace_func = nf
                        break
                _need_draw = True
            elif k == KEY_DOWN:
                # cycle to prev enabled function
                for i in range(1, _NUM_FUNCS):
                    nf = (_trace_func - i) % _NUM_FUNCS
                    if _funcs[nf][0] and _funcs[nf][1]:
                        _trace_func = nf
                        break
                _need_draw = True
            elif k == KEY_ENTER:
                _trace_on = False
                _need_draw = True
        else:
            if k == KEY_LEFT:
                _xmin -= dx
                _xmax -= dx
                _need_draw = True
            elif k == KEY_RIGHT:
                _xmin += dx
                _xmax += dx
                _need_draw = True
            elif k == KEY_UP:
                _ymin += dy
                _ymax += dy
                _need_draw = True
            elif k == KEY_DOWN:
                _ymin -= dy
                _ymax -= dy
                _need_draw = True
            elif k == KEY_ENTER:
                _trace_on = True
                _trace_x = (_xmin + _xmax) / 2
                for i in range(_NUM_FUNCS):
                    if _funcs[i][0] and _funcs[i][1]:
                        _trace_func = i
                        break
                _need_draw = True
            else:
                ch = ctx.input.char
                if ch == '+':
                    # zoom in
                    cx = (_xmin + _xmax) / 2
                    cy = (_ymin + _ymax) / 2
                    rx = (_xmax - _xmin) * 0.4
                    ry = (_ymax - _ymin) * 0.4
                    _xmin = cx - rx
                    _xmax = cx + rx
                    _ymin = cy - ry
                    _ymax = cy + ry
                    _need_draw = True
                elif ch == '-':
                    # zoom out
                    cx = (_xmin + _xmax) / 2
                    cy = (_ymin + _ymax) / 2
                    rx = (_xmax - _xmin) * 0.625
                    ry = (_ymax - _ymin) * 0.625
                    _xmin = cx - rx
                    _xmax = cx + rx
                    _ymin = cy - ry
                    _ymax = cy + ry
                    _need_draw = True
                elif ch == '0':
                    # reset zoom
                    _xmin, _xmax = -10.0, 10.0
                    _ymin, _ymax = -10.0, 10.0
                    _need_draw = True

        if _need_draw:
            _draw_graph(ctx)
            _need_draw = False

    elif _view == _VIEW_TABLE:
        if k == KEY_UP:
            _table_scroll -= 1
            if _table_scroll < 0:
                _table_scroll = 0
            _need_draw = True
        elif k == KEY_DOWN:
            _table_scroll += 1
            _need_draw = True
        elif k == KEY_ENTER:
            from picoware.ui.dialog import text_input
            s = text_input(d, ctx.input, "Table start", str(_table_start))
            if s is not None:
                try:
                    _table_start = float(s)
                except ValueError:
                    pass
                s2 = text_input(d, ctx.input, "Table step", str(_table_step))
                if s2 is not None:
                    try:
                        _table_step = float(s2)
                        if _table_step <= 0:
                            _table_step = 1.0
                    except ValueError:
                        pass
                _table_scroll = 0
            _need_draw = True

        if _need_draw:
            _draw_table(ctx)
            _need_draw = False

    elif _view == _VIEW_CALC:
        if k == KEY_ENTER:
            from picoware.ui.dialog import text_input
            expr = text_input(d, ctx.input, "Evaluate", "")
            if expr is not None and expr.strip():
                result = _safe_eval(expr)
                if result is not None:
                    _calc_history.append((expr, result))
                else:
                    _calc_history.append((expr, "Error"))
            _need_draw = True

        if _need_draw:
            _draw_calc(ctx)
            _need_draw = False


def stop(ctx):
    global _funcs, _calc_history, _COLORS
    _funcs = None
    _calc_history = None
    _COLORS = None
    collect()
