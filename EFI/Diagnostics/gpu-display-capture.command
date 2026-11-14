#!/bin/zsh
set -u
here="${0:A:h}"
[[ "$(uname -s)" == Darwin ]] || exit 1
out="$here/reports/gpu-display-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out" || exit 1
sw_vers > "$out/system.txt" 2>&1

# Deploy GPUBundles if missing
mkdir -p /Library/GPUBundles/nvmtl/aircache 2>/dev/null || true
if [[ -d "$here/GPU/metal" ]]; then
    cp -f "$here/GPU/metal/NVMTLDriver" /Library/GPUBundles/NVMTLDriver 2>/dev/null || true
    chmod 755 /Library/GPUBundles/NVMTLDriver 2>/dev/null || true
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
    printf '*\n' > /Library/GPUBundles/nvmtl-allow.txt 2>/dev/null || true
    chmod 644 /Library/GPUBundles/nvmtl-allow.txt /Library/GPUBundles/nvmtl/intel_icd.json 2>/dev/null || true
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
    rm -rf /tmp/XeGfxAGDC.kext /tmp/XeGfxAccel.kext
    cp -R "$here/GPU/kexts/XeGfxAGDC.kext" /tmp/XeGfxAGDC.kext 2>/dev/null || true
    cp -R "$here/GPU/kexts/XeGfxAccel.kext" /tmp/XeGfxAccel.kext 2>/dev/null || true
    chown -R root:wheel /tmp/XeGfx*.kext 2>/dev/null || true
    chmod -R 755 /tmp/XeGfx*.kext 2>/dev/null || true
    kextload /tmp/XeGfxAGDC.kext 2>/dev/null || true
    kextload /tmp/XeGfxAccel.kext 2>/dev/null || true
    sleep 1
fi
sysctl -w debug.nvaccelfb=1 >/dev/null 2>&1 || true

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
print -r -- "$out"