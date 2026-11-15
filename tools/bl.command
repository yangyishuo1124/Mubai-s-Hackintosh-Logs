#!/bin/zsh
set -u
OUT="/Volumes/SYSTEM/EFI/Diagnostics/reports/bl-diag.txt"
mkdir -p "/Volumes/SYSTEM/EFI/Diagnostics/reports"
{
  echo "=== DATE ==="
  /bin/date
  echo "=== HARDWARE ==="
  /usr/sbin/system_profiler SPHardwareDataType 2>&1
  echo "=== DISPLAYS ==="
  /usr/sbin/system_profiler SPDisplaysDataType 2>&1
  echo "=== LOG SHOW (XeGfxIntelFB) ==="
  /usr/bin/log show --style compact --predicate 'eventMessage contains "XeGfxIntelFB"' --last 1h 2>&1
  echo "=== IOREG PNLF ==="
  /usr/sbin/ioreg -r -n PNLF 2>&1
  echo "=== IOREG AppleBacklightDisplay / AppleDisplay / IODisplayConnect ==="
  /usr/sbin/ioreg -l -w0 -c AppleBacklightDisplay 2>&1
  /usr/sbin/ioreg -l -w0 -c XeGfxBacklightHandler 2>&1
  /usr/sbin/ioreg -l -w0 -c AppleDisplay 2>&1
  /usr/sbin/ioreg -l -w0 -c IODisplayConnect 2>&1
  echo "=== LOG SHOW (COREBRIGHTNESSD / BRIGHTNESS) ==="
  /usr/bin/log show --style compact --predicate 'process == "corebrightnessd" OR eventMessage contains[c] "brightness"' --last 10m | /usr/bin/tail -n 100 2>&1
  echo "=== IOGRAPHICSFAMILY INFO.PLIST ==="
  /usr/bin/grep -l "AppleBacklightDisplay" /System/Library/Extensions/*.kext/Contents/Info.plist /System/Library/Extensions/*.kext/Contents/PlugIns/*.kext/Contents/Info.plist 2>&1
  /usr/bin/plutil -p /System/Library/Extensions/IOGraphicsFamily.kext/Contents/Info.plist 2>&1
  echo "=== IOREG AppleACPILid & LID0 & ApplePS2Keyboard ==="
  /usr/sbin/ioreg -r -c AppleACPILid 2>&1
  /usr/sbin/ioreg -r -n LID0 -d 2 2>&1
  /usr/sbin/ioreg -r -c ApplePS2Keyboard -d 2 2>&1
  echo "=== APPLEBACKLIGHT INFO.PLIST ==="
  /usr/bin/plutil -p /System/Library/Extensions/AppleBacklight.kext/Contents/Info.plist 2>&1
  echo "=== IOREG XeGfxIntelFramebuffer ==="
  /usr/sbin/ioreg -r -c XeGfxIntelFramebuffer -d 4 2>&1
  echo "=== KEXTSTAT ==="
  /usr/sbin/kextstat | /usr/bin/grep -i -E "xegfx|backlight|display" 2>&1
  echo "=== NVRAM ==="
  /usr/sbin/nvram -p | /usr/bin/grep -i xei 2>&1
  echo "=== PMSET -G ==="
  /usr/bin/pmset -g 2>&1
  echo "=== PMSET ASSERTIONS ==="
  /usr/bin/pmset -g assertions 2>&1
  echo "=== PMSET LOG (TAIL 120) ==="
  /usr/bin/pmset -g log | /usr/bin/tail -n 120 2>&1
  echo "=== IOREG CLAMSHELL & IOPM ==="
  /usr/sbin/ioreg -r -k AppleClamshellState 2>&1
  /usr/sbin/ioreg -r -c IOPMrootDomain -d 2 2>&1
  echo "=== IOREG ACPI LID / PWRB / SLPB ==="
  /usr/sbin/ioreg -p IOACPIPlane -w 0 | /usr/bin/grep -i -E "LID|PNP0C0D|PWRB|SLPB" 2>&1
  echo "=== LOG SHOW (SLEEP/LID/WAKE/PMRD/FB 15m) ==="
  /usr/bin/log show --style compact --predicate 'eventMessage contains[c] "clamshell" OR eventMessage contains[c] "lid" OR eventMessage contains[c] "PMRD" OR eventMessage contains[c] "XeGfxIntelFB" OR eventMessage contains[c] "AppleACPIButtons" OR eventMessage contains[c] "ApplePS2Keyboard"' --last 15m | /usr/bin/tail -n 200 2>&1
} > "$OUT"
/bin/ls -lh "$OUT"
echo "Saved to $OUT"
