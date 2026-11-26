#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TC_DIR="$HOME/.loom/toolchains/rp2040"

echo "Installing Loom-Pico RP2040 toolchain to $TC_DIR..."
rm -rf "$TC_DIR/bin" "$TC_DIR/lib" "$TC_DIR/sdk"
mkdir -p "$TC_DIR/bin" "$TC_DIR/lib" "$TC_DIR/sdk"

cp "$REPO_ROOT/build/loomc-rp2040" "$TC_DIR/bin/loomc-rp2040"
cp "$REPO_ROOT/build/loomc-rp2040" "$TC_DIR/bin/loomc"

if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffreestanding -fdata-sections -ffunction-sections -c "$REPO_ROOT/sdk/targets/rp2040/boot.s" -o "$REPO_ROOT/build/boot.o"
    arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffreestanding -fdata-sections -ffunction-sections -c "$REPO_ROOT/sdk/targets/rp2040/scheduler_m0.s" -o "$REPO_ROOT/build/scheduler_m0.o"
    arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffreestanding -fdata-sections -ffunction-sections -Wall -Wextra -c "$REPO_ROOT/sdk/targets/rp2040/usb_cdc_rt.c" -o "$REPO_ROOT/build/usb_cdc_rt.o"
    arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -Os -ffreestanding -fdata-sections -ffunction-sections -Wall -Wextra -c "$REPO_ROOT/sdk/targets/rp2040/scheduler_kernel.c" -o "$REPO_ROOT/build/scheduler_kernel.o"
    arm-none-eabi-ar rcs "$REPO_ROOT/build/libloom_pico_rt.a" "$REPO_ROOT/build/boot.o" "$REPO_ROOT/build/scheduler_m0.o" "$REPO_ROOT/build/usb_cdc_rt.o" "$REPO_ROOT/build/scheduler_kernel.o"
    LIBGCC_PATH="$(arm-none-eabi-gcc -mcpu=cortex-m0plus -mthumb -print-libgcc-file-name)"
    if [ -f "$LIBGCC_PATH" ]; then
        cp "$LIBGCC_PATH" "$TC_DIR/lib/libgcc.a"
    fi
fi
cp "$REPO_ROOT/build/libloom_pico_rt.a" "$TC_DIR/lib/libloom_pico_rt.a"

cp -R "$REPO_ROOT/sdk/." "$TC_DIR/sdk/"

cat > "$TC_DIR/toolchain.toml" <<EOF
name = "rp2040"
kind = "rp2040"
version = "1.4.0"
description = "Loom RP2040 Embedded Bare-Metal Toolchain (ARM Cortex-M0+)"
target = "thumbv6m-none-eabi"
cpu = "cortex-m0plus"
EOF

echo "Installed Loom-Pico RP2040 toolchain successfully."
