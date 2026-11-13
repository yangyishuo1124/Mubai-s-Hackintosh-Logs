#!/bin/zsh
set -u
out="$HOME/Desktop/S5650AA-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"

sw_vers > "$out/system.txt" 2>&1
uname -a >> "$out/system.txt" 2>&1
networksetup -listallhardwareports > "$out/network-ports.txt" 2>&1
system_profiler SPAirPortDataType SPBluetoothDataType SPAudioDataType SPUSBDataType > "$out/system-profiler.txt" 2>&1
ifconfig > "$out/ifconfig.txt" 2>&1
pmset -g batt > "$out/battery-summary.txt" 2>&1
ioreg -lw0 -r -c AppleSmartBattery > "$out/battery-ioreg.txt" 2>&1
ioreg -lw0 -r -c VoodooI2CController > "$out/i2c-controller-ioreg.txt" 2>&1
ioreg -lw0 -r -c VoodooI2CHIDDevice > "$out/touchpad-ioreg.txt" 2>&1
kmutil showloaded > "$out/loaded-kexts.txt" 2>&1
log show --last 30m --style compact --predicate 'eventMessage CONTAINS[c] "rtw89" OR eventMessage CONTAINS[c] "RealtekFirmware" OR eventMessage CONTAINS[c] "BlueToolFixup" OR eventMessage CONTAINS[c] "VoodooI2C" OR eventMessage CONTAINS[c] "AppleALC" OR eventMessage CONTAINS[c] "SimpleHDA"' > "$out/driver-log.txt" 2>&1

echo "Saved to $out"
echo "The report may contain Wi-Fi names, MAC addresses, serial numbers and Bluetooth identifiers. Review it before sharing."
