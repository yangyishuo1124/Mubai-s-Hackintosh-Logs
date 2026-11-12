#!/bin/zsh
set -u

here="$(cd "$(dirname "$0")" && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"
out="$(mktemp -d "/tmp/s5650aa-${stamp}.XXXXXX")"
mkdir -p "$here/reports"

sw_vers > "$out/system.txt" 2>&1
uname -a >> "$out/system.txt" 2>&1
networksetup -listallhardwareports > "$out/network-ports.txt" 2>&1
networksetup -listallnetworkservices > "$out/network-services.txt" 2>&1
networksetup -getairportnetwork en0 > "$out/current-wifi.txt" 2>&1
ifconfig en0 > "$out/en0.txt" 2>&1
ipconfig getifaddr en0 > "$out/en0-address.txt" 2>&1
ipconfig getpacket en0 > "$out/en0-dhcp-packet.txt" 2>&1
route -n get default > "$out/default-route.txt" 2>&1
scutil --nwi > "$out/network-state.txt" 2>&1
system_profiler SPAirPortDataType > "$out/hardware.txt" 2>&1
ioreg -p IOUSB -l -w0 > "$out/usb-ioreg.txt" 2>&1
ioreg -r -c IOBluetoothHostController -l -w0 > "$out/bluetooth-ioreg.txt" 2>&1
ioreg -r -c RealtekBluetoothFirmware -l -w0 > "$out/realtek-firmware-ioreg.txt" 2>&1
ioreg -r -c VoodooI2CHIDDevice -l -w0 > "$out/touchpad-ioreg.txt" 2>&1
kmutil showloaded > "$out/loaded-kexts.txt" 2>&1
ioreg -lw0 -r -c AppleSmartBattery > "$out/battery.txt" 2>&1
dmesg | tail -n 5000 > "$out/kernel-messages.txt" 2>&1
nvram -p | grep -i bluetooth > "$out/bluetooth-nvram.txt" 2>&1
gateway="$(route -n get default 2>/dev/null | awk '/gateway:/ {print $2; exit}')"
if [[ -n "$gateway" ]]; then
    ping -c 3 -W 1000 "$gateway" > "$out/gateway-ping.txt" 2>&1
fi
ping -c 3 -W 1000 1.1.1.1 > "$out/internet-ping.txt" 2>&1

if [[ -x "$here/rtw89ctl" ]]; then
    "$here/rtw89ctl" status > "$out/rtw89-status.txt" 2>&1
    "$here/rtw89ctl" log | tail -n 500 > "$out/rtw89-log.txt" 2>&1
fi

/usr/bin/log show --last boot --info --debug --style compact --predicate 'process == "bluetoothd" OR process == "BlueTool" OR eventMessage CONTAINS[c] "RealtekFirmware" OR eventMessage CONTAINS[c] "RealtekBluetoothFirmware"' > "$out/bluetooth-log.txt" 2>&1
/usr/bin/log show --last 30m --style compact --predicate 'eventMessage CONTAINS[c] "rtw89" OR eventMessage CONTAINS[c] "DHCP" OR eventMessage CONTAINS[c] "bootp" OR eventMessage CONTAINS[c] "WiFi"' > "$out/wifi-log.txt" 2>&1

archive="$here/reports/s5650aa-${stamp}.zip"
/usr/bin/ditto -c -k "$out" "$archive"
sync
echo "Saved diagnostics to: $archive"
echo "This report can contain network names and hardware identifiers. Review it before sharing."
echo "Before rebooting, run: sudo diskutil unmount /Volumes/SYSTEM"
