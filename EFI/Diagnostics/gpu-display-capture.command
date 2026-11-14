#!/bin/zsh
# Read-only GPU/display status capture; no stage requests or boot changes.
set -u
here="${0:A:h}"
[[ "$(uname -s)" == Darwin ]] || exit 1
out="$here/reports/gpu-display-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out" || exit 1
sw_vers > "$out/system.txt" 2>&1
# Do not wait for the driver log lock before saving independent state.
/usr/sbin/sysctl debug.xegfx_progress debug.xegfx_running debug.xegfx_stage > "$out/status-first.txt" 2>&1 &
state_pid=$!
/usr/sbin/sysctl -b debug.xegfx_log > "$out/driver-first.txt" 2>&1 &
log_pid=$!
/bin/ps -axo pid,ppid,state,etime,comm > "$out/processes-first.txt" 2>&1
for n in {1..24}; do
    date '+%Y-%m-%d %H:%M:%S' >> "$out/heartbeat.txt"
    sleep 5
done
# A still-blocked first read is evidence; avoid accumulating log readers.
if kill -0 "$log_pid" 2>/dev/null; then
    print 'first log reader still pending after 120 seconds' > "$out/log-pending.txt"
else
    /usr/sbin/sysctl -b debug.xegfx_log > "$out/driver-last.txt" 2>&1 &
fi
if kill -0 "$state_pid" 2>/dev/null; then
    print 'first status reader still pending after 120 seconds' > "$out/status-pending.txt"
else
    /usr/sbin/sysctl debug.xegfx_progress debug.xegfx_running debug.xegfx_stage > "$out/status-last.txt" 2>&1 &
fi
/bin/ps -axo pid,ppid,state,etime,comm > "$out/processes-last.txt" 2>&1
print -r -- "$out"
