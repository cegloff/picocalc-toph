"""Lightweight CAS: tokenizer, parser, symbolic diff, simplify, factor, solve."""

import math

# --- Tokenizer ---

_NUM = 0
_ID = 1
_OP = 2
_LP = 3
_RP = 4
_COM = 5
_EQ = 6


def _tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in ' \t':
            i += 1
        elif c.isdigit() or (c == '.' and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and (s[j].isdigit() or s[j] == '.'):
                j += 1
            if j < n and s[j] in 'eE':
                j += 1
                if j < n and s[j] in '+-':
                    j += 1
                while j < n and s[j].isdigit():
                    j += 1
            toks.append((_NUM, s[i:j]))
            i = j
        elif c.isalpha() or c == '_':
            j = i
            while j < n and (s[j].isalnum() or s[j] == '_'):
                j += 1
            toks.append((_ID, s[i:j]))
            i = j
        elif c == '(':
            toks.append((_LP, '('))
            i += 1
        elif c == ')':
            toks.append((_RP, ')'))
            i += 1
        elif c == ',':
            toks.append((_COM, ','))
            i += 1
        elif c == '=':
            toks.append((_EQ, '='))
            i += 1
        elif c in '+-*/^':
            toks.append((_OP, c))
            i += 1
        else:
            i += 1
    return toks


# --- Parser: tokens -> S-expression tuples ---

class _Parser:
    __slots__ = ('t', 'p')

    def __init__(self, toks):
        self.t = toks
        self.p = 0

    def peek(self):
        return self.t[self.p] if self.p < len(self.t) else None

    def eat(self):
        tk = self.t[self.p]
        self.p += 1
        return tk

    def parse(self):
        e = self.expr()
        tk = self.peek()
        if tk and tk[0] == _EQ:
            self.eat()
            r = self.expr()
            return ("eq", e, r)
        return e

    def expr(self):
        return self.add()

    def add(self):
        left = self.mul()
        while True:
            tk = self.peek()
            if tk and tk[0] == _OP and tk[1] in '+-':
                op = self.eat()[1]
                right = self.mul()
                left = ("add", left, right) if op == '+' else ("add", left, ("neg", right))
            else:
                break
        return left

    def mul(self):
        left = self.pow_()
        while True:
            tk = self.peek()
            if tk and tk[0] == _OP and tk[1] in '*/':
                op = self.eat()[1]
                right = self.pow_()
                left = ("mul", left, right) if op == '*' else ("mul", left, ("pow", right, ("num", -1)))
            else:
                # implicit multiply: 2x, x(...)
                if tk and tk[0] in (_NUM, _ID, _LP):
                    if tk[0] == _LP:
                        # only implicit mul if prev was not an operator
                        pass  # let it fall through to pow_ which handles calls
                    else:
                        right = self.pow_()
                        left = ("mul", left, right)
                        continue
                break
        return left

    def pow_(self):
        base = self.unary()
        tk = self.peek()
        if tk and tk[0] == _OP and tk[1] == '^':
            self.eat()
            exp = self.unary()
            return ("pow", base, exp)
        return base

    def unary(self):
        tk = self.peek()
        if tk and tk[0] == _OP and tk[1] == '-':
            self.eat()
            e = self.unary()
            return ("neg", e)
        if tk and tk[0] == _OP and tk[1] == '+':
            self.eat()
            return self.unary()
        return self.atom()

    def atom(self):
        tk = self.peek()
        if not tk:
            return ("num", 0)
        if tk[0] == _NUM:
            self.eat()
            v = float(tk[1]) if '.' in tk[1] or 'e' in tk[1] or 'E' in tk[1] else int(tk[1])
            return ("num", v)
        if tk[0] == _ID:
            name = self.eat()[1]
            nk = self.peek()
            if nk and nk[0] == _LP:
                self.eat()  # (
                args = []
                if self.peek() and self.peek()[0] != _RP:
                    args.append(self.expr())
                    while self.peek() and self.peek()[0] == _COM:
                        self.eat()
                        args.append(self.expr())
                if self.peek() and self.peek()[0] == _RP:
                    self.eat()
                return ("call", name, tuple(args))
            # constants
            if name == 'pi':
                return ("num", math.pi)
            if name == 'e' and (not nk or nk[0] != _ID):
                return ("num", math.e)
            return ("var", name)
        if tk[0] == _LP:
            self.eat()
            e = self.expr()
            if self.peek() and self.peek()[0] == _RP:
                self.eat()
            return e
        self.eat()
        return ("num", 0)


def parse(s):
    return _Parser(_tokenize(s)).parse()


# --- Simplifier ---

def _is_num(e, v=None):
    if e[0] != "num":
        return False
    return v is None or e[1] == v


def simplify(e):
    if e[0] in ("num", "var"):
        return e
    if e[0] == "neg":
        a = simplify(e[1])
        if _is_num(a):
            return ("num", -a[1])
        if a[0] == "neg":
            return a[1]
        return ("neg", a)
    if e[0] == "add":
        a = simplify(e[1])
        b = simplify(e[2])
        if _is_num(a, 0):
            return b
        if _is_num(b, 0):
            return a
        if _is_num(a) and _is_num(b):
            return ("num", a[1] + b[1])
        if b[0] == "neg":
            if _is_num(a) and _is_num(b[1]):
                return ("num", a[1] - b[1][1]) if b[1][0] == "num" else ("add", a, b)
        return ("add", a, b)
    if e[0] == "mul":
        a = simplify(e[1])
        b = simplify(e[2])
        if _is_num(a, 0) or _is_num(b, 0):
            return ("num", 0)
        if _is_num(a, 1):
            return b
        if _is_num(b, 1):
            return a
        if _is_num(a, -1):
            return ("neg", b)
        if _is_num(b, -1):
            return ("neg", a)
        if _is_num(a) and _is_num(b):
            return ("num", a[1] * b[1])
        return ("mul", a, b)
    if e[0] == "pow":
        base = simplify(e[1])
        exp = simplify(e[2])
        if _is_num(exp, 0):
            return ("num", 1)
        if _is_num(exp, 1):
            return base
        if _is_num(base) and _is_num(exp):
            try:
                return ("num", base[1] ** exp[1])
            except Exception:
                pass
        return ("pow", base, exp)
    if e[0] == "call":
        args = tuple(simplify(a) for a in e[2])
        if len(args) == 1 and _is_num(args[0]):
            fn = e[1]
            v = args[0][1]
            try:
                fns = {"sin": math.sin, "cos": math.cos, "tan": math.tan,
                       "ln": math.log, "log": math.log, "exp": math.exp,
                       "sqrt": math.sqrt, "abs": abs,
                       "asin": math.asin, "acos": math.acos, "atan": math.atan,
                       "floor": math.floor, "ceil": math.ceil}
                if fn in fns:
                    return ("num", fns[fn](v))
            except Exception:
                pass
        return ("call", e[1], args)
    if e[0] == "eq":
        return ("eq", simplify(e[1]), simplify(e[2]))
    return e


# --- Symbolic Differentiation ---

def diff(e, var="x"):
    if e[0] == "num":
        return ("num", 0)
    if e[0] == "var":
        return ("num", 1) if e[1] == var else ("num", 0)
    if e[0] == "neg":
        return ("neg", diff(e[1], var))
    if e[0] == "add":
        return simplify(("add", diff(e[1], var), diff(e[2], var)))
    if e[0] == "mul":
        # product rule: u'v + uv'
        u, v = e[1], e[2]
        du, dv = diff(u, var), diff(v, var)
        return simplify(("add", ("mul", du, v), ("mul", u, dv)))
    if e[0] == "pow":
        base, exp = e[1], e[2]
        # check if exp contains var
        if not _has_var(exp, var):
            # power rule: n*x^(n-1)*dx
            return simplify(("mul", ("mul", exp, ("pow", base, ("add", exp, ("num", -1)))), diff(base, var)))
        if not _has_var(base, var):
            # a^g(x) = a^g(x) * ln(a) * g'(x)
            return simplify(("mul", ("mul", e, ("call", "ln", (base,))), diff(exp, var)))
        # general: e^(g*ln(f))
        return simplify(("mul", e, diff(("mul", exp, ("call", "ln", (base,))), var)))
    if e[0] == "call":
        fn = e[1]
        if len(e[2]) != 1:
            return ("num", 0)
        a = e[2][0]
        da = diff(a, var)
        # chain rule
        inner = None
        if fn == "sin":
            inner = ("call", "cos", (a,))
        elif fn == "cos":
            inner = ("neg", ("call", "sin", (a,)))
        elif fn == "tan":
            inner = ("pow", ("call", "cos", (a,)), ("num", -2))
        elif fn in ("ln", "log"):
            inner = ("pow", a, ("num", -1))
        elif fn == "exp":
            inner = ("call", "exp", (a,))
        elif fn == "sqrt":
            inner = ("mul", ("num", 0.5), ("pow", a, ("num", -0.5)))
        elif fn == "asin":
            inner = ("pow", ("add", ("num", 1), ("neg", ("pow", a, ("num", 2)))), ("num", -0.5))
        elif fn == "acos":
            inner = ("neg", ("pow", ("add", ("num", 1), ("neg", ("pow", a, ("num", 2)))), ("num", -0.5)))
        elif fn == "atan":
            inner = ("pow", ("add", ("num", 1), ("pow", a, ("num", 2))), ("num", -1))
        if inner:
            return simplify(("mul", inner, da))
        return ("num", 0)
    return ("num", 0)


def _has_var(e, var):
    if e[0] == "var":
        return e[1] == var
    if e[0] == "num":
        return False
    if e[0] == "neg":
        return _has_var(e[1], var)
    if e[0] in ("add", "mul", "pow", "eq"):
        return _has_var(e[1], var) or _has_var(e[2], var)
    if e[0] == "call":
        return any(_has_var(a, var) for a in e[2])
    return False


# --- Expression to string ---

def to_str(e):
    if e[0] == "num":
        v = e[1]
        if isinstance(v, float):
            if v == int(v) and abs(v) < 1e12:
                return str(int(v))
            return "%.6g" % v
        return str(v)
    if e[0] == "var":
        return e[1]
    if e[0] == "neg":
        s = to_str(e[1])
        if e[1][0] in ("add",):
            return "-(" + s + ")"
        return "-" + s
    if e[0] == "add":
        ls = to_str(e[1])
        r = e[2]
        if r[0] == "neg":
            return ls + "-" + to_str(r[1])
        return ls + "+" + to_str(r)
    if e[0] == "mul":
        ls = _mul_str(e[1])
        rs = _mul_str(e[2])
        return ls + "*" + rs
    if e[0] == "pow":
        bs = _pow_str(e[1])
        es = to_str(e[2])
        return bs + "^" + es
    if e[0] == "call":
        args = ",".join(to_str(a) for a in e[2])
        return e[1] + "(" + args + ")"
    if e[0] == "eq":
        return to_str(e[1]) + "=" + to_str(e[2])
    return "?"


def _mul_str(e):
    if e[0] in ("add",):
        return "(" + to_str(e) + ")"
    return to_str(e)


def _pow_str(e):
    if e[0] in ("add", "mul", "neg"):
        return "(" + to_str(e) + ")"
    return to_str(e)


# --- Evaluate expression tree numerically ---

def eval_expr(e, env):
    if e[0] == "num":
        return e[1]
    if e[0] == "var":
        if e[1] in env:
            return env[e[1]]
        raise ValueError("undefined: " + e[1])
    if e[0] == "neg":
        return -eval_expr(e[1], env)
    if e[0] == "add":
        return eval_expr(e[1], env) + eval_expr(e[2], env)
    if e[0] == "mul":
        return eval_expr(e[1], env) * eval_expr(e[2], env)
    if e[0] == "pow":
        b = eval_expr(e[1], env)
        ex = eval_expr(e[2], env)
        return b ** ex
    if e[0] == "call":
        fn = e[1]
        args = [eval_expr(a, env) for a in e[2]]
        fns = {"sin": math.sin, "cos": math.cos, "tan": math.tan,
               "ln": math.log, "log": math.log, "exp": math.exp,
               "sqrt": math.sqrt, "abs": abs,
               "asin": math.asin, "acos": math.acos, "atan": math.atan,
               "floor": math.floor, "ceil": math.ceil,
               "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh}
        if fn in fns:
            return fns[fn](*args)
        raise ValueError("unknown func: " + fn)
    return 0


# --- Polynomial tools ---

def _poly_coeffs(e, var="x"):
    """Extract polynomial coefficients [a0, a1, a2, ...] from expression."""
    e = simplify(e)
    coeffs = {}
    _collect_terms(e, var, 1, coeffs)
    if coeffs is None:
        return None
    if not coeffs:
        return [0]
    deg = max(coeffs.keys())
    if deg > 10:
        return None
    result = [0] * (deg + 1)
    for k, v in coeffs.items():
        result[k] = v
    return result


def _collect_terms(e, var, coeff, coeffs):
    if coeffs is None:
        return
    if _is_num(e):
        coeffs[0] = coeffs.get(0, 0) + coeff * e[1]
        return
    if e[0] == "var" and e[1] == var:
        coeffs[1] = coeffs.get(1, 0) + coeff
        return
    if e[0] == "var":
        return  # other variable, can't extract
    if e[0] == "neg":
        _collect_terms(e[1], var, -coeff, coeffs)
        return
    if e[0] == "add":
        _collect_terms(e[1], var, coeff, coeffs)
        _collect_terms(e[2], var, coeff, coeffs)
        return
    if e[0] == "mul":
        # try to separate constant * x^n
        if _is_num(e[1]) and not _has_var(e[1], var):
            _collect_terms(e[2], var, coeff * e[1][1], coeffs)
            return
        if _is_num(e[2]) and not _has_var(e[2], var):
            _collect_terms(e[1], var, coeff * e[2][1], coeffs)
            return
    if e[0] == "pow" and e[1][0] == "var" and e[1][1] == var and _is_num(e[2]):
        n = int(e[2][1])
        if e[2][1] == n and n >= 0:
            coeffs[n] = coeffs.get(n, 0) + coeff
            return
    # can't decompose further
    return


def _factor_poly(coeffs):
    """Factor polynomial from coefficients. Returns string or None."""
    deg = len(coeffs) - 1
    if deg < 2:
        return None
    if deg == 2:
        a, b, c = coeffs[2], coeffs[1], coeffs[0]
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        sd = math.sqrt(disc)
        r1 = (-b + sd) / (2 * a)
        r2 = (-b - sd) / (2 * a)
        # format as a*(x-r1)*(x-r2)
        parts = []
        if a != 1:
            parts.append("%.6g" % a if a != int(a) else str(int(a)))
        parts.append(_root_factor("x", r1))
        parts.append(_root_factor("x", r2))
        return "*".join(parts)
    return None


def _root_factor(var, r):
    if r == 0:
        return var
    ri = int(r)
    if r == ri:
        if ri > 0:
            return "(%s-%d)" % (var, ri)
        elif ri < 0:
            return "(%s+%d)" % (var, -ri)
        return var
    if r > 0:
        return "(%s-%.6g)" % (var, r)
    return "(%s+%.6g)" % (var, -r)


# --- Solve ---

def _solve_linear(coeffs, var="x"):
    a, b = coeffs[1], coeffs[0]
    if a == 0:
        return None
    r = -b / a
    return _fmt_val(r)


def _solve_quadratic(coeffs, var="x"):
    a, b, c = coeffs[2], coeffs[1], coeffs[0]
    disc = b * b - 4 * a * c
    if disc < 0:
        return "no real solution"
    if disc == 0:
        r = -b / (2 * a)
        return "%s=%.6g" % (var, r)
    sd = math.sqrt(disc)
    r1 = (-b + sd) / (2 * a)
    r2 = (-b - sd) / (2 * a)
    return "%s=%s or %s=%s" % (var, _fmt_val(r1), var, _fmt_val(r2))


def _fmt_val(v):
    if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
        return str(int(v))
    return "%.6g" % v


# --- Numeric solvers ---

def _newton(f, x0, tol=1e-10, maxiter=50):
    x = x0
    h = 1e-8
    for _ in range(maxiter):
        fx = f(x)
        if abs(fx) < tol:
            return x
        dfx = (f(x + h) - f(x - h)) / (2 * h)
        if abs(dfx) < 1e-15:
            break
        x -= fx / dfx
    if abs(f(x)) < 1e-6:
        return x
    return None


def _bisect(f, a, b, tol=1e-10, maxiter=100):
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        return None
    for _ in range(maxiter):
        m = (a + b) / 2
        fm = f(m)
        if abs(fm) < tol or (b - a) < tol:
            return m
        if fa * fm < 0:
            b = m
            fb = fm
        else:
            a = m
            fa = fm
    return (a + b) / 2


def _golden_min(f, a, b, tol=1e-8, maxiter=100):
    gr = (math.sqrt(5) + 1) / 2
    c = b - (b - a) / gr
    d = a + (b - a) / gr
    for _ in range(maxiter):
        if abs(b - a) < tol:
            break
        if f(c) < f(d):
            b = d
        else:
            a = c
        c = b - (b - a) / gr
        d = a + (b - a) / gr
    return (a + b) / 2


def _simpson(f, a, b, n=100):
    if n % 2:
        n += 1
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        x = a + i * h
        s += f(x) * (4 if i % 2 else 2)
    return s * h / 3


def find_zero(f, a, b):
    """Find a zero of f in [a,b] using bisection then Newton refinement."""
    r = _bisect(f, a, b)
    if r is not None:
        nr = _newton(f, r)
        if nr is not None:
            return nr
        return r
    # try Newton from midpoint
    return _newton(f, (a + b) / 2)


def find_min(f, a, b):
    return _golden_min(f, a, b)


def find_max(f, a, b):
    return _golden_min(lambda x: -f(x), a, b)


def integrate(f, a, b):
    return _simpson(f, a, b)


# --- Top-level CAS dispatcher ---

def cas_eval(cmd, args_str, S):
    """Dispatch CAS commands. Returns result string or None."""
    var = "x"

    if cmd == "factor":
        e = parse(args_str)
        coeffs = _poly_coeffs(e, var)
        if coeffs:
            r = _factor_poly(coeffs)
            if r:
                return r
        return "can't factor"

    if cmd == "expand":
        e = parse(args_str)
        e = simplify(e)
        return to_str(e)

    if cmd == "d":
        # d(expr, var)
        parts = _split_args(args_str)
        expr_s = parts[0] if parts else args_str
        if len(parts) > 1:
            var = parts[1].strip()
        e = parse(expr_s)
        de = diff(e, var)
        de = simplify(de)
        return to_str(de)

    if cmd == "solve":
        parts = _split_args(args_str)
        expr_s = parts[0] if parts else args_str
        if len(parts) > 1:
            var = parts[1].strip()
        e = parse(expr_s)
        # if equation, move RHS to LHS
        if e[0] == "eq":
            e = simplify(("add", e[1], ("neg", e[2])))
        coeffs = _poly_coeffs(e, var)
        if coeffs:
            deg = len(coeffs) - 1
            if deg == 1:
                return "%s=%s" % (var, _solve_linear(coeffs, var))
            if deg == 2:
                return _solve_quadratic(coeffs, var)
        # fallback: numeric
        return _nsolve_dispatch(e, var, S)

    if cmd == "zeros":
        parts = _split_args(args_str)
        expr_s = parts[0] if parts else args_str
        if len(parts) > 1:
            var = parts[1].strip()
        e = parse(expr_s)
        coeffs = _poly_coeffs(e, var)
        if coeffs:
            deg = len(coeffs) - 1
            if deg == 1:
                r = _solve_linear(coeffs, var)
                return "{%s}" % r if r else "no solution"
            if deg == 2:
                a, b, c = coeffs[2], coeffs[1], coeffs[0]
                disc = b * b - 4 * a * c
                if disc < 0:
                    return "no real zeros"
                sd = math.sqrt(disc)
                r1 = (-b + sd) / (2 * a)
                r2 = (-b - sd) / (2 * a)
                if disc == 0:
                    return "{%s}" % _fmt_val(r1)
                return "{%s, %s}" % (_fmt_val(r1), _fmt_val(r2))
        return "can't find zeros"

    if cmd == "nSolve" or cmd == "nsolve":
        return _nsolve_dispatch(parse(args_str), var, S)

    if cmd == "integrate":
        parts = _split_args(args_str)
        if len(parts) >= 4:
            # definite integral: integrate(expr, var, a, b)
            expr_s = parts[0]
            var = parts[1].strip()
            try:
                a = float(parts[2].strip())
                b = float(parts[3].strip())
            except ValueError:
                return "bad bounds"
            e = parse(expr_s)
            env = dict(S.get("vars", {}))

            def f(xv):
                env[var] = xv
                return eval_expr(e, env)

            try:
                r = _simpson(f, a, b)
                return _fmt_val(r)
            except Exception:
                return "error"
        # symbolic - just return notation
        return "integrate(" + args_str + ")"

    return None


def _nsolve_dispatch(e, var, S):
    env = dict(S.get("vars", {}))

    def f(xv):
        env[var] = xv
        try:
            return eval_expr(e, env)
        except Exception:
            return float('inf')

    # try Newton from several starting points
    for x0 in [0, 1, -1, 5, -5, 10, -10]:
        r = _newton(f, x0)
        if r is not None:
            return "%s=%s" % (var, _fmt_val(r))
    return "no solution found"


def _split_args(s):
    """Split on commas respecting parentheses."""
    parts = []
    depth = 0
    cur = []
    for c in s:
        if c == '(':
            depth += 1
            cur.append(c)
        elif c == ')':
            depth -= 1
            cur.append(c)
        elif c == ',' and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        parts.append("".join(cur))
    return parts
