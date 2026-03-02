"""AI Chat client for OpenWebUI."""

PLUGIN_NAME = "AI Chat"

from micropython import const
from gc import collect
from picoware.core.input import (
    KEY_ENTER, KEY_ESC, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_BACKSPACE, KEY_F1, KEY_F2, KEY_F10
)
from picoware.core.display import WHITE, CYAN, DARK_GRAY, LIGHT_GRAY

_ST_SETUP = const(0)
_ST_CONVOS = const(1)
_ST_MODEL = const(2)
_ST_CHAT = const(3)
_ST_SETTINGS = const(4)
_ST_TOOLS = const(5)

_DATA_DIR = "picoware/data/chat"
_API_HOST = "bots.egloff.tech"
_MAX_CHARS = const(63)
_MSG_Y0 = const(10)
_MSG_LINES = const(33)
_INPUT_Y = const(276)
_HINT_Y = const(290)
_FONT = const(0)

_state = _ST_CONVOS
_cfg = None
_convos = []
_menu = None
_msgs = []
_model = ""
_slug = ""
_scroll = 0
_dirty = True
_input_buf = []
_input_cur = 0
_tools = []
_enabled_tools = []
_enabled_features = []
_tools_return = _ST_SETTINGS

_FEATURES = [
    {"id": "web_search", "name": "Web Search"},
    {"id": "image_generation", "name": "Image Generation"},
    {"id": "code_interpreter", "name": "Code Interpreter"},
]


# ── data ──────────────────────────────────────────────────────────

def _dirs(ctx):
    ctx.storage.mkdir("picoware/data")
    ctx.storage.mkdir(_DATA_DIR)


def _load_cfg(ctx):
    global _cfg, _enabled_tools, _enabled_features
    d = ctx.storage.read_json(_DATA_DIR + "/settings.json")
    _cfg = {"api_key": d.get("api_key", ""), "model": d.get("model", "")}
    _enabled_tools = d.get("tool_ids", [])
    _enabled_features = d.get("feature_ids", [])


def _save_cfg(ctx):
    _dirs(ctx)
    data = dict(_cfg)
    data["tool_ids"] = _enabled_tools
    data["feature_ids"] = _enabled_features
    ctx.storage.write_json(_DATA_DIR + "/settings.json", data)


def _load_convos(ctx):
    global _convos
    d = ctx.storage.read_json(_DATA_DIR + "/convos.json")
    _convos = d if isinstance(d, list) else []


def _save_convos(ctx):
    _dirs(ctx)
    ctx.storage.write_json(_DATA_DIR + "/convos.json", _convos)


def _load_chat(ctx, slug):
    global _msgs, _model, _slug
    d = ctx.storage.read_json(_DATA_DIR + "/" + slug + ".json")
    _msgs = d.get("messages", [])
    _model = d.get("model", _cfg.get("model", ""))
    _slug = slug


def _save_chat(ctx):
    if not _slug or not _msgs:
        return
    _dirs(ctx)
    ctx.storage.write_json(
        _DATA_DIR + "/" + _slug + ".json",
        {"model": _model, "messages": _msgs}
    )


def _update_index(ctx):
    if not _msgs:
        return
    title = "New chat"
    for m in _msgs:
        if m["role"] == "user":
            title = m["content"][:30]
            break
    for c in _convos:
        if c["slug"] == _slug:
            c["title"] = title
            c["model"] = _model
            _save_convos(ctx)
            return
    _convos.insert(0, {"slug": _slug, "title": title, "model": _model})
    _save_convos(ctx)


