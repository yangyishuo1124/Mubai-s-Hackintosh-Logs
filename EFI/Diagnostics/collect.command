#!/bin/zsh
set -u

here="$(cd "$(dirname "$0")" && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"
out="$(mktemp -d "/tmp/s5650aa-${stamp}.XXXXXX")"
mkdir -p "$here/reports"

sw_vers > "$out/system.txt" 2>&1
uname -a >> "$out/system.txt" 2>&1
sysctl hw.ncpu hw.activecpu hw.physicalcpu hw.logicalcpu hw.physicalcpu_max hw.logicalcpu_max > "$out/cpu-counts.txt" 2>&1
ioreg -r -c AppleACPICPU -l -w0 > "$out/cpu-ioreg.txt" 2>&1
ioreg -r -c IOAudioDevice -l -w0 > "$out/audio-devices.txt" 2>&1
ioreg -r -c IOHDACodecDevice -l -w0 > "$out/audio-codecs.txt" 2>&1
ioreg -r -n HDAS -l -w0 > "$out/audio-controller.txt" 2>&1
ioreg -r -n HDEF -l -w0 > "$out/audio-controller-hdef.txt" 2>&1
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
# The Bluetooth daemon can wait for an unrelated IOService to become idle.
# Keep the complete topology, including busy counters, before sampling it.
ioreg -p IOService -w0 > "$out/ioservice-tree.txt" 2>&1
grep -E 'busy [1-9][0-9]*' "$out/ioservice-tree.txt" > "$out/ioservice-busy.txt" || true
ps -axo pid,ppid,state,etime,comm > "$out/processes.txt" 2>&1
launchctl print system/com.apple.bluetoothd > "$out/bluetooth-launchd.txt" 2>&1
btpid="$(pgrep -x bluetoothd | head -n 1)"
if [[ -n "$btpid" ]]; then
    /usr/bin/sample "$btpid" 3 -file "$out/bluetooth-sample.txt" > "$out/bluetooth-sample-status.txt" 2>&1
fi
ioreg -p IOService -w0 > "$out/ioservice-tree-after-sample.txt" 2>&1
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
/usr/bin/log show --last boot --style compact --predicate 'eventMessage CONTAINS[c] "IOKitWaitQuiet" OR eventMessage CONTAINS[c] "busy timeout" OR eventMessage CONTAINS[c] "stall"' > "$out/device-init-log.txt" 2>&1
/usr/bin/log show --last 30m --style compact --predicate 'eventMessage CONTAINS[c] "rtw89" OR eventMessage CONTAINS[c] "DHCP" OR eventMessage CONTAINS[c] "bootp" OR eventMessage CONTAINS[c] "WiFi"' > "$out/wifi-log.txt" 2>&1

archive="$here/reports/s5650aa-${stamp}.zip"
/usr/bin/log show --last boot --info --style compact --predicate 'process == "coreaudiod" OR eventMessage CONTAINS[c] "SimpleHDA" OR eventMessage CONTAINS[c] "AppleHDA" OR eventMessage CONTAINS[c] "AppleALC"' > "$out/audio-log.txt" 2>&1
/usr/bin/ditto -c -k "$out" "$archive"
sync
echo "Saved diagnostics to: $archive"
echo "This report can contain network names and hardware identifiers. Review it before sharing."
echo "Before rebooting, run: sudo diskutil unmount /Volumes/SYSTEM"
