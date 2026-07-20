#!/usr/bin/env bash
# Compile + upload + monitor an Atmos bench sketch on the ESP32-S3 DevKitC-1 (N16R8).
#
#   ./atmos-flash.sh 01_bringup      # or 02_i2c_scan / 03_sd_test / 04_atmos_node
#   ./atmos-flash.sh 02_i2c_scan -n  # compile + upload, skip the serial monitor
#
# Ctrl-C exits the monitor.
#
# This is the repo copy (sketches live alongside it, so it works right after a
# clone). The bench-machine copy lives at ~/bin/atmos-flash.sh and points at
# ~/Arduino/ instead.

set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# N16R8 = 16MB flash + 8MB octal PSRAM (FlashSize/PSRAM are load-bearing; the
# board defaults 4M/PSRAM-off read back wrong).
# CDCOnBoot=default: Serial -> UART0 -> the WCH bridge this board's data port
# actually uses. CDCOnBoot=cdc would send Serial to the *native* USB port, which
# has no cable in it, so sketch output vanishes while the ROM banner still shows.
FQBN="esp32:esp32:esp32s3:CDCOnBoot=default,FlashSize=16M,PSRAM=opi"

SKETCH="${1:-}"
if [[ -z "$SKETCH" ]]; then
  echo "usage: $(basename "$0") <sketch-name> [-n]"
  echo "available:"
  ls -1 "$SCRIPT_DIR" | grep -E '^[0-9]{2}_' | sed 's/^/  /'
  exit 1
fi

SKETCH_DIR="$SCRIPT_DIR/$SKETCH"
[[ -d "$SKETCH_DIR" ]] || { echo "no such sketch: $SKETCH_DIR"; exit 1; }

# Prefer the CP2102 UART bridge (ttyUSB*) over the native-USB CDC port (ttyACM*):
# the UART bridge can always be driven into the bootloader without button presses.
PORT="$(ls /dev/ttyUSB* 2>/dev/null | head -1 || true)"
[[ -n "$PORT" ]] || PORT="$(ls /dev/ttyACM* 2>/dev/null | head -1 || true)"

if [[ -z "$PORT" ]]; then
  echo "No /dev/ttyUSB* or /dev/ttyACM* found."
  echo "Plug the DevKit into the UART USB-C port, then: dmesg | tail -20"
  exit 1
fi

echo "==> sketch $SKETCH"
echo "==> port   $PORT"

arduino-cli compile -b "$FQBN" "$SKETCH_DIR"
arduino-cli upload -b "$FQBN" -p "$PORT" "$SKETCH_DIR"

if [[ "${2:-}" == "-n" ]]; then
  echo "==> uploaded (monitor skipped)"
  exit 0
fi

echo "==> monitor @115200 (Ctrl-C to exit)"
# Deep-sleep sketches reboot the CDC port on every wake; --config on ttyACM can race that.
arduino-cli monitor -p "$PORT" --config baudrate=115200
