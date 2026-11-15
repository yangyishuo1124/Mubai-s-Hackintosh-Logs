#!/bin/zsh
set -u
here="${0:A:h}"
[[ "$(uname -s)" == Darwin ]] || exit 1
out="$here/reports/gpu-display-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out" || exit 1
sw_vers > "$out/system.txt" 2>&1
mkdir -p "$out/crashes" 2>/dev/null || true
for f in /Library/Logs/DiagnosticReports/(WindowServer|ControlCenter|System*|panic*|Kernel*)*.(ips|panic)(Nom[1,8]) /Library/Logs/DiagnosticReports/*panic*(Nom[1,5]) /Library/Logs/DiagnosticReports/Retired/*panic*(Nom[1,5]) /Library/Logs/DiagnosticReports/Kernel*.panic(Nom[1,5]) /Library/Logs/DiagnosticReports/Retired/Kernel*.panic(Nom[1,5]) /Users/*/Library/Logs/DiagnosticReports/(WindowServer|ControlCenter|System*)*.ips(Nom[1,6]); do
    [[ -f "$f" ]] && cp -f "$f" "$out/crashes/" 2>/dev/null || true
done
ls -lt /Library/Logs/DiagnosticReports/ /Library/Logs/DiagnosticReports/Retired/ > "$out/diag-reports-list.txt" 2>&1 || true
nvram -p 2>/dev/null | awk '$1 ~ /(^|:)(aapl,panic-info|panic-info|xegfx-step|xegfx-step-prev|xegfx-accel|xegfx-prev)$/' > "$out/kernel-panic-nvram.txt" 2>&1 || true

# Deploy GPUBundles if missing
mkdir -p /Library/GPUBundles/nvmtl/aircache /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime 2>/dev/null || true
if [[ -d "$here/GPU/metal" ]]; then
    rm -f /Library/GPUBundles/NVMTLDriver 2>/dev/null || true
    cat > /Library/GPUBundles/NVMTLDriver.bundle/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>NVMTLDriver</string>
	<key>CFBundleIdentifier</key>
	<string>com.nullmoth.NVMTLDriver</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>NVMTLDriver</string>
	<key>CFBundlePackageType</key>
	<string>BNDL</string>
	<key>CFBundleShortVersionString</key>
	<string>0.1</string>
	<key>CFBundleVersion</key>
	<string>0.1</string>