# ── ui helpers ────────────────────────────────────────────────────

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
    d.fill_rect(0, 0, 320, _MSG_Y0, DARK_GRAY)
    _tc = len(_enabled_tools) + len(_enabled_features)
    label = _model[:50]
    if _tc:
        label = _model[:44] + " T:" + str(_tc)
    d.text(2, 1, label, LIGHT_GRAY, _FONT)

    lines = []
    for msg in _msgs:
        pfx = "You: " if msg["role"] == "user" else "AI: "
        color = WHITE if msg["role"] == "user" else CYAN
        for ln in _wrap(pfx + msg["content"], _MAX_CHARS):
            lines.append((ln, color))
        lines.append(("", 0))

    total = len(lines)
    if total <= _MSG_LINES:
        start = 0
    else:
        start = max(0, total - _MSG_LINES - _scroll)

    y = _MSG_Y0
    end = min(start + _MSG_LINES, total)
    for i in range(start, end):
        t, c = lines[i]
        if t:
            d.text(2, y, t, c, _FONT)
        y += 8

    # input bar
    d.fill_rect(0, _INPUT_Y, 320, 12, DARK_GRAY)
    inp = "> " + "".join(_input_buf)
    d.text(2, _INPUT_Y + 2, inp[:_MAX_CHARS], WHITE, _FONT)
    # blinking cursor
    cx = 2 + (_input_cur + 2) * 5
    if cx < 318:
        d.fill_rect(cx, _INPUT_Y + 2, 1, 8, WHITE)

    # hint bar
    d.fill_rect(0, _HINT_Y, 320, 30, DARK_GRAY)
    d.text(2, _HINT_Y + 2, "ENTER:send ^/v:scroll F2:tools ESC:back", LIGHT_GRAY, _FONT)
    d.swap()


def _show_status(ctx, msg):
    d = ctx.display
    d.clear()
    d.text(10, 150, msg, WHITE, _FONT)
    d.swap()


# ── api ───────────────────────────────────────────────────────────

def _hdrs():
    return {
        "Authorization": "Bearer " + _cfg["api_key"],
        "Content-Type": "application/json",
    }


def _fetch_models(ctx):
    from picoware.net.http import http_get
    from json import loads
    body, _ = http_get(_API_HOST, "/api/models", headers=_hdrs())
    collect()
    data = loads(body)
    del body
    collect()
    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if mid:
            models.append(mid)
    del data
    collect()
    return models


def _fetch_tools(ctx):
    from picoware.net.http import http_get
    from json import loads
    body, _ = http_get(_API_HOST, "/api/v1/tools/", headers=_hdrs())
    collect()
    data = loads(body)
    del body
    collect()
    items = data if isinstance(data, list) else data.get("data", [])
    tools = []
    for t in items:
        tid = t.get("id", "")
        name = t.get("name", tid)
        if tid:
            tools.append({"id": tid, "name": name})
    del data
    collect()
    return tools


def _send_msg(ctx, text):
    global _dirty, _scroll
    _msgs.append({"role": "user", "content": text})
    _msgs.append({"role": "assistant", "content": ""})
    _scroll = 0
    _draw_chat(ctx)

    from json import dumps, loads
    from picoware.net.http import http_post, http_readline

    api_msgs = _msgs[:-1]
    if len(api_msgs) > 20:
        api_msgs = api_msgs[-20:]
    req = {"model": _model, "messages": api_msgs, "stream": True}
    if _enabled_tools:
        req["tool_ids"] = _enabled_tools
    if _enabled_features:
        req["features"] = {fid: True for fid in _enabled_features}
    body = dumps(req)
    del req
    del api_msgs
    collect()

    try:
        sock, status = http_post(
            _API_HOST, "/api/chat/completions",
            body=body, headers=_hdrs(), stream=True
        )
        del body
        collect()
    except Exception as e:
        _msgs[-1]["content"] = "[Error: " + str(e) + "]"
        _dirty = True
        return

    if status != 200:
        _msgs[-1]["content"] = "[HTTP " + str(status) + "]"
        try:
            sock.close()
        except:
            pass
        _dirty = True
        return

    try:
        while True:
            line = http_readline(sock)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line == b"data: [DONE]":
                break
            if line.startswith(b"data: "):
                try:
                    chunk = loads(line[6:])
                    delta = chunk["choices"][0]["delta"]
                    content = delta.get("content", "")
                    if content:
                        if _msgs[-1]["content"] == "[Using tools...]":
                            _msgs[-1]["content"] = ""
                        _msgs[-1]["content"] += content
                        _draw_chat(ctx)
                    elif delta.get("tool_calls"):
                        if not _msgs[-1]["content"]:
                            _msgs[-1]["content"] = "[Using tools...]"
                            _draw_chat(ctx)
                except:
                    pass
    except Exception as e:
        if not _msgs[-1]["content"]:
            _msgs[-1]["content"] = "[Stream error: " + str(e) + "]"
    finally:
        try:
            sock.close()
        except:
            pass

    collect()
    _save_chat(ctx)
    _update_index(ctx)
    _dirty = True


