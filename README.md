# Loom-Pico (v1.5.0)

Bare-metal **Loom compiler (`loomc-rp2040`)**, **USB-CDC runtime**, and **complete RP2040 Board Support Package (BSP)** for the **Raspberry Pi Pico** (`thumbv6m-none-eabi`, ARM Cortex-M0+).

## Features

- **Unified `loom` CLI Integration**: Build, flash, and monitor RP2040 firmware via `loom build`, `loom flash`, and `loom monitor`.
- **Memory Footprint & Section Analysis**: Automatically displays Flash and SRAM utilization bars on build/run.
- **Bare-Metal TargetProfile**: Enforces static/stack-only semantics (`thumbv6m-none-eabi`, `cortex-m0plus`, 32-bit pointers) and rejects host heap/thread/file/network APIs at compile time.
- **USB-CDC Serial `Print(...)`**: Built-in RP2040 `USBCTRL` device controller and CDC-ACM driver (`sdk/targets/rp2040/usb_cdc_rt.c`) routes Loom `Print(...)` directly over USB serial.
- **Complete Fresh Loom v1.5 BSP** (`sdk/targets/rp2040/bsp/`):
  - `RP2040` — Register base addresses, atomic SET/CLR/XOR aliases, resets
  - `Clocks` — XOSC 12 MHz, `PLL_SYS` 125 MHz, `PLL_USB` 48 MHz
  - `System` — SysTick, NVIC IRQs, WFI, DMB, chip/core IDs, reboot
  - `Time` — 64-bit microsecond timer, `Sleep_Us`, `Sleep_Ms`, hardware alarms
  - `GPIO` — Pin functions, pulls, digital I/O, toggle (`Gpio_Init_Output`, `Gpio_Write`, `Gpio_Read`, `Gpio_Toggle`)
  - `UART` — PL011 `UART0`/`UART1` TX/RX
  - `SPI` — PL022 `SPI0`/`SPI1` master driver
  - `I2C` — DW_apb_i2c `I2C0`/`I2C1` master driver with `I2C_Error` handling
  - `PWM` — 8 slices x 2 channels
  - `ADC` — 12-bit SAR ADC + internal temperature sensor
  - `DMA` — 12-channel DMA controller
  - `PIO` — `PIO0`/`PIO1` instruction loading, state machine control, TX/RX FIFOs
  - `Watchdog` — Hardware watchdog timer & scratch registers
  - `RTC` — Real-Time Clock
  - `Multicore` — SIO FIFO & Core1 launch
  - `Usb_Cdc` — USB-CDC serial TX/RX helpers

## Building & Installing the Toolchain

```bash
cmake -S . -B build
cmake --build build -j8
# Build bare-metal runtime (libloom_pico_rt.a)
mkdir -p build/rt
arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffunction-sections -fdata-sections -c sdk/targets/rp2040/boot.s -o build/rt/boot.o
arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffreestanding -nostdlib -ffunction-sections -fdata-sections -c sdk/targets/rp2040/usb_cdc_rt.c -o build/rt/usb_cdc_rt.o
arm-none-eabi-ar rcs build/libloom_pico_rt.a build/rt/boot.o build/rt/usb_cdc_rt.o
./scripts/install_toolchain.sh
```

## Running & Flashing the Example (`Blinky_USB`)

```bash
cd examples/Blinky_USB
# Build, flash to Pico, and open live serial monitor in one command
loom flash --monitor
```

Or step-by-step:
```bash
loom build
loom flash
loom monitor
```

## Running Tests

```bash
python3 tests/run_pico_tests.py
```
