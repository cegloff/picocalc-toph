# Building PicoCalcOS Firmware

This guide covers setting up a build environment and compiling the PicoCalcOS firmware for the PicoCalc (Raspberry Pi Pico 2W).

## Prerequisites

- **Git**
- **GNU Make**
- **CMake** >= 3.12
- **ARM GCC toolchain** (`gcc-arm-none-eabi`)
- **Python 3**

## Linux Setup

### 1. Install Build Tools

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y cmake gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential python3 git
```

**Fedora:**

```bash
sudo dnf install -y cmake arm-none-eabi-gcc-cs arm-none-eabi-newlib gcc gcc-c++ make python3 git
```

**Arch Linux:**

```bash
sudo pacman -S cmake arm-none-eabi-gcc arm-none-eabi-newlib base-devel python git
```

### 2. Clone and Build MicroPython

```bash
mkdir -p ~/pico
git clone https://github.com/micropython/micropython.git ~/pico/micropython
cd ~/pico/micropython

# Build the MicroPython cross-compiler
make -C mpy-cross -j$(nproc)

# Initialize submodules for the Pico 2W board
cd ports/rp2
make BOARD=RPI_PICO2_W submodules
```

### 3. Clone PicoCalcOS

```bash
git clone https://github.com/topherCantique/picocalc-toph.git
cd picocalc-toph
```

### 4. Build Firmware

```bash
./build.sh
```

By default the build script looks for MicroPython at `~/pico/micropython`. To use a different location:

```bash
MICROPYTHON_DIR=/path/to/micropython ./build.sh
```

The compiled firmware will be at `builds/PicoCalcOS-Pico2W.uf2`.

---

## Windows + WSL Setup

The build uses the ARM GCC cross-compiler which requires a Linux environment. On Windows, use WSL (Windows Subsystem for Linux).

### 1. Install WSL

If WSL is not already installed, open PowerShell as Administrator:

```powershell
wsl --install -d Ubuntu-22.04
```

Restart your machine if prompted, then launch Ubuntu from the Start menu to complete setup.

### 2. Install Build Tools in WSL

Open your WSL Ubuntu terminal:

```bash
sudo apt-get update
sudo apt-get install -y cmake gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential python3 git
```

### 3. Clone and Build MicroPython (inside WSL)

```bash
mkdir -p ~/pico
git clone https://github.com/micropython/micropython.git ~/pico/micropython
cd ~/pico/micropython

# Build the MicroPython cross-compiler
make -C mpy-cross -j$(nproc)

# Initialize submodules for the Pico 2W board
cd ports/rp2
make BOARD=RPI_PICO2_W submodules
```

### 4. Clone PicoCalcOS

You can either clone the repo inside WSL or work with an existing clone on the Windows filesystem. The Windows `C:\` drive is accessible in WSL at `/mnt/c/`.

**Option A — Clone inside WSL (faster builds):**

```bash
cd ~
git clone https://github.com/topherCantique/picocalc-toph.git
cd picocalc-toph
```

**Option B — Use existing Windows clone:**

```bash
cd /mnt/c/Users/YourUsername/path/to/picocalc-toph
```

### 5. Build Firmware

If your repo was cloned on Windows, the build script may have Windows-style line endings (`\r\n`) that bash can't parse. Use `sed` to strip them:

```bash
# From a Windows clone (fixes CRLF line endings)
sed 's/\r$//' build.sh | bash

# From a WSL-native clone (no fix needed)
./build.sh
```

The compiled firmware will be at `builds/PicoCalcOS-Pico2W.uf2`.

---

## Flashing the Firmware

### Enter Bootloader Mode

1. Hold the **BOOTSEL** button on the Pico 2W
2. While holding, press and release **RESET** (or plug in USB)
3. Release BOOTSEL — the device mounts as a USB drive named **RP2350**

### Copy the UF2

**Linux:**

```bash
cp builds/PicoCalcOS-Pico2W.uf2 /media/$USER/RP2350/
```

**Windows (from Explorer):**

Copy `builds\PicoCalcOS-Pico2W.uf2` to the `RP2350` drive.

**Windows (from Git Bash / terminal):**

```bash
cp builds/PicoCalcOS-Pico2W.uf2 /g/
```

Replace `/g/` with whichever drive letter the RP2350 mounted as.

The device will reboot automatically after the copy completes.

---

## What the Build Does

The `build.sh` script:

1. **Cleans** previous frozen modules from the MicroPython RP2 port
2. **Copies frozen Python modules** (`firmware/main.py`, `firmware/picoware/`) into MicroPython's module directory
3. **Copies C hardware drivers** (`drivers/PicoCalc/`, `drivers/font/`) into MicroPython's module directory
4. **Builds** MicroPython for the `RPI_PICO2_W` board with the custom C modules
5. **Outputs** the UF2 firmware to `builds/PicoCalcOS-Pico2W.uf2`

### C Driver Modules

The firmware includes these native C modules (registered via `drivers/PicoCalc/picocalcos_modules.cmake`):

| Module | Purpose |
|--------|---------|
| `picoware_lcd` | ST7789 320x320 display via PIO + PSRAM framebuffer |
| `picoware_keyboard` | I2C keyboard scanning |
| `picoware_southbridge` | Battery monitoring, backlight, power control via I2C |
| `picoware_psram` | QSPI PSRAM access via PIO + DMA |
| `picoware_sd` | SPI SD card with FAT32 + VFS |
| `picoware_boards` | Hardware board detection |
| `font` | Bitmap font rendering (8pt–24pt) |

## Troubleshooting

### `cyw43-driver not initialized`

You need to initialize submodules specifically for the Pico 2W board (which has WiFi):

```bash
cd ~/pico/micropython/ports/rp2
make BOARD=RPI_PICO2_W submodules
```

### `$'\r': command not found`

The build script has Windows line endings. Run with:

```bash
sed 's/\r$//' build.sh | bash
```

### `MicroPython not found`

Set the `MICROPYTHON_DIR` environment variable to point to your MicroPython clone:

```bash
MICROPYTHON_DIR=~/pico/micropython ./build.sh
```

### Build fails with out-of-memory on WSL

WSL may have limited memory by default. Create or edit `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=4GB
```

Then restart WSL: `wsl --shutdown` from PowerShell.
