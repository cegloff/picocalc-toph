"""Home screen: history display, expression evaluation, variable assignment."""

import math
from gc import collect

# Layout constants (must match main.py)
_SB_H = 10
_CONTENT_Y = 10
_CONTENT_H = 274
_ENTRY_Y = 284


def draw(d, S):
    """Draw home screen content area (history)."""
    from picoware.core.display import FONT_8, FONT_12, GRAY

    hist = S["hist"]
    if not hist:
        d.text(60, _CONTENT_Y + 120, "Press ENTER to evaluate", GRAY, FONT_12)
        return

    # Draw history bottom-up: most recent at bottom of content area
    fh12 = 12  # FONT_12 height
    fh8 = 8    # FONT_8 height
    pair_h = fh12 + fh8 + 4  # expression + result + gap
    max_vis = _CONTENT_H // pair_h
    hscr = S.get("hscr", 0)

    n = len(hist)
    start = max(0, n - max_vis - hscr)
    end = n - hscr
    if end < 0:
        end = 0
    if start < 0:
        start = 0

    # Draw from top
    y = _CONTENT_Y + 2
    for i in range(start, end):
        if y + pair_h > _ENTRY_Y:
            break
        h = hist[i]
        # Expression left-aligned
        expr_s = h["e"]
        # Truncate if too long
        cw = 7  # FONT_12 char width
        max_c = 310 // cw
        if len(expr_s) > max_c:
            expr_s = expr_s[:max_c - 2] + ".."
        d.text(4, y, expr_s, d.fg, FONT_12)
        y += fh12 + 1
        # Result right-aligned
        res_s = str(h["r"])
        if len(res_s) > max_c:
            res_s = res_s[:max_c - 2] + ".."
        rw = len(res_s) * cw
        d.text(316 - rw, y, res_s, d.fg, FONT_12)
        y += fh8 + 3


def handle_key(k, S):
    """Handle Home-specific keys. Returns True if handled."""
    from picoware.core.input import KEY_UP, KEY_DOWN

    if k == KEY_UP:
        if S["hscr"] < len(S["hist"]) - 1:
            S["hscr"] += 1
            S["dirty"] = True
            return True
    elif k == KEY_DOWN:
        if S["hscr"] > 0:
            S["hscr"] -= 1
            S["dirty"] = True
            return True
    return False


def evaluate(expr_str, S):
    """Evaluate expression string. Returns result string."""
    expr_str = expr_str.strip()
    if not expr_str:
        return None

    # Check for CAS commands: factor(, expand(, solve(, d(, integrate(, nSolve(, zeros(
    cas_cmds = ("factor", "expand", "solve", "zeros", "d", "integrate", "nSolve", "nsolve")
    for cmd in cas_cmds:
        if expr_str.startswith(cmd + "(") and expr_str.endswith(")"):
            args_str = expr_str[len(cmd) + 1:-1]
            try:
                import _cas
                result = _cas.cas_eval(cmd, args_str, S)
                collect()
                if result is not None:
                    _add_hist(S, expr_str, result)
                    return result
            except Exception as e:
                r = "error: " + str(e)
                _add_hist(S, expr_str, r)
                return r

    # Check for variable assignment: name := expr
    if ":=" in expr_str:
        parts = expr_str.split(":=", 1)
        vname = parts[0].strip()
        vexpr = parts[1].strip()
        try:
            val = _eval_numeric(vexpr, S)
            S["vars"][vname] = val
            S["ans"] = val
            r = _fmt(val)
            _add_hist(S, expr_str, r)
            return r
        except Exception as e:
            r = "error: " + str(e)
            _add_hist(S, expr_str, r)
            return r

    # Numeric evaluation
    try:
        val = _eval_numeric(expr_str, S)
        S["ans"] = val
        r = _fmt(val)
        _add_hist(S, expr_str, r)
        return r
    except Exception as e:
        r = "error"
        _add_hist(S, expr_str, r)
        return r


def _eval_numeric(expr_str, S):
    """Evaluate expression numerically with sandboxed env."""
    env = _build_env(S)
    code = compile(expr_str, "<e>", "eval")
    return eval(code, {"__builtins__": {}}, env)


def _build_env(S):
    angle = S.get("angle", "RAD")
    env = {
        "abs": abs, "min": min, "max": max, "pow": pow,
        "round": round, "int": int, "float": float,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
        "floor": math.floor, "ceil": math.ceil,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "degrees": math.degrees, "radians": math.radians,
        "ln": math.log,
        "ans": S.get("ans", 0),
    }
    # Angle-mode trig
    if angle == "DEG":
        env["sin"] = lambda x: math.sin(math.radians(x))
        env["cos"] = lambda x: math.cos(math.radians(x))
        env["tan"] = lambda x: math.tan(math.radians(x))
    else:
        env["sin"] = math.sin
        env["cos"] = math.cos
        env["tan"] = math.tan
    # User variables
    for k, v in S.get("vars", {}).items():
        env[k] = v
    return env


def _add_hist(S, expr, result):
    S["hist"].append({"e": expr, "r": result})
    if len(S["hist"]) > 20:
        S["hist"] = S["hist"][-20:]
    S["hscr"] = 0
    S["dirty"] = True


def _fmt(v):
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e12:
            return str(int(v))
        return "%.10g" % v
    return str(v)


def get_toolbar():
    """Return toolbar labels for Home view."""
    return ("Tools", "Algebra", "Calc", "Funcs", "Clear")


def get_dropdown(fi):
    """Return dropdown items for F-key index fi (0-4) on Home."""
    if fi == 0:
        return ["Clear Home", "Mode..."]
    if fi == 1:
        return ["factor(", "expand(", "solve(", "zeros("]
    if fi == 2:
        return ["d(", "integrate(", "nSolve("]
    if fi == 3:
        return ["sin(", "cos(", "tan(", "ln(", "log(", "sqrt(", "abs(", "floor(", "ceil("]
    if fi == 4:
        return None  # direct action: clear
    return None


def handle_dropdown(item, S):
    """Handle dropdown menu selection. Returns text to insert or action string."""
    if item == "Clear Home":
        S["hist"] = []
        S["hscr"] = 0
        S["dirty"] = True
        return None
    if item == "Mode...":
        return "__MODE__"
    # Otherwise it's text to insert into entry line
    return item
