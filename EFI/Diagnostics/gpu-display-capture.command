#!/bin/zsh
# Boot recovery: evidence only. No driver loading, initialization or display changes.
set -u
here="${0:A:h}"
out="$here/reports/boot-recovery-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
/usr/sbin/sysctl kern.bootargs kern.boottime > "$out/boot.txt" 2>&1
/usr/bin/kmutil showloaded > "$out/kexts.txt" 2>&1
/usr/sbin/ioreg -p IOService -w0 > "$out/services.txt" 2>&1
/bin/ps -axo pid,ppid,state,etime,comm > "$out/processes.txt" 2>&1
/usr/bin/log show --last 5m --style compact --predicate 'process == "WindowServer" OR process == "watchdogd" OR eventMessage CONTAINS[c] "panic"' > "$out/display-log.txt" 2>&1
