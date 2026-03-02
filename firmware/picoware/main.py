from gc import collect, mem_free


def _create_ctx():
    from picoware.core.display import Display, BLACK, WHITE
    from picoware.core.input import Input
    from picoware.core.storage import Storage
    from picoware.core.hw import Hardware

    storage = Storage()
    storage.mount_vfs("/sd")

    # ensure directories exist
    for d in ("picoware", "picoware/settings", "picoware/apps", "picoware/data"):
        if not storage.exists(d):
            storage.mkdir(d)

    from picoware.core.settings import Settings
    settings = Settings(storage)

    dark = settings.get("dark_mode", True)
    fg = WHITE if dark else BLACK
    bg = BLACK if dark else WHITE

    display = Display(fg=fg, bg=bg)
    print("Display init OK")
    display.text(10, 10, "Booting...", fg)
    display.swap()
    print("First swap OK")
    inp = Input()
    print("Input init OK")
    hw = Hardware()

    # apply brightness
    hw.set_lcd_backlight(settings.get("brightness", 128))
    hw.set_kb_backlight(settings.get("kb_brightness", 64))

    # WiFi
    wifi = None
    try:
        from picoware.net.wifi import WiFi
        wifi = WiFi()
        if settings.get("auto_connect_wifi", True):
            ssid = settings.get("wifi_ssid", "")
            pw = settings.get("wifi_password", "")
            if ssid:
                print("Connecting to WiFi:", ssid)
                wifi.connect(ssid, pw, timeout_ms=10000)
    except Exception as e:
        print("WiFi init error:", e)

    class Ctx:
        __slots__ = (
            'display', 'input', 'storage', 'settings',
            'hw', 'wifi', '_back_requested',
        )
    ctx = Ctx()
    ctx.display = display
    ctx.input = inp
    ctx.storage = storage
    ctx.settings = settings
    ctx.hw = hw
    ctx.wifi = wifi
    ctx._back_requested = False

    return ctx


def _gc(ctx):
    collect()


def _back(ctx):
    ctx._back_requested = True


def _list_apps(storage):
    apps = []
    base = "picoware/apps"
    try:
        entries = storage.listdir(base)
    except Exception as e:
        print("App scan error:", e)
        return apps

    for entry in entries:
        if entry.startswith(".") or entry.startswith("_"):
            continue

        # check for entry point via picoware_sd.exists
        folder = base + "/" + entry
        has_main = (storage.exists(folder + "/main.py") or
                    storage.exists(folder + "/main.mpy"))
        if not has_main:
            continue

        name = " ".join(w[0].upper() + w[1:] for w in entry.split("_") if w)
        try:
            meta = storage.read_json(folder + "/app.json")
            if meta and meta.get("name"):
                name = meta["name"]
        except Exception:
            pass

        apps.append({"slug": entry, "name": name})

    apps.sort(key=lambda a: a["name"])
    return apps


def _load_app(slug):
    import sys

    app_path = "/sd/picoware/apps/" + slug

    if "main" in sys.modules:
        del sys.modules["main"]

    if app_path in sys.path:
        sys.path.remove(app_path)
    sys.path.insert(0, app_path)

    try:
        mod = __import__("main")
        for attr in ("start", "run", "stop"):
            if not hasattr(mod, attr):
                print("App", slug, "missing", attr)
                sys.path.remove(app_path)
                return None
        if "main" in sys.modules:
            del sys.modules["main"]
        return mod
    except Exception as e:
        print("App load error:", slug, e)
        if app_path in sys.path:
            sys.path.remove(app_path)
        return None


def _unload_app(slug, mod):
    import sys

    app_path = "/sd/picoware/apps/" + slug

    while app_path in sys.path:
        sys.path.remove(app_path)

    if mod:
        del mod

    to_remove = []
    for name in sys.modules:
        if name == "main":
            to_remove.append(name)
            continue
        m = sys.modules[name]
        f = getattr(m, "__file__", None)
        if f and f.startswith(app_path):
            to_remove.append(name)
    for name in to_remove:
        del sys.modules[name]

    collect()


