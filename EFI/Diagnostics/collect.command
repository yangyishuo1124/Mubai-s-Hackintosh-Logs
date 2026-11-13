#!/bin/zsh
set -u

here="$(cd "$(dirname "$0")" && pwd)"
out="$here/reports/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"

sw_vers > "$out/system.txt" 2>&1
uname -a >> "$out/system.txt" 2>&1
networksetup -listallhardwareports > "$out/network-ports.txt" 2>&1
networksetup -listallnetworkservices > "$out/network-services.txt" 2>&1
ifconfig en0 > "$out/en0.txt" 2>&1
ipconfig getifaddr en0 > "$out/en0-address.txt" 2>&1
ipconfig getpacket en0 > "$out/en0-dhcp-packet.txt" 2>&1
route -n get default > "$out/default-route.txt" 2>&1
scutil --nwi > "$out/network-state.txt" 2>&1
system_profiler SPAirPortDataType SPBluetoothDataType SPUSBDataType > "$out/hardware.txt" 2>&1
kmutil showloaded > "$out/loaded-kexts.txt" 2>&1
ioreg -lw0 -r -c AppleSmartBattery > "$out/battery.txt" 2>&1

if [[ -x "$here/rtw89ctl" ]]; then
    "$here/rtw89ctl" status > "$out/rtw89-status.txt" 2>&1
fi

log show --last boot --style compact --predicate 'eventMessage CONTAINS[c] "RealtekFirmware" OR eventMessage CONTAINS[c] "BlueToolFixup" OR eventMessage CONTAINS[c] "bluetoothd"' > "$out/bluetooth-log.txt" 2>&1
log show --last 30m --style compact --predicate 'eventMessage CONTAINS[c] "rtw89" OR eventMessage CONTAINS[c] "DHCP" OR eventMessage CONTAINS[c] "bootp" OR eventMessage CONTAINS[c] "WiFi"' > "$out/wifi-log.txt" 2>&1

echo "Saved diagnostics to: $out"
echo "This report can contain network names and hardware identifiers. Review it before sharing."
