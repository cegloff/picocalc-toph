from picoware.core.input import (
    KEY_ENTER, KEY_BACKSPACE, KEY_ESC, KEY_LEFT, KEY_RIGHT,
)


def alert(display, inp, message, title="Alert"):
    display.clear()
    fh = display.font_height()

    # title bar
    display.fill_rect(0, 0, 320, fh + 10, display.fg)
    display.text(4, 5, title, display.bg)

    # message (word-wrap)
    cw = display.char_width()
    max_chars = (320 - 16) // cw
    y = fh + 20
    words = message.split(' ')
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        if len(test) > max_chars:
            display.text(8, y, line, display.fg)
            y += fh + 2
            line = word
        else:
            line = test
    if line:
        display.text(8, y, line, display.fg)

    # OK button
    btn_y = 320 - fh - 16
    btn_w = display.text_width("  OK  ")
    btn_x = (320 - btn_w) // 2
    display.fill_rect(btn_x, btn_y, btn_w, fh + 8, display.fg)
    display.text(btn_x + display.char_width(), btn_y + 4, "OK", display.bg)

    display.swap()

    # wait for enter/back
    while True:
        inp.poll()
        k = inp.key
        if k == KEY_ENTER or k == KEY_BACKSPACE or k == KEY_ESC:
            inp.reset()
            return


def confirm(display, inp, message, title="Confirm"):
    selected = 0  # 0=Yes, 1=No

    while True:
        display.clear()
        fh = display.font_height()

        # title bar
        display.fill_rect(0, 0, 320, fh + 10, display.fg)
        display.text(4, 5, title, display.bg)

        # message
        cw = display.char_width()
        max_chars = (320 - 16) // cw
        y = fh + 20
        words = message.split(' ')
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) > max_chars:
                display.text(8, y, line, display.fg)
                y += fh + 2
                line = word
            else:
                line = test
        if line:
            display.text(8, y, line, display.fg)

        # Yes / No buttons
        btn_y = 320 - fh - 16
        yes_x = 60
        no_x = 200
        btn_w = display.text_width("  Yes  ")

        if selected == 0:
            display.fill_rect(yes_x, btn_y, btn_w, fh + 8, display.fg)
            display.text(yes_x + display.char_width(), btn_y + 4, "Yes", display.bg)
            display.text(no_x + display.char_width(), btn_y + 4, "No", display.fg)
        else:
            display.text(yes_x + display.char_width(), btn_y + 4, "Yes", display.fg)
            display.fill_rect(no_x, btn_y, btn_w, fh + 8, display.fg)
            display.text(no_x + display.char_width(), btn_y + 4, "No", display.bg)

        display.swap()

        inp.poll()
        k = inp.key
        if k == KEY_LEFT:
            selected = 0
        elif k == KEY_RIGHT:
            selected = 1
        elif k == KEY_ENTER:
            inp.reset()
            return selected == 0
        elif k == KEY_BACKSPACE or k == KEY_ESC:
            inp.reset()
            return False


def text_input(display, inp, title="Input", initial=""):
    text = list(initial)
    cursor = len(text)
    fh = display.font_height()
    cw = display.char_width()

    while True:
        display.clear()

        # title bar
        display.fill_rect(0, 0, 320, fh + 10, display.fg)
        display.text(4, 5, title, display.bg)

        # text field
        field_y = fh + 20
        display.rect(4, field_y, 312, fh + 8, display.fg)

        shown = "".join(text)
        display.text(8, field_y + 4, shown, display.fg)

        # cursor
        cx = 8 + cursor * cw
        display.fill_rect(cx, field_y + 2, 2, fh + 4, display.fg)

        # hint
        display.text(8, 320 - fh - 4, "ENTER=save  ESC=cancel", display.fg)

        display.swap()

        inp.poll()
        k = inp.key
        if k == -1:
            continue

        if k == KEY_ENTER:
            inp.reset()
            return "".join(text)

        if k == KEY_ESC:
            inp.reset()
            return None

        if k == KEY_BACKSPACE:
            if cursor > 0:
                cursor -= 1
                text.pop(cursor)
        elif k == KEY_LEFT:
            if cursor > 0:
                cursor -= 1
        elif k == KEY_RIGHT:
            if cursor < len(text):
                cursor += 1
        else:
            ch = inp.char
            if ch and ch != '\n' and ch != '\t':
                text.insert(cursor, ch)
                cursor += 1
