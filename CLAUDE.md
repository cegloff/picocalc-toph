# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PicoCalcOS is a custom firmware/OS for the PicoCalc (Raspberry Pi Pico 2W). It's built on MicroPython with native C hardware drivers. The OS provides a launcher, settings, WiFi management, and a plugin-based app system that loads apps from the SD card at runtime.

## Build

```bash
# Requires MicroPython repo at ~/pico/micropython (override with MICROPYTHON_DIR env var)
# Also requires ARM GCC toolchain and CMake >= 3.12
./build.sh
```

The build script copies frozen Python modules and C drivers into the MicroPython RP2 port, then builds firmware. Output: `builds/PicoCalcOS-Pico2W.uf2`.

There are no tests, linter, or formatter configured.

## Architecture

### Layers

1. **C Drivers** (`drivers/`) — Hardware access via PIO/DMA/I2C/SPI, compiled as MicroPython C modules
2. **Python HAL** (`firmware/picoware/core/`) — Wraps C drivers into Python classes (Display, Input, Storage, Hardware, Settings)
3. **UI Framework** (`firmware/picoware/ui/`) — Menu, Dialog, StatusBar components
4. **OS Main** (`firmware/picoware/main.py`) — Launcher loop, app lifecycle, settings UI
5. **Apps** (`apps/`) — Plugin apps deployed to `/sd/picoware/apps/` on the device

### Boot Flow

`firmware/main.py` → `picoware.main.main()` → creates `Ctx` (initializes all subsystems) → enters launcher loop → discovers apps from `/sd/picoware/apps/` → loads/runs selected app

### App Lifecycle

Apps are Python modules with three required functions receiving a `ctx` object:
- `start(ctx)` — Initialize, return `True` on success
- `run(ctx)` — Called repeatedly in a loop (must not block indefinitely)
- `stop(ctx)` — Cleanup

The launcher calls `run()` in a tight loop, checking for `KEY_HOME` between calls to return to launcher. Apps call `ctx.back()` to request exit.

### Ctx Object

Single context object passed to all app functions, providing access to all subsystems:
- `ctx.display` — 320x320 framebuffer (draw primitives, text, `swap()` to flush)
- `ctx.input` — Keyboard (`poll()`, then read `.key` / `.char`)
- `ctx.storage` — SD card filesystem (VFS mounted at `/sd`)
- `ctx.settings` — Persistent JSON config at `/sd/picoware/settings/system.json`
- `ctx.hw` — Battery level, backlight control, power off
- `ctx.wifi` — Optional; may be `None`. Check before use.
- `ctx.back()` — Request return to launcher
- `ctx.gc()` — Force garbage collection

### Display

320x320 ST7789 with PSRAM framebuffer. All drawing happens in an offscreen buffer; call `d.swap()` to push to screen. Colors are RGB565 constants (BLACK, WHITE, RED, GREEN, BLUE, CYAN, MAGENTA, YELLOW, ORANGE, GRAY, DARK_GRAY, LIGHT_GRAY). Five bitmap fonts: FONT_8 through FONT_24.

### Input

Keyboard via I2C southbridge. Call `ctx.input.poll()` each frame, then read `ctx.input.key` (returns -1 if no key). Key constants are in `picoware.core.input` (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC, KEY_BACKSPACE, KEY_HOME, KEY_F1–KEY_F10, etc.).

### C Driver Modules

Registered via `drivers/PicoCalc/picocalcos_modules.cmake`. Each has its own CMakeLists.txt:
- `picoware_lcd` — ST7789 display + PSRAM framebuffer + PIO
- `picoware_keyboard` — I2C keyboard scanning
- `picoware_southbridge` — Battery/backlight via I2C
- `picoware_psram` — QSPI PSRAM via PIO+DMA
- `picoware_sd` — SPI SD card + FAT32 + VFS
- `picoware_boards` — Board detection
- `font` — Bitmap font rendering (8–24pt, RGB565/RGB332)

## Adding a New App

1. Create `apps/myapp/main.py` with `start(ctx)`, `run(ctx)`, `stop(ctx)`
2. Create `apps/myapp/app.json` with `{"name": "Display Name"}`
3. Rebuild firmware with `./build.sh`, or copy to `/sd/picoware/apps/myapp/` on the device

## Key Constraints

- MicroPython environment: no `asyncio` in app loops, limited heap (~200KB), no threading
- `run()` is called in a tight loop — keep it non-blocking
- Call `ctx.gc()` between memory-heavy operations to avoid OOM
- Apps are dynamically loaded/unloaded via `sys.path` manipulation; module cleanup happens automatically
- Display is 320x320 — all UI must fit within this resolution
