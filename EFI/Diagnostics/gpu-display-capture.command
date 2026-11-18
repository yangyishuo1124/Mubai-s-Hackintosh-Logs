#!/bin/zsh
# Apps-only GPU: deny WindowServer before late accelerator loading.
set -eu
here="${0:A:h}"
out="$here/reports/gpu-apps-only-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
exec > "$out/startup.txt" 2>&1
/bin/zsh "$here/gpu-windowserver-policy.command"
/bin/launchctl unsetenv NVMTL_ENABLE || true
wpid=''
for n in {1..60}; do
    wpid="$(/usr/bin/pgrep -x WindowServer | /usr/bin/head -n 1)"
    [[ -n "$wpid" ]] && break
    sleep 2
done
[[ -n "$wpid" ]] || { echo 'No WindowServer; refusing late GPU activation'; exit 1; }
if /bin/ps eww -p "$wpid" | /usr/bin/grep -q 'NVMTL_ENABLE='; then
    echo 'WindowServer inherited allow-list bypass. Restart normally after environment removal; not activating accelerator this boot.'
    exit 1
fi
plugin=''
for candidate in /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver /Library/GPUBundles/NVMTLDriver; do
    [[ ! -f "$candidate" ]] || plugin="$candidate"
done
[[ -n "$plugin" ]] || { echo 'Metal plugin missing'; exit 1; }
/usr/bin/strings "$plugin" | /usr/bin/grep -q 'denied by list' || { echo 'Cannot verify process-deny support'; exit 1; }
stage="$(/usr/sbin/sysctl -n debug.xegfx_stage)"
if [[ "$stage" -lt 7 ]]; then
    /usr/sbin/sysctl debug.xegfx_env='compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1 compat.linuxkpi.xe_probe_skip_lrc_ggtt_remove=1'
    /usr/sbin/sysctl debug.xegfx_wdog=60
    /usr/sbin/sysctl debug.xegfx_stage=7
fi
if ! /usr/sbin/ioreg -r -c NMXAccel | /usr/bin/grep -q NMXAccel; then
    base='/Library/Application Support/MubaiGPUAppsOnly'
    backup="$base/backup-$(date +%Y%m%d-%H%M%S)-$$"
    dest=/Library/Extensions/XeGfxAccel.kext
    mkdir -p "$backup"
    [[ ! -e "$dest" ]] || mv "$dest" "$backup/XeGfxAccel.kext"
    /usr/bin/ditto "$here/../OC/Kexts/XeGfxAccel.kext" "$dest"
    /usr/libexec/PlistBuddy -c 'Delete :OSBundleRequired' "$dest/Contents/Info.plist" 2>/dev/null || true
    chown -R root:wheel "$dest"
    chmod -R 755 "$dest"
    /usr/bin/codesign -f -s - "$dest"
    /usr/bin/kmutil load -p "$dest"
fi
# No AGDC, framebuffer adoption, nvaccelfb writes, or WindowServer restart.
/usr/sbin/ioreg -r -c NMXAccel -l -w0 > "$out/accelerator.txt"
/usr/bin/kmutil showloaded > "$out/kexts.txt"
/usr/sbin/sysctl kern.bootargs debug.xegfx_stage debug.nvaccelfb > "$out/status.txt" 2>&1 || true
/usr/sbin/sysctl -b debug.xegfx_log > "$out/driver.txt" 2>&1 || true
echo 'Apps-only GPU activation attempted; confirm NMXAccel and app Metal tests in reports.'
