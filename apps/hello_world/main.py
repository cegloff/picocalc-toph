PLUGIN_NAME = "Hello World"

_running = False


def start(ctx):
    global _running
    _running = True
    return True


def run(ctx):
    global _running
    if not _running:
        return

    d = ctx.display
    d.clear()

    d.fill_rect(0, 0, 320, d.font_height() + 10, d.fg)
    d.text(4, 5, "Hello World Plugin", d.bg)

    from gc import mem_free
    d.text(20, 60, "PicoCalcOS is running!", d.fg)
    d.text(20, 90, "Free memory: " + str(mem_free()), d.fg)

    if ctx.wifi and ctx.wifi.is_connected:
        d.text(20, 120, "WiFi: " + (ctx.wifi.ip or "connected"), d.fg)
    else:
        d.text(20, 120, "WiFi: not connected", d.fg)

    d.text(20, 150, "Battery: " + str(ctx.hw.battery_percent()) + "%", d.fg)

    d.text(20, 280, "Press ESC or HOME to exit", d.fg)
    d.swap()

    # check for back
    from picoware.core.input import KEY_ESC, KEY_BACKSPACE
    k = ctx.input.key
    if k == KEY_ESC or k == KEY_BACKSPACE:
        ctx.back()


def stop(ctx):
    global _running
    _running = False
