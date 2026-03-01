#!/bin/bash
# Build PicoCalcOS firmware for PicoCalc Pico 2W
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MICROPYTHON_DIR="${MICROPYTHON_DIR:-$HOME/pico/micropython}"
RPI_PORT="$MICROPYTHON_DIR/ports/rp2"
BOARD="RPI_PICO2_W"

echo "=== PicoCalcOS Build ==="
echo "Repository:   $REPO_DIR"
echo "MicroPython:  $MICROPYTHON_DIR"
echo ""

if [ ! -d "$MICROPYTHON_DIR" ]; then
    echo "ERROR: MicroPython not found at $MICROPYTHON_DIR"
    echo "Clone it first: git clone https://github.com/micropython/micropython.git ~/pico/micropython"
    echo "Then: cd ~/pico/micropython && make -C mpy-cross && cd ports/rp2 && make submodules"
    exit 1
fi

echo "Cleaning previous modules..."
rm -rf "$RPI_PORT/modules/main.py"
rm -rf "$RPI_PORT/modules/picoware"
rm -rf "$RPI_PORT/modules/PicoCalc"
rm -rf "$RPI_PORT/modules/font"

echo "Installing modules..."

# Frozen Python modules
cp "$REPO_DIR/firmware/main.py" "$RPI_PORT/modules/main.py"
cp -r "$REPO_DIR/firmware/picoware" "$RPI_PORT/modules/picoware"

# C hardware drivers
cp -r "$REPO_DIR/drivers/PicoCalc" "$RPI_PORT/modules/PicoCalc"
cp -r "$REPO_DIR/drivers/font" "$RPI_PORT/modules/font"

echo "Building firmware..."
cd "$RPI_PORT"
rm -rf "build-$BOARD"
make -j$(nproc) BOARD="$BOARD" USER_C_MODULES="$RPI_PORT/modules/PicoCalc/picocalcos_modules.cmake"

echo ""
echo "=== Build Complete ==="
echo "Firmware: $RPI_PORT/build-$BOARD/firmware.uf2"

mkdir -p "$REPO_DIR/builds"
cp "$RPI_PORT/build-$BOARD/firmware.uf2" "$REPO_DIR/builds/PicoCalcOS-Pico2W.uf2"
echo "Copied to: $REPO_DIR/builds/PicoCalcOS-Pico2W.uf2"
