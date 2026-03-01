# PicoCalcOS C Modules for MicroPython
# Hardware drivers only — no LVGL, auto_complete, vector, response

# LCD Driver (ST7789 via PIO/PSRAM framebuffer)
add_library(usermod_picoware_lcd INTERFACE)
target_sources(usermod_picoware_lcd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_lcd/picoware_lcd.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_lcd/lcd.c
)
target_include_directories(usermod_picoware_lcd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_lcd
    ${CMAKE_BINARY_DIR}
)
target_compile_definitions(usermod_picoware_lcd INTERFACE MODULE_PICOWARE_LCD_ENABLED=1)
target_link_libraries(usermod INTERFACE usermod_picoware_lcd)
target_link_libraries(usermod_picoware_lcd INTERFACE pico_stdlib hardware_pio hardware_gpio hardware_clocks)

# Board Detection
add_library(usermod_picoware_boards INTERFACE)
target_sources(usermod_picoware_boards INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_boards/picoware_boards.c
)
target_include_directories(usermod_picoware_boards INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_boards
)
target_link_libraries(usermod INTERFACE usermod_picoware_boards)
target_link_libraries(usermod_picoware_boards INTERFACE pico_stdlib)

# PSRAM (QSPI via PIO + DMA)
add_library(usermod_picoware_psram INTERFACE)
pico_generate_pio_header(usermod_picoware_psram
    ${CMAKE_CURRENT_LIST_DIR}/picoware_psram/psram_qspi.pio
)
target_sources(usermod_picoware_psram INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_psram/picoware_psram.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_psram/psram_qspi.c
)
target_include_directories(usermod_picoware_psram INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_psram
)
target_compile_definitions(usermod_picoware_psram INTERFACE MODULE_PICOWARE_PSRAM_ENABLED=1)
target_compile_options(usermod_picoware_psram INTERFACE -Wno-unused-function)
target_link_libraries(usermod INTERFACE usermod_picoware_psram)
target_link_libraries(usermod_picoware_psram INTERFACE pico_stdlib hardware_pio hardware_dma hardware_gpio)

# Southbridge (I2C — backlight, battery, power)
add_library(usermod_picoware_southbridge INTERFACE)
target_sources(usermod_picoware_southbridge INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/picoware_southbridge.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/southbridge.c
)
target_include_directories(usermod_picoware_southbridge INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard
)
target_compile_definitions(usermod_picoware_southbridge INTERFACE MODULE_PICOWARE_SOUTHBRIDGE_ENABLED=1)
target_link_libraries(usermod INTERFACE usermod_picoware_southbridge)
target_link_libraries(usermod_picoware_southbridge INTERFACE pico_stdlib hardware_gpio hardware_i2c)

# Keyboard (I2C via southbridge)
add_library(usermod_picoware_keyboard INTERFACE)
target_sources(usermod_picoware_keyboard INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/picoware_keyboard.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/keyboard.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/southbridge.c
)
target_include_directories(usermod_picoware_keyboard INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard
)
target_compile_definitions(usermod_picoware_keyboard INTERFACE MODULE_PICOWARE_KEYBOARD_ENABLED=1)
target_link_libraries(usermod INTERFACE usermod_picoware_keyboard)
target_link_libraries(usermod_picoware_keyboard INTERFACE pico_stdlib hardware_gpio hardware_i2c)

# SD Card (SPI + FAT32 + VFS)
add_library(usermod_picoware_sd INTERFACE)
target_sources(usermod_picoware_sd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_sd/picoware_sd.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_sd/picoware_vfs.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_sd/sdcard.c
    ${CMAKE_CURRENT_LIST_DIR}/picoware_sd/fat32.c
)
target_include_directories(usermod_picoware_sd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_sd
)
target_compile_definitions(usermod_picoware_sd INTERFACE MODULE_WAVESHARE_SD_ENABLED=1)
target_link_libraries(usermod INTERFACE usermod_picoware_sd)
target_link_libraries(usermod_picoware_sd INTERFACE pico_stdlib pico_printf pico_float hardware_gpio hardware_i2c hardware_spi hardware_pio)

# Font module (8pt-24pt bitmap fonts)
add_library(usermod_font INTERFACE)
target_sources(usermod_font INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/../font/font_mp.c
    ${CMAKE_CURRENT_LIST_DIR}/../font/font8.c
    ${CMAKE_CURRENT_LIST_DIR}/../font/font12.c
    ${CMAKE_CURRENT_LIST_DIR}/../font/font16.c
    ${CMAKE_CURRENT_LIST_DIR}/../font/font20.c
    ${CMAKE_CURRENT_LIST_DIR}/../font/font24.c
)
target_include_directories(usermod_font INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/../font
)
target_link_libraries(usermod INTERFACE usermod_font)
