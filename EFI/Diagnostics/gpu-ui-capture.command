#!/bin/zsh
# Read-only compositor evidence; called before and after the boot capture interval.
set -u
out="$1"
mkdir -p "$out"
/usr/sbin/sysctl kern.bootargs kern.boottime > "$out/boot.txt" 2>&1
/usr/sbin/ioreg -r -c NMXAccel -l -w0 > "$out/accelerator.txt" 2>&1
/usr/sbin/ioreg -r -c IOFramebuffer -l -w0 > "$out/framebuffers.txt" 2>&1
/usr/sbin/ioreg -p IOService -w0 > "$out/services.txt" 2>&1
/usr/sbin/sysctl debug.nvaccelfb debug.nvaccel_headless debug.nvaccel_igpu \
    debug.nvaccel_pipe_init debug.nvaccel_pipe_validate debug.nvaccel_pipe_perform \
    debug.nvaccel_pipe_complete debug.nvaccel_iop_copy_us debug.nvaccel_iop_copy_us_max \
    debug.nvaccel_iop_vbl_hit debug.nvaccel_iop_vbl_miss > "$out/presentation.txt" 2>&1
/usr/bin/kmutil showloaded > "$out/kexts.txt" 2>&1
/bin/ps -axo pid,ppid,state,%cpu,etime,comm > "$out/processes.txt" 2>&1
[[ ! -f /tmp/nvmtl.log ]] || /usr/bin/tail -n 4000 /tmp/nvmtl.log > "$out/nvmtl-tail.txt"
/usr/bin/log show --last 5m --style compact --info --predicate \
    '(process == "WindowServer" AND (eventMessage CONTAINS[c] "Metal" OR eventMessage CONTAINS[c] "IOPresent" OR eventMessage CONTAINS[c] "accelerat" OR eventMessage CONTAINS[c] "GPU")) OR (process == "kernel" AND (eventMessage CONTAINS[c] "NMXAccel" OR eventMessage CONTAINS[c] "XeGfxIntelFB"))' \
    > "$out/compositor-log.txt" 2>&1
wpid="$(/usr/bin/pgrep -x WindowServer | /usr/bin/head -n 1)"
if [[ -n "$wpid" ]]; then
    /usr/bin/vmmap "$wpid" 2> "$out/vmmap-status.txt" | /usr/bin/grep -E 'NVMTLDriver|libvulkan|libnvmtl|CoreDisplay|Metal' > "$out/windowserver-images.txt"
    /usr/bin/sample "$wpid" 3 -file "$out/windowserver-sample.txt" > "$out/sample-status.txt" 2>&1
fi
console_user="$(/usr/bin/stat -f %Su /dev/console)"
if [[ "$console_user" != root && "$console_user" != loginwindow ]]; then
    /usr/bin/sudo -u "$console_user" /usr/bin/defaults read com.apple.universalaccess reduceTransparency > "$out/reduce-transparency.txt" 2>&1
    /usr/bin/sudo -u "$console_user" /usr/bin/defaults read com.apple.universalaccess reduceMotion > "$out/reduce-motion.txt" 2>&1
fi
exit 0