# ── lifecycle ─────────────────────────────────────────────────────

def start(ctx):
    global _state, _dirty, _menu
    _load_cfg(ctx)
    _load_convos(ctx)
    _state = _ST_SETUP if not _cfg["api_key"] else _ST_CONVOS
    _menu = None
    _dirty = True
    return True


def run(ctx):
    global _state, _menu, _dirty, _scroll, _model, _slug, _msgs, _input_buf, _input_cur
    global _tools, _enabled_tools, _enabled_features, _tools_return

    k = ctx.input.key

    # ── setup: prompt for API key ──
    if _state == _ST_SETUP:
        from picoware.ui.dialog import text_input
        key = text_input(ctx.display, ctx.input, title="API Key",
                         initial=_cfg.get("api_key", ""))
        if key:
            _cfg["api_key"] = key
            _save_cfg(ctx)
            _state = _ST_CONVOS
            _menu = None
            _dirty = True
        else:
            ctx.back()
        return

    # ── conversation list ──
    if _state == _ST_CONVOS:
        if _menu is None:
            items = ["+ New Chat"] + [c.get("title", "?") for c in _convos]
            from picoware.ui.menu import Menu
            _menu = Menu(ctx.display, items, title="AI Chat")
            _dirty = True
        if k != -1:
            if k == KEY_F10:
                _state = _ST_SETTINGS
                _menu = None
                _dirty = True
                return
            r = _menu.handle_input(k)
            if r == -1:
                ctx.back()
                return
            if r is not None:
                if r == 0:
                    _state = _ST_MODEL
                    _menu = None
                    _dirty = True
                else:
                    _load_chat(ctx, _convos[r - 1]["slug"])
                    _state = _ST_CHAT
                    _menu = None
                    _scroll = 0
                    _input_buf = []
                    _input_cur = 0
                    _dirty = True
                return
            _dirty = True
        if _dirty:
            _menu.draw(force=True)
            _dirty = False
        return

    # ── model selection ──
    if _state == _ST_MODEL:
        if _menu is None:
            if not ctx.wifi or not ctx.wifi.is_connected:
                from picoware.ui.dialog import alert
                alert(ctx.display, ctx.input, "WiFi not connected")
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            _show_status(ctx, "Loading models...")
            try:
                models = _fetch_models(ctx)
            except Exception as e:
                from picoware.ui.dialog import alert
                alert(ctx.display, ctx.input, str(e), title="Error")
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            if not models:
                from picoware.ui.dialog import alert
                alert(ctx.display, ctx.input, "No models available")
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            from picoware.ui.menu import Menu
            _menu = Menu(ctx.display, models, title="Select Model")
            _dirty = True
        if k != -1:
            r = _menu.handle_input(k)
            if r == -1:
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            if r is not None:
                _model = _menu.selected_item
                from utime import ticks_ms
                _slug = str(ticks_ms())
                _msgs = []
                _scroll = 0
                _input_buf = []
                _input_cur = 0
                _state = _ST_CHAT
                _menu = None
                _dirty = True
                return
            _dirty = True
        if _dirty:
            _menu.draw(force=True)
            _dirty = False
        return

    # ── chat view ──
    if _state == _ST_CHAT:
        if k == KEY_ENTER:
            text = "".join(_input_buf).strip()
            if text:
                _input_buf.clear()
                _input_cur = 0
                if not ctx.wifi or not ctx.wifi.is_connected:
                    from picoware.ui.dialog import alert
                    alert(ctx.display, ctx.input, "WiFi not connected")
                else:
                    _send_msg(ctx, text)
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
        if k == KEY_ESC:
            _save_chat(ctx)
            _update_index(ctx)
            _state = _ST_CONVOS
            _menu = None
            _dirty = True
            return
        if k == KEY_F1:
            _save_chat(ctx)
            _update_index(ctx)
            _state = _ST_MODEL
            _menu = None
            _dirty = True
            return
        if k == KEY_F2:
            _save_chat(ctx)
            _update_index(ctx)
            _tools_return = _ST_CHAT
            _state = _ST_TOOLS
            _menu = None
            _dirty = True
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

    # ── settings ──
    if _state == _ST_SETTINGS:
        if _menu is None:
            from picoware.ui.menu import Menu
            _menu = Menu(ctx.display,
                         ["Edit API Key", "Manage Tools", "Clear History", "Back"],
                         title="Settings")
            _dirty = True
        if k != -1:
            r = _menu.handle_input(k)
            if r == -1 or r == 3:
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            if r == 0:
                from picoware.ui.dialog import text_input
                key = text_input(ctx.display, ctx.input, title="API Key",
                                 initial=_cfg.get("api_key", ""))
                if key is not None:
                    _cfg["api_key"] = key
                    _save_cfg(ctx)
                _dirty = True
                return
            if r == 1:
                _tools_return = _ST_SETTINGS
                _state = _ST_TOOLS
                _menu = None
                _dirty = True
                return
            if r == 2:
                from picoware.ui.dialog import confirm
                if confirm(ctx.display, ctx.input, "Delete all conversations?"):
                    _convos.clear()
                    _save_convos(ctx)
                _state = _ST_CONVOS
                _menu = None
                _dirty = True
                return
            _dirty = True
        if _dirty:
            _menu.draw(force=True)
            _dirty = False
        return

    # ── tool selection ──
    if _state == _ST_TOOLS:
        if _menu is None:
            if not ctx.wifi or not ctx.wifi.is_connected:
                from picoware.ui.dialog import alert
                alert(ctx.display, ctx.input, "WiFi not connected")
                _state = _tools_return
                _menu = None
                _dirty = True
                return
            _show_status(ctx, "Loading tools...")
            try:
                _tools = _fetch_tools(ctx)
            except Exception as e:
                _tools = []
            labels = _tool_labels() + ["Done"]
            from picoware.ui.menu import Menu
            _menu = Menu(ctx.display, labels, title="Tools")
            _dirty = True
        if k != -1:
            nf = len(_FEATURES)
            nt = len(_tools)
            r = _menu.handle_input(k)
            if r == -1:
                _state = _tools_return
                _menu = None
                _dirty = True
                return
            if r is not None:
                if r == nf + nt:
                    _save_cfg(ctx)
                    _state = _tools_return
                    _menu = None
                    _dirty = True
                    return
                if r < nf:
                    fid = _FEATURES[r]["id"]
                    if fid in _enabled_features:
                        _enabled_features.remove(fid)
                    else:
                        _enabled_features.append(fid)
                else:
                    tid = _tools[r - nf]["id"]
                    if tid in _enabled_tools:
                        _enabled_tools.remove(tid)
                    else:
                        _enabled_tools.append(tid)
                sel = _menu._selected
                scr = _menu._scroll
                _menu.items = _tool_labels() + ["Done"]
                _menu._selected = sel
                _menu._scroll = scr
            _dirty = True
        if _dirty:
            _menu.draw(force=True)
            _dirty = False


def _tool_labels():
    labels = []
    for f in _FEATURES:
        prefix = "[x] " if f["id"] in _enabled_features else "[ ] "
        labels.append(prefix + f["name"][:(_MAX_CHARS - 5)])
    for t in _tools:
        prefix = "[x] " if t["id"] in _enabled_tools else "[ ] "
        labels.append(prefix + t["name"][:(_MAX_CHARS - 5)])
    return labels


def stop(ctx):
    global _state, _cfg, _convos, _menu, _msgs, _model, _slug, _scroll, _dirty
    global _input_buf, _input_cur, _tools, _enabled_tools, _enabled_features, _tools_return
    _state = _ST_CONVOS
    _cfg = None
    _convos = []
    _menu = None
    _msgs = []
    _model = ""
    _slug = ""
    _scroll = 0
    _dirty = True
    _input_buf = []
    _input_cur = 0
    _tools = []
    _enabled_tools = []
    _enabled_features = []
    _tools_return = _ST_SETTINGS
    collect()
