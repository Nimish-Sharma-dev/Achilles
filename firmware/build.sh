#!/usr/bin/env bash
# firmware/build.sh — recompiles both demo firmware images.
# Needs: apt install gcc-arm-none-eabi binutils-arm-none-eabi
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CFLAGS="-mcpu=cortex-m3 -mthumb -Wall -O1 -ffreestanding -nostdlib -fno-builtin -std=c11"
LDFLAGS="-T linker.ld -nostdlib -Wl,--gc-sections"

for VARIANT in baseline tampered; do
  echo "== building $VARIANT =="
  arm-none-eabi-gcc $CFLAGS -c startup.c -o startup_$VARIANT.o
  arm-none-eabi-gcc $CFLAGS -c main_$VARIANT.c -o main_$VARIANT.o
  arm-none-eabi-gcc $CFLAGS $LDFLAGS startup_$VARIANT.o main_$VARIANT.o -o firmware_$VARIANT.elf
  arm-none-eabi-objcopy -O binary firmware_$VARIANT.elf firmware_$VARIANT.bin
  rm -f startup_$VARIANT.o main_$VARIANT.o
done
echo "Done. firmware_baseline.{elf,bin} and firmware_tampered.{elf,bin} rebuilt."