def _run_settings(ctx):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE, KEY_ESC
    from picoware.core.display import BLACK, WHITE

    items = [
        "Dark Mode",
        "LCD Brightness",
        "KB Brightness",
        "WiFi",
        "Back",
    ]
    selected = 0
    d = ctx.display
    fh = d.font_height()
    item_h = fh + 8

    while True:
        d.clear()

        # title
        d.fill_rect(0, 0, 320, fh + 10, d.fg)
        d.text(4, 5, "Settings", d.bg)

        y = fh + 14
        for i, label in enumerate(items):
            val = ""
            if label == "Dark Mode":
                val = "ON" if ctx.settings.get("dark_mode") else "OFF"
            elif label == "LCD Brightness":
                val = str(ctx.settings.get("brightness", 128))
            elif label == "KB Brightness":
                val = str(ctx.settings.get("kb_brightness", 64))
            elif label == "WiFi":
                if ctx.wifi and ctx.wifi.is_connected:
                    val = ctx.wifi.ip or "connected"
                else:
                    ssid = ctx.settings.get("wifi_ssid", "")
                    val = ssid if ssid else "not configured"

            full = label + (("  " + val) if val else "")

            if i == selected:
                d.fill_rect(0, y, 320, item_h, d.fg)
                d.text(8, y + 4, full, d.bg)
            else:
                d.text(8, y + 4, full, d.fg)
            y += item_h

        d.swap()

        ctx.input.poll()
        k = ctx.input.key
        if k == -1:
            continue

        if k == KEY_UP and selected > 0:
            selected -= 1
        elif k == KEY_DOWN and selected < len(items) - 1:
            selected += 1
        elif k == KEY_BACKSPACE or k == KEY_ESC:
            return
        elif k == KEY_ENTER:
            choice = items[selected]

            if choice == "Back":
                return

            elif choice == "Dark Mode":
                dark = not ctx.settings.get("dark_mode", True)
                ctx.settings.set("dark_mode", dark)
                d.fg = WHITE if dark else BLACK
                d.bg = BLACK if dark else WHITE

            elif choice == "LCD Brightness":
                _adjust_value(ctx, "brightness", 0, 255, 16, "LCD Brightness")

            elif choice == "KB Brightness":
                _adjust_value(ctx, "kb_brightness", 0, 255, 16, "KB Brightness")

            elif choice == "WiFi":
                _run_wifi_settings(ctx)


def _adjust_value(ctx, key, min_val, max_val, step, title):
    from picoware.core.input import KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_BACKSPACE, KEY_ESC

    val = ctx.settings.get(key, min_val)
    d = ctx.display
    fh = d.font_height()

    while True:
        d.clear()
        d.fill_rect(0, 0, 320, fh + 10, d.fg)
        d.text(4, 5, title, d.bg)

        # value bar
        bar_y = 140
        bar_w = 280
        bar_x = 20
        pct = (val - min_val) / max(1, max_val - min_val)
        filled = int(bar_w * pct)

        d.rect(bar_x, bar_y, bar_w, 20, d.fg)
        d.fill_rect(bar_x + 1, bar_y + 1, filled, 18, d.fg)

        val_str = str(val)
        tw = d.text_width(val_str)
        d.text((320 - tw) // 2, bar_y + 30, val_str, d.fg)

        d.text(8, 320 - fh - 4, "LEFT/RIGHT=adjust  ENTER=save", d.fg)

        d.swap()

        ctx.input.poll()
        k = ctx.input.key
        if k == -1:
            continue

        if k == KEY_LEFT:
            val = max(min_val, val - step)
            if key == "brightness":
                ctx.hw.set_lcd_backlight(val)
            elif key == "kb_brightness":
                ctx.hw.set_kb_backlight(val)
        elif k == KEY_RIGHT:
            val = min(max_val, val + step)
            if key == "brightness":
                ctx.hw.set_lcd_backlight(val)
            elif key == "kb_brightness":
                ctx.hw.set_kb_backlight(val)
        elif k == KEY_ENTER:
            ctx.settings.set(key, val)
            return
        elif k == KEY_BACKSPACE or k == KEY_ESC:
            # revert
            old = ctx.settings.get(key, min_val)
            if key == "brightness":
                ctx.hw.set_lcd_backlight(old)
            elif key == "kb_brightness":
                ctx.hw.set_kb_backlight(old)
            return


def _run_wifi_settings(ctx):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE, KEY_ESC
    from picoware.ui.dialog import text_input, alert

    items = ["Scan Networks", "Manual SSID", "Disconnect", "Back"]
    selected = 0
    d = ctx.display
    fh = d.font_height()
    item_h = fh + 8

    while True:
        d.clear()
        d.fill_rect(0, 0, 320, fh + 10, d.fg)

        status = "WiFi: "
        if ctx.wifi and ctx.wifi.is_connected:
            status += ctx.wifi.ip or "connected"
        else:
            status += "disconnected"
        d.text(4, 5, status, d.bg)

        y = fh + 14
        for i, label in enumerate(items):
            if i == selected:
                d.fill_rect(0, y, 320, item_h, d.fg)
                d.text(8, y + 4, label, d.bg)
            else:
                d.text(8, y + 4, label, d.fg)
            y += item_h

        d.swap()

        ctx.input.poll()
        k = ctx.input.key
        if k == -1:
            continue

        if k == KEY_UP and selected > 0:
            selected -= 1
        elif k == KEY_DOWN and selected < len(items) - 1:
            selected += 1
        elif k == KEY_BACKSPACE or k == KEY_ESC:
            return
        elif k == KEY_ENTER:
            choice = items[selected]

            if choice == "Back":
                return

            elif choice == "Disconnect":
                if ctx.wifi:
                    ctx.wifi.disconnect()

            elif choice == "Manual SSID":
                ssid = text_input(d, ctx.input, "Enter SSID", ctx.settings.get("wifi_ssid", ""))
                if ssid is not None:
                    pw = text_input(d, ctx.input, "Enter Password", ctx.settings.get("wifi_password", ""))
                    if pw is not None:
                        ctx.settings.set("wifi_ssid", ssid)
                        ctx.settings.set("wifi_password", pw)
                        if ctx.wifi:
                            d.clear()
                            d.text(80, 150, "Connecting...", d.fg)
                            d.swap()
                            if ctx.wifi.connect(ssid, pw):
                                alert(d, ctx.input, "Connected to " + ssid, "WiFi")
                            else:
                                alert(d, ctx.input, "Failed to connect", "WiFi")

            elif choice == "Scan Networks":
                _scan_and_connect(ctx)


def _scan_and_connect(ctx):
    from picoware.core.input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACKSPACE, KEY_ESC
    from picoware.ui.dialog import text_input, alert

    d = ctx.display
    d.clear()
    d.text(80, 150, "Scanning...", d.fg)
    d.swap()

    if not ctx.wifi:
        alert(d, ctx.input, "WiFi not available", "Error")
        return

    networks = ctx.wifi.scan()
    if not networks:
        alert(d, ctx.input, "No networks found", "WiFi Scan")
        return

    items = [n["ssid"] + " (" + str(n["rssi"]) + ")" for n in networks]
    selected = 0
    fh = d.font_height()
    item_h = fh + 8
    scroll = 0
    visible = (320 - fh - 14) // item_h

    while True:
        d.clear()
        d.fill_rect(0, 0, 320, fh + 10, d.fg)
        d.text(4, 5, "Select Network", d.bg)

        y = fh + 14
        end = min(scroll + visible, len(items))
        for i in range(scroll, end):
            if i == selected:
                d.fill_rect(0, y, 320, item_h, d.fg)
                d.text(8, y + 4, items[i], d.bg)
            else:
                d.text(8, y + 4, items[i], d.fg)
            y += item_h

        d.swap()

        ctx.input.poll()
        k = ctx.input.key
        if k == -1:
            continue

        if k == KEY_UP and selected > 0:
            selected -= 1
            if selected < scroll:
                scroll = selected
        elif k == KEY_DOWN and selected < len(items) - 1:
            selected += 1
            if selected >= scroll + visible:
                scroll = selected - visible + 1
        elif k == KEY_BACKSPACE or k == KEY_ESC:
            return
        elif k == KEY_ENTER:
            ssid = networks[selected]["ssid"]
            pw = text_input(d, ctx.input, "Password for " + ssid, "")
            if pw is not None:
                ctx.settings.set("wifi_ssid", ssid)
                ctx.settings.set("wifi_password", pw)
                d.clear()
                d.text(80, 150, "Connecting...", d.fg)
                d.swap()
                if ctx.wifi.connect(ssid, pw):
                    alert(d, ctx.input, "Connected to " + ssid, "WiFi")
                    return
                else:
                    alert(d, ctx.input, "Failed to connect", "WiFi")


def main():
    ctx = _create_ctx()

    # attach helpers
    ctx.gc = lambda: _gc(ctx)
    ctx.back = lambda: _back(ctx)

    from picoware.core.input import KEY_HOME

    print("PicoCalcOS ready. Free mem:", mem_free())

    while True:
        # build launcher items
        builtin = ["Settings", "App Store"]
        try:
            apps = _list_apps(ctx.storage)
        except Exception as e:
            print("_list_apps failed:", e)
            apps = []
        app_labels = [a["name"] for a in apps]
        all_labels = builtin + app_labels + ["Power Off"]

        from picoware.ui.menu import Menu
        from picoware.ui.statusbar import StatusBar

        statusbar = StatusBar(ctx.display, ctx.hw, ctx.settings, ctx.wifi)
        sb_h = statusbar.height

        menu = Menu(
            ctx.display, all_labels, title="PicoCalcOS",
            y=sb_h, h=320 - sb_h,
        )

        # launcher loop
        in_launcher = True
        while in_launcher:
            # draw status bar then menu
            ctx.display.clear()
            statusbar.draw()
            menu._y = sb_h
            menu._h = 320 - sb_h
            menu.draw(force=True)

            # wait for input
            while True:
                ctx.input.poll()
                k = ctx.input.key
                if k == -1:
                    continue

                result = menu.handle_input(k)
                if result is not None:
                    break

                # redraw on nav
                ctx.display.clear()
                statusbar.draw()
                menu.draw(force=True)

            if result == -1:
                continue  # no back from launcher

            choice = all_labels[result]

            if choice == "Settings":
                _run_settings(ctx)

            elif choice == "App Store":
                from picoware.net.appstore import run_appstore
                run_appstore(ctx)
                collect()

            elif choice == "Power Off":
                ctx.hw.power_off()

            else:
                # load and run app
                app_index = result - len(builtin)
                app_info = apps[app_index]
                slug = app_info["slug"]
                display_name = app_info["name"]

                collect()
                mod = _load_app(slug)
                if mod is None:
                    from picoware.ui.dialog import alert
                    alert(ctx.display, ctx.input, "Failed to load " + display_name, "Error")
                    continue

                ctx._back_requested = False
                try:
                    if not mod.start(ctx):
                        from picoware.ui.dialog import alert
                        alert(ctx.display, ctx.input, display_name + " failed to start", "Error")
                        _unload_app(slug, mod)
                        continue

                    while not ctx._back_requested:
                        ctx.input.poll()
                        if ctx.input.key == KEY_HOME:
                            ctx.input.reset()
                            break
                        mod.run(ctx)

                    mod.stop(ctx)
                except Exception as e:
                    print("App error:", slug, e)
                    try:
                        mod.stop(ctx)
                    except:
                        pass

                _unload_app(slug, mod)
                collect()
                print("Returned to launcher. Free mem:", mem_free())
