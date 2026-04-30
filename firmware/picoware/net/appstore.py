"""App Store: browse, download, and update apps from tophcalc.egloff.tech."""

import gc
import uos

_HOST = "tophcalc.egloff.tech"
_APPS_PATH = "picoware/apps"
_SD_PREFIX = "/sd/picoware/apps"


def run_appstore(ctx):
    from picoware.ui.dialog import alert, confirm

    if not ctx.wifi or not ctx.wifi.is_connected:
        alert(ctx.display, ctx.input, "WiFi not connected. Connect in Settings first.", "App Store")
        return

    # fetch manifest
    _show_status(ctx, "Fetching apps...")
    try:
        from picoware.net.http import http_get
        body, _ = http_get(_HOST, "/apps.json")
        from json import loads
        manifest = loads(body)
        apps = manifest.get("apps", [])
        del body, manifest
        gc.collect()
    except Exception as e:
        alert(ctx.display, ctx.input, "Failed to fetch app list: {}".format(e), "Error")
        return

    if not apps:
        alert(ctx.display, ctx.input, "No apps available.", "App Store")
        return

    # app list menu loop
    _app_menu(ctx, apps)


def _app_menu(ctx, apps):
    from picoware.ui.menu import Menu
    from picoware.ui.dialog import alert, confirm

    while True:
        # build labels with install status
        labels = []
        for app in apps:
            slug = app["slug"]
            installed = ctx.storage.exists("{}/{}/main.py".format(_APPS_PATH, slug))
            tag = " [installed]" if installed else " [new]"
            labels.append(app["name"] + tag)
        labels.append("Back")

        menu = Menu(ctx.display, labels, title="App Store")

        while True:
            ctx.display.clear()
            menu.draw(force=True)

            while True:
                ctx.input.poll()
                k = ctx.input.key
                if k == -1:
                    continue
                result = menu.handle_input(k)
                if result is not None:
                    break
                ctx.display.clear()
                menu.draw(force=True)

            if result == -1 or result == len(apps):
                return

            app = apps[result]
            slug = app["slug"]
            name = app["name"]
            files = app.get("files", [])
            size_kb = app.get("size", 0) // 1024

            installed = ctx.storage.exists("{}/{}/main.py".format(_APPS_PATH, slug))
            action = "Re-download" if installed else "Download"
            msg = "{} {}? ({}KB, {} files)".format(action, name, size_kb, len(files))

            if confirm(ctx.display, ctx.input, msg, "App Store"):
                del menu, labels
                gc.collect()
                ok = _download_app(ctx, app)
                if ok:
                    alert(ctx.display, ctx.input, "{} installed.".format(name), "App Store")
                # loop back to menu (labels will refresh install status)
            break  # break inner menu loop to rebuild labels

        gc.collect()


def _download_app(ctx, app):
    from picoware.ui.dialog import alert
    from picoware.net.http import HttpSession

    slug = app["slug"]
    name = app["name"]
    files = app.get("files", [])
    all_files = files + ["app.json"]

    tmp_rel = "{}/{}_tmp".format(_APPS_PATH, slug)
    tmp_abs = "{}/{}_tmp".format(_SD_PREFIX, slug)
    final_rel = "{}/{}".format(_APPS_PATH, slug)
    final_abs = "{}/{}".format(_SD_PREFIX, slug)

    gc.collect()

    # clean stale temp dir from previous failed download
    if ctx.storage.exists(tmp_rel):
        try:
            _rmdir(ctx, tmp_rel)
        except:
            pass

    ctx.storage.mkdir(tmp_rel)

    session = HttpSession(_HOST)

    try:
        session.open()
        try:
            for i, fname in enumerate(all_files):
                _draw_progress(ctx, name, i, len(all_files), fname, 0, -1)
                path = "/apps/{}/{}".format(slug, fname)
                dest = "{}/{}".format(tmp_abs, fname)
                try:
                    session.get_to_file(path, dest)
                except Exception as e:
                    print("Download error:", fname, e, "free=", gc.mem_free())
                    try:
                        uos.remove(dest)
                    except:
                        pass
                    raise
                gc.collect()
        finally:
            session.close()

        # success: swap temp → final
        if ctx.storage.exists(final_rel):
            _rmdir(ctx, final_rel)
        uos.rename(tmp_abs, final_abs)
        return True

    except Exception as e:
        print("Download error:", e)
        # clean up temp — guard with exists() so we don't log ENOENT noise
        # when mkdir itself failed and the temp dir was never created.
        try:
            if ctx.storage.exists(tmp_rel):
                _rmdir(ctx, tmp_rel)
        except:
            pass
        alert(ctx.display, ctx.input, "Download failed: {}".format(e), "Error")
        return False


def _rmdir(ctx, rel_path):
    """Remove a directory and all its files."""
    for fname in ctx.storage.listdir(rel_path):
        ctx.storage.remove("{}/{}".format(rel_path, fname))
    ctx.storage.remove(rel_path)


def _draw_progress(ctx, app_name, file_idx, file_count, filename, _bytes_done, _content_length):
    d = ctx.display
    d.clear()
    fh = d.font_height()

    # title bar
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, "Downloading", d.bg)

    # app name
    y = fh + 24
    d.text(8, y, app_name, d.fg)

    # file info
    y += fh + 12
    d.text(8, y, "File {}/{}: {}".format(file_idx + 1, file_count, filename), d.fg)

    # file-level progress bar
    y += fh + 16
    bar_x, bar_w, bar_h = 16, 288, 20
    d.rect(bar_x, y, bar_w, bar_h, d.fg)
    if file_count > 0:
        fill_w = (bar_w - 4) * file_idx // file_count
        if fill_w > 0:
            d.fill_rect(bar_x + 2, y + 2, fill_w, bar_h - 4, d.fg)

    d.swap()


def _show_status(ctx, message):
    d = ctx.display
    d.clear()
    fh = d.font_height()
    d.fill_rect(0, 0, 320, fh + 10, d.fg)
    d.text(4, 5, "App Store", d.bg)
    d.text(8, fh + 24, message, d.fg)
    d.swap()
