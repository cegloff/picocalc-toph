"""Snake game for PicoCalc."""

PLUGIN_NAME = "Snake"

from micropython import const
from utime import ticks_ms, ticks_diff

_CELL = const(10)
_COLS = const(30)  # 300 / 10
_ROWS = const(28)  # 280 / 10
_OFFSET_X = const(10)
_OFFSET_Y = const(20)
_SPEED_MS = const(150)

_DIR_UP = const(0)
_DIR_DOWN = const(1)
_DIR_LEFT = const(2)
_DIR_RIGHT = const(3)

_snake = None
_food = None
_direction = _DIR_RIGHT
_score = 0
_alive = True
_last_move = 0
_ctx = None
_dirty = True


def _rand(n):
    """Simple random int [0, n) using ticks."""
    return ticks_ms() % n


def _place_food():
    global _food
    while True:
        x = _rand(_COLS)
        y = _rand(_ROWS)
        if (x, y) not in _snake:
            _food = (x, y)
            return


def _reset():
    global _snake, _food, _direction, _score, _alive, _last_move, _dirty
    cx, cy = _COLS // 2, _ROWS // 2
    _snake = [(cx - 2, cy), (cx - 1, cy), (cx, cy)]
    _direction = _DIR_RIGHT
    _score = 0
    _alive = True
    _last_move = ticks_ms()
    _dirty = True
    _place_food()


def start(ctx):
    global _ctx
    _ctx = ctx
    _reset()
    return True


def run(ctx):
    global _direction, _alive, _last_move, _snake, _score, _dirty

    from picoware.core.input import (
        KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC,
    )

    k = ctx.input.key

    if not _alive:
        if k == KEY_ENTER:
            _reset()
        elif k == KEY_ESC:
            ctx.back()
        return

    if k == KEY_ESC:
        ctx.back()
        return

    # direction input (prevent 180-degree reversal)
    if k == KEY_UP and _direction != _DIR_DOWN:
        _direction = _DIR_UP
        _dirty = True
    elif k == KEY_DOWN and _direction != _DIR_UP:
        _direction = _DIR_DOWN
        _dirty = True
    elif k == KEY_LEFT and _direction != _DIR_RIGHT:
        _direction = _DIR_LEFT
        _dirty = True
    elif k == KEY_RIGHT and _direction != _DIR_LEFT:
        _direction = _DIR_RIGHT
        _dirty = True

    # move on timer
    now = ticks_ms()
    if ticks_diff(now, _last_move) < _SPEED_MS:
        if _dirty:
            _draw(ctx)
        return
    _last_move = now
    _dirty = True

    # compute new head
    hx, hy = _snake[-1]
    if _direction == _DIR_UP:
        hy -= 1
    elif _direction == _DIR_DOWN:
        hy += 1
    elif _direction == _DIR_LEFT:
        hx -= 1
    elif _direction == _DIR_RIGHT:
        hx += 1

    # wall collision
    if hx < 0 or hx >= _COLS or hy < 0 or hy >= _ROWS:
        _alive = False
        _draw(ctx)
        return

    # self collision
    if (hx, hy) in _snake:
        _alive = False
        _draw(ctx)
        return

    _snake.append((hx, hy))

    # food collision
    if (hx, hy) == _food:
        _score += 1
        _place_food()
    else:
        _snake.pop(0)

    _draw(ctx)


def _draw(ctx):
    global _dirty
    _dirty = False
    d = ctx.display
    d.clear()

    GREEN = d.GREEN if hasattr(d, 'GREEN') else 0x07E0
    RED = d.RED if hasattr(d, 'RED') else 0xF800

    # score bar
    fh = d.font_height()
    d.text(4, 2, "Snake  Score: {}".format(_score), d.fg)

    # border
    d.rect(_OFFSET_X - 1, _OFFSET_Y - 1, _COLS * _CELL + 2, _ROWS * _CELL + 2, d.fg)

    # food
    fx, fy = _food
    d.fill_rect(_OFFSET_X + fx * _CELL, _OFFSET_Y + fy * _CELL, _CELL, _CELL, RED)

    # snake
    for x, y in _snake:
        d.fill_rect(_OFFSET_X + x * _CELL, _OFFSET_Y + y * _CELL, _CELL, _CELL, GREEN)

    # game over overlay
    if not _alive:
        msg = "GAME OVER"
        msg2 = "Score: {}".format(_score)
        msg3 = "ENTER=retry ESC=quit"
        tw = d.text_width(msg)
        d.text((320 - tw) // 2, 130, msg, d.fg)
        tw2 = d.text_width(msg2)
        d.text((320 - tw2) // 2, 150, msg2, d.fg)
        tw3 = d.text_width(msg3)
        d.text((320 - tw3) // 2, 170, msg3, d.fg)

    d.swap()


def stop(ctx):
    global _snake, _food, _ctx
    _snake = None
    _food = None
    _ctx = None