</dict>
</plist>
EOF
    chmod 644 /Library/GPUBundles/NVMTLDriver.bundle/Contents/Info.plist 2>/dev/null || true
    cp -f "$here/GPU/metal/NVMTLDriver" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver 2>/dev/null || true
    chmod 755 /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver 2>/dev/null || true
    if [[ ! -f /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libLLVM.dylib ]]; then
        if [[ -f /Library/GPUBundles/air-runtime/libLLVM.dylib ]]; then
            mv -f /Library/GPUBundles/air-runtime/*.dylib /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/ 2>/dev/null || true
            rmdir /Library/GPUBundles/air-runtime 2>/dev/null || true
        elif [[ -d "$here/GPU/metal/air-runtime" ]]; then
            cp -f "$here/GPU/metal/air-runtime/libLLVM.dylib" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libLLVM.dylib 2>/dev/null || true
            cp -f "$here/GPU/metal/air-runtime/libzstd.1.dylib" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libzstd.1.dylib 2>/dev/null || true
        fi
        chmod 755 /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/*.dylib 2>/dev/null || true
    fi
    rm -rf /Library/GPUBundles/NVMTLDriver.bundle/Contents/_CodeSignature 2>/dev/null || true
    cp -f "$here/GPU/vulkan/libdrm.2.dylib" /Library/GPUBundles/nvmtl/libdrm.2.dylib 2>/dev/null || true
    cp -f "$here/GPU/vulkan/libvulkan.1.dylib" /Library/GPUBundles/nvmtl/libvulkan.dylib 2>/dev/null || true
    cp -f "$here/GPU/vulkan/libvulkan_intel.dylib" /Library/GPUBundles/nvmtl/libvulkan_intel.dylib 2>/dev/null || true
    cp -f "$here/GPU/metal/libnvmtl_translate.dylib" /Library/GPUBundles/nvmtl/libnvmtl_translate.dylib 2>/dev/null || true
    chmod 755 /Library/GPUBundles/nvmtl/*.dylib 2>/dev/null || true
    cat > /Library/GPUBundles/nvmtl/intel_icd.json << 'EOF'
{
    "file_format_version": "1.0.1",
    "ICD": {
        "library_path": "/Library/GPUBundles/nvmtl/libvulkan_intel.dylib",
        "api_version": "1.4.363",
        "library_arch": "64"
    }
}
EOF
    chmod 644 /Library/GPUBundles/nvmtl/intel_icd.json 2>/dev/null || true
fi
cat > /Library/GPUBundles/nvmtl-allow.txt << 'EOF'
WindowServer
EOF
chmod 644 /Library/GPUBundles/nvmtl-allow.txt 2>/dev/null || true

mkdir -p /Library/GPUBundles/nvmtl 2>/dev/null || true
cat > /Library/GPUBundles/nvmtl/nvrm610.conf << 'EOF'
NVMTL_XE_UNIFIED=1
EOF
chmod 644 /Library/GPUBundles/nvmtl/nvrm610.conf 2>/dev/null || true
if [[ -f "$here/GPU/vulkan/libvulkan_intel.dylib" ]] && ! cmp -s "$here/GPU/vulkan/libvulkan_intel.dylib" /Library/GPUBundles/nvmtl/libvulkan_intel.dylib 2>/dev/null; then
    cp -f "$here/GPU/vulkan/libvulkan_intel.dylib" /Library/GPUBundles/nvmtl/libvulkan_intel.dylib 2>/dev/null || true
    chmod 755 /Library/GPUBundles/nvmtl/libvulkan_intel.dylib 2>/dev/null || true
    codesign -f -s - /Library/GPUBundles/nvmtl/libvulkan_intel.dylib >/dev/null 2>&1 || true
fi
if ! codesign -v /Library/GPUBundles/NVMTLDriver.bundle >/dev/null 2>&1; then
    codesign -f -s - /Library/GPUBundles/nvmtl/*.dylib >/dev/null 2>&1 || true
    codesign -f -s - /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/*.dylib >/dev/null 2>&1 || true
    codesign -f -s - /Library/GPUBundles/NVMTLDriver.bundle >/dev/null 2>&1 || true
fi

# Automatic background Stage 7 acceleration claim & Framebuffer binding at boot
stage="$(sysctl -n debug.xegfx_stage 2>/dev/null || echo 0)"
if [[ "$stage" -lt 7 ]]; then
    sysctl debug.xegfx_env='compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1 compat.linuxkpi.xe_probe_skip_lrc_ggtt_remove=1' >/dev/null 2>&1 || true
    sysctl debug.xegfx_wdog=60 >/dev/null 2>&1 || true
    sysctl debug.xegfx_stage=7 >/dev/null 2>&1 || true
    sleep 1
fi
if ! ioreg -r -c NMXAccel | grep -q NMXAccel; then
    rm -rf /tmp/XeGfxAGDC.kext /tmp/XeGfxAccel.kext 2>/dev/null || true
    if [[ ! -d /Library/Extensions/XeGfxAGDC.kext || ! -d /Library/Extensions/XeGfxAccel.kext ]]; then
        rm -rf /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext 2>/dev/null || true
        cp -R "$here/GPU/kexts/XeGfxAGDC.kext" /Library/Extensions/XeGfxAGDC.kext 2>/dev/null || true
        cp -R "$here/GPU/kexts/XeGfxAccel.kext" /Library/Extensions/XeGfxAccel.kext 2>/dev/null || true
        chown -R root:wheel /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext 2>/dev/null || true
        chmod -R 755 /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext 2>/dev/null || true
    fi
    kextload /Library/Extensions/XeGfxAGDC.kext 2>/dev/null || true
    kextload /Library/Extensions/XeGfxAccel.kext 2>/dev/null || true
    sleep 1
fi
if [[ -d /Library/Extensions/NMIntelFB.kext ]]; then
    rm -rf /Library/Extensions/NMIntelFB.kext 2>/dev/null || true
fi
kextstat | grep -E 'XeGfx|NMIntel|NMX' > "$out/kextstat.txt" 2>&1 || true
ioreg -r -c XeGfxIntelFramebuffer -l > "$out/xeintelfb-ioreg.txt" 2>&1 || true
sysctl -w debug.xegfx_agdc=1 >/dev/null 2>&1 || true
sysctl -w debug.xegfx_agdc_k5=1 >/dev/null 2>&1 || true
sysctl -w debug.xegfx_agdc_fbcapex=1 >/dev/null 2>&1 || true
sysctl -w debug.xegfx_agdc_client_ack=1 >/dev/null 2>&1 || true
sleep 1
sysctl -w debug.nvaccel_iop=1 >/dev/null 2>&1 || true
sysctl -w debug.nvaccelfb=1 >/dev/null 2>&1 || true
sysctl -w debug.nvaccelfb=3 >/dev/null 2>&1 || true
sysctl -w debug.nvaccelfb=4 >/dev/null 2>&1 || true
sleep 1
defaults delete /Library/Preferences/com.apple.universalaccess reduceTransparency 2>/dev/null || true
defaults delete /Library/Preferences/com.apple.universalaccess reduceMotion 2>/dev/null || true
for uhome in /Users/*(N); do
    uname="${uhome:t}"
    [[ "$uname" == "Shared" || "$uname" == "Guest" ]] && continue
    sudo -u "$uname" defaults delete com.apple.universalaccess reduceTransparency 2>/dev/null || true
    sudo -u "$uname" defaults delete com.apple.universalaccess reduceMotion 2>/dev/null || true
done
killall -9 universalaccessd 2>/dev/null || true
if [[ -f "$here/ws-restart.request" ]]; then
    mv "$here/ws-restart.request" "$here/reports/ws-restart-$(date +%Y%m%d-%H%M%S)-$$.attempted" 2>/dev/null || rm -f "$here/ws-restart.request"
    /usr/bin/log stream --style compact --predicate 'process == "WindowServer" OR process == "loginwindow" OR sender == "XeGfxAccel" OR sender == "XeGfxAGDC" OR sender == "NMIntelFB" OR (sender == "kernel" AND (eventMessage CONTAINS "xegfx" OR eventMessage CONTAINS "NMIntelFB")) OR eventMessage CONTAINS "NVMTL"' > /tmp/ws-live.txt 2>&1 &
    stream_pid=$!
    sleep 1
    killall -9 WindowServer 2>/dev/null || true
    for i in {1..35}; do
        sleep 2
        cp -f /tmp/ws-live.txt "$out/ws-live.txt" 2>/dev/null || true
        if [[ "$i" -eq 4 || "$i" -eq 12 || "$i" -eq 24 || "$i" -eq 34 ]]; then
            /usr/sbin/sysctl debug.nmxaccel_headless debug.nvaccelfb debug.nvaccel_iop debug.nvaccel_iop_ok_h4 debug.nvaccel_iop_fail debug.nvaccel_pipe_init debug.nvaccel_pipe_validate debug.nvaccel_pipe_perform debug.nvaccel_pipe_complete debug.nvaccel_scanout_copies debug.nvaccel_scanout_last_us debug.nvaccel_scanout_max_us debug.nvaccel_scanout_sum_us debug.nvaccel_scanout_self debug.nvaccel_iop_copy_us debug.nvaccel_iop_copy_us_max debug.xegfx_agdc debug.xegfx_agdc_k5 debug.xegfx_agdc_fbcapex debug.xegfx_agdc_client_ack debug.xegfx_agdc_k5_asked debug.xegfx_agdc_k5_link debug.xegfx_agdc_k5_caps debug.xegfx_agdc_k5_why debug.xegfx_agdc_fbcapex_asked debug.xegfx_agdc_fbcapex_served debug.xegfx_agdc_client_set debug.xegfx_agdc_last_refused debug.xegfx_agdc_refused debug.xegfx_agdc_cmds > "$out/accel-after-restart.txt" 2>&1 || true
            dmesg > "$out/dmesg-after-restart.txt" 2>&1 || true
        fi
        if [[ "$i" -eq 10 ]]; then
            /usr/bin/sample WindowServer 3 -file "$out/ws-sample-early.txt" >/dev/null 2>&1 &
        fi
        if [[ "$i" -eq 28 ]]; then
            /bin/ps -axo pid,pcpu,pmem,state,etime,comm > "$out/ps-after-restart.txt" 2>&1 || true
            /usr/bin/sample WindowServer 3 -file "$out/ws-sample.txt" >/dev/null 2>&1 &
        fi
    done
    kill "$stream_pid" 2>/dev/null || true
    cp -f /tmp/ws-live.txt "$out/ws-live.txt" 2>/dev/null || true
fi

# Consume the request BEFORE installation: a failed attempt never loops on boot.
if [[ -f "$here/gpu-ui-install.request" && -f "$here/gpu-ui-install.command" ]]; then
    request="$here/reports/gpu-ui-request-$(date +%Y%m%d-%H%M%S)-$$.attempted"
    if mv "$here/gpu-ui-install.request" "$request"; then
        /bin/bash "$here/gpu-ui-install.command" install > "$out/ui-install-launch.txt" 2>&1
        print "installer exit=$? (see gpu-ui-install report)" >> "$out/ui-install-launch.txt"
    fi
fi
if [[ -f "$here/gpu-ui-rollback.request" && -f "$here/gpu-ui-install.command" ]]; then
    request="$here/reports/gpu-ui-rollback-$(date +%Y%m%d-%H%M%S)-$$.attempted"
    if mv "$here/gpu-ui-rollback.request" "$request"; then
        /bin/bash "$here/gpu-ui-install.command" rollback > "$out/ui-rollback-launch.txt" 2>&1
    fi
fi
if [[ -f "$here/gpu-ui-capture.command" ]]; then
    /bin/zsh "$here/gpu-ui-capture.command" "$out/ui-first" &
fi
/usr/sbin/sysctl debug.xegfx_progress debug.xegfx_running debug.xegfx_stage > "$out/status-first.txt" 2>&1 &
state_pid=$!
/usr/sbin/sysctl -b debug.xegfx_log > "$out/driver-first.txt" 2>&1 &
log_pid=$!
/bin/ps -axo pid,ppid,state,etime,comm > "$out/processes-first.txt" 2>&1
for n in {1..24}; do
    date '+%Y-%m-%d %H:%M:%S' >> "$out/heartbeat.txt"
    sleep 5
done
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
/usr/sbin/sysctl debug.nmxaccel_headless debug.nvaccelfb debug.nvaccel_heads_published debug.nvaccel_heads_registered debug.nvaccel_heads_piped debug.nvaccel_iop_ok_h4 debug.nvaccel_iop_fail debug.nvaccel_pipe_init debug.nvaccel_pipe_validate debug.nvaccel_pipe_perform > "$out/accel-sysctls.txt" 2>&1 || true
/usr/sbin/sysctl debug.xegfx_agdc debug.xegfx_agdc_cmds debug.xegfx_agdc_refused debug.xegfx_agdc_maxfb debug.xegfx_agdc_fbcapex_asked debug.xegfx_agdc_fbcapex_served > "$out/agdc-sysctls.txt" 2>&1 || true
/usr/bin/log show --last 3m --style compact --predicate 'process == "WindowServer" AND eventMessage CONTAINS "NVMTL"' > "$out/ws-nvmtl.txt" 2>&1 || true
if [[ -f "$here/gpu-ui-capture.command" ]]; then
    /bin/zsh "$here/gpu-ui-capture.command" "$out/ui-last" &
fi
print -r -- "$out"
