#!/bin/zsh
set -euo pipefail
base="${0:A:h}"
[[ $EUID -eq 0 ]] || { printf '%s\n' '请使用 sudo 运行此脚本 / Run with sudo'; exit 1; }
out="$base/reports/gpu-probe-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$base/reports"
exec > >(tee "$out") 2>&1
printf '%s\n' 'Stage-5/6/7 加速声明 + 用户态 /dev/dri/renderD128 DRM/Xe UAPI + Mesa ANV Vulkan + Metal (NVMTLDriver) 端到端实测；保持 GOP 显示。'
printf '%s\n' 'Stage-5/6/7 acceleration claim + userspace DRM/Xe UAPI + Mesa ANV Vulkan + Metal (NVMTLDriver) end-to-end verification; GOP display retained.'
cd "$base/GPU"
shasum -a 256 -c SHA256.txt
if ! sysctl -n debug.xegfx_stage >/dev/null 2>&1; then
    printf '%s\n' '开机驱动尚未启动，采集后停止，不再尝试手动加载。'
    printf '%s\n' 'Boot driver is not active; collecting without manual loading.'
    zsh "$base/collect.command"
    exit 1
fi

policy="$(ioreg -r -c XeGfxResident -l)"
if [[ "$policy" != *'"XeGfxProbePolicy" = "ptl-worker-heartbeat-v24"'* ]]; then
    printf '%s\n' '当前加载的仍是旧版驱动，停止探测，请重启后再运行。'
    printf '%s\n' 'Loaded driver lacks the stage-4 policy; reboot before probing.'
    zsh "$base/collect.command"
    exit 1
fi
stage="$(sysctl -n debug.xegfx_stage)"
[[ "$stage" == <0-7> ]] || { printf '%s\n' '已有其他阶段运行，本脚本停止 / Unexpected existing stage; stopping'; exit 1; }

sysctl debug.xegfx_trace=0
if [[ "$stage" -lt 7 ]]; then
    printf '%s\n' "当前 Stage=$stage，触发 Stage 5+6+7（xg_exec_check + xg_store_check + xg_accel_claim）..."
    sysctl debug.xegfx_env='compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1 compat.linuxkpi.xe_probe_skip_lrc_ggtt_remove=1'
    sysctl debug.xegfx_wdog=60
    progress_out="${out%.txt}-progress.txt"
    stage_out="${out%.txt}-stage.txt"
    previous="$(sysctl -b debug.xegfx_log)"
    printf '%s\n' "$previous"
    last_progress="$(sysctl -n debug.xegfx_progress)"
    printf '%s\n' "[progress=$last_progress] stage 7 request follows"
    printf '%s\n' "$(date '+%Y-%m-%d %H:%M:%S') progress=$last_progress" >> "$progress_out"
    sysctl debug.xegfx_stage=7 > "$stage_out" 2>&1 &
    stage_pid=$!
    while true; do
        if snapshot="$(sysctl -b debug.xegfx_log 2>&1)"; then
            if [[ "$snapshot" != "$previous" ]]; then
                if [[ "$snapshot" == "$previous"* ]]; then
                    printf '%s' "${snapshot#"$previous"}"
                else
                    printf '%s\n' '[driver log rotated; current snapshot follows]'
                    printf '%s\n' "$snapshot"
                fi
                previous="$snapshot"
            fi
        else
            printf '%s\n' "[log read failed] $snapshot"
            break
        fi
        if value="$(sysctl -n debug.xegfx_progress 2>&1)"; then
            if [[ "$value" != "$last_progress" ]]; then
                printf '%s\n' "[progress=$value]"
                printf '%s\n' "$(date '+%Y-%m-%d %H:%M:%S') progress=$value" >> "$progress_out"
                last_progress="$value"
            fi
        else
            printf '%s\n' "[progress read failed] $value"
            break
        fi
        kill -0 "$stage_pid" 2>/dev/null || break
        sleep 0.1
    done
    cat "$stage_out"
    wait "$stage_pid"
else
    printf '%s\n' "当前 Stage=$stage 已处于激活状态，直接进入用户态与 Metal 验证。"
fi

sysctl debug.xegfx_stage
printf '%s\n' '阶段结果数组（索引对应阶段号）/ Signed results indexed by stage:'
sysctl -b debug.xegfx_results | od -An -v -t d4
sysctl -b debug.xegfx_log

printf '%s\n' '=== [Phase 1] 用户态 /dev/dri/renderD128 DRM/Xe UAPI 实测 (xe-uapi-probe) ==='
ls -la /dev/dri /dev/dri/* 2>&1 || true
if [[ -f "$base/GPU/xe-uapi-probe" ]]; then
    cp -f "$base/GPU/xe-uapi-probe" /tmp/xe-uapi-probe
    chmod +x /tmp/xe-uapi-probe
    /tmp/xe-uapi-probe || printf '%s\n' "[xe-uapi-probe exited with status $?]"
fi

printf '%s\n' '=== [Phase 2] 用户态 libdrm + Mesa ANV (xe backend) 离屏 Vulkan 实测 ==='
if [[ -d "$base/GPU/vulkan" ]]; then
    rm -rf /tmp/xe-vk
    mkdir -p /tmp/xe-vk
    cp -f "$base/GPU/vulkan/"* /tmp/xe-vk/
    ln -sf /tmp/xe-vk/libvulkan.1.dylib /tmp/xe-vk/libvulkan.dylib
    ln -sf /tmp/xe-vk/libdrm.2.dylib /tmp/xe-vk/libdrm.dylib
    chmod +x /tmp/xe-vk/drmlist /tmp/xe-vk/vkprobe /tmp/xe-vk/vkcoh /tmp/xe-vk/vkdraw /tmp/xe-vk/*.dylib

    mkdir -p /Users/runner/src/xe-userland/prefix 2>/dev/null || true
    ln -sfn /tmp/xe-vk /Users/runner/src/xe-userland/prefix/lib 2>/dev/null || true

    cat > /tmp/xe-vk/intel_icd.x86_64.json << 'EOF'
{
    "ICD": {
        "api_version": "1.4.363",
        "library_arch": "64",
        "library_path": "/tmp/xe-vk/libvulkan_intel.dylib"
    },
    "file_format_version": "1.0.1"
}
EOF

    printf '%s\n' '=== [2.1] drmlist (libdrm drmGetDevices2) ==='
    env DYLD_LIBRARY_PATH=/tmp/xe-vk /tmp/xe-vk/drmlist || printf '%s\n' "[drmlist exited with status $?]"

    printf '%s\n' '=== [2.2] vkprobe (Mesa ANV xe PhysicalDevice & QueueFamilies) ==='
    if ! env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json /tmp/xe-vk/vkprobe; then
        printf '%s\n' '[vkprobe failed; re-running with debug logging enabled]'
        env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json VK_LOADER_DEBUG=error,warn,driver MESA_LOG_LEVEL=debug INTEL_DEBUG=bat /tmp/xe-vk/vkprobe || true
    fi

    printf '%s\n' '=== [2.3] vkcoh (Mesa ANV xe Memory Coherency & Compute/Transfer) ==='
    if ! env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json /tmp/xe-vk/vkcoh; then
        printf '%s\n' '[vkcoh failed; re-running with debug logging enabled]'
        env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json MESA_LOG_LEVEL=debug INTEL_DEBUG=bat /tmp/xe-vk/vkcoh || true
    fi

    printf '%s\n' '=== [2.4] vkdraw (Mesa ANV xe Offscreen Graphics Pipeline & RenderPass) ==='
    if ! (cd /tmp && env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json /tmp/xe-vk/vkdraw); then
        printf '%s\n' '[vkdraw failed; re-running with debug logging enabled]'
        (cd /tmp && env DYLD_LIBRARY_PATH=/tmp/xe-vk VK_DRIVER_FILES=/tmp/xe-vk/intel_icd.x86_64.json VK_ICD_FILENAMES=/tmp/xe-vk/intel_icd.x86_64.json MESA_LOG_LEVEL=debug INTEL_DEBUG=bat /tmp/xe-vk/vkdraw) || true
    fi
fi

printf '%s\n' '=== [Phase 3] 部署 Metal 驱动插件并实测 Metal Compute & Draw (mtlprobe) ==='
mkdir -p /Library/GPUBundles/nvmtl/aircache /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime
rm -f /Library/GPUBundles/NVMTLDriver
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
chmod 644 /Library/GPUBundles/NVMTLDriver.bundle/Contents/Info.plist
cp -f "$base/GPU/metal/NVMTLDriver" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver
chmod 755 /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver
if [[ ! -f /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libLLVM.dylib ]]; then
    if [[ -f /Library/GPUBundles/air-runtime/libLLVM.dylib ]]; then
        mv -f /Library/GPUBundles/air-runtime/*.dylib /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/ 2>/dev/null || true
        rmdir /Library/GPUBundles/air-runtime 2>/dev/null || true
    elif [[ -d "$base/GPU/metal/air-runtime" ]]; then
        cp -f "$base/GPU/metal/air-runtime/libLLVM.dylib" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libLLVM.dylib
        cp -f "$base/GPU/metal/air-runtime/libzstd.1.dylib" /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/libzstd.1.dylib
    fi
    chmod 755 /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/air-runtime/*.dylib 2>/dev/null || true
fi

cp -f "$base/GPU/vulkan/libdrm.2.dylib" /Library/GPUBundles/nvmtl/libdrm.2.dylib
cp -f "$base/GPU/vulkan/libvulkan.1.dylib" /Library/GPUBundles/nvmtl/libvulkan.dylib
cp -f "$base/GPU/vulkan/libvulkan_intel.dylib" /Library/GPUBundles/nvmtl/libvulkan_intel.dylib
cp -f "$base/GPU/metal/libnvmtl_translate.dylib" /Library/GPUBundles/nvmtl/libnvmtl_translate.dylib
chmod 755 /Library/GPUBundles/nvmtl/*.dylib

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

printf '*\n' > /Library/GPUBundles/nvmtl-allow.txt
chmod 644 /Library/GPUBundles/nvmtl-allow.txt /Library/GPUBundles/nvmtl/intel_icd.json

printf '%s\n' '--- 检查与加载 NMXAccel ---'
if ! ioreg -r -c NMXAccel | grep -q NMXAccel; then
    printf '%s\n' '安装并加载 NMXAccel 与 XeGfxAGDC 驱动到 /Library/Extensions/ ...'
    rm -rf /tmp/XeGfxAGDC.kext /tmp/XeGfxAccel.kext
    rm -rf /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext
    cp -R "$base/GPU/kexts/XeGfxAGDC.kext" /Library/Extensions/XeGfxAGDC.kext
    cp -R "$base/GPU/kexts/XeGfxAccel.kext" /Library/Extensions/XeGfxAccel.kext
    chown -R root:wheel /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext
    chmod -R 755 /Library/Extensions/XeGfxAGDC.kext /Library/Extensions/XeGfxAccel.kext
    kextload /Library/Extensions/XeGfxAGDC.kext 2>&1 || true
    kextload /Library/Extensions/XeGfxAccel.kext 2>&1 || true
    sleep 1
    if ! ioreg -r -c NMXAccel | grep -q NMXAccel; then
        printf '%s\n' '[提示] 已将驱动安装到持久化目录 /Library/Extensions/，如果上方提示 requires a reboot，请重启电脑以使 AuxKC 生效！'
    fi
fi

printf '%s\n' '--- NMXAccel 状态检查 ---'
ioreg -r -c NMXAccel -l || printf '%s\n' '[NMXAccel not matched yet]'

printf '%s\n' '=== 注册 Framebuffer 呈现管道到 NMXAccel ==='
sysctl -w debug.nvaccelfb=1 2>&1 || true

if [[ -f "$base/GPU/metal/mtlprobe" ]]; then
    cp -f "$base/GPU/metal/mtlprobe" /tmp/mtlprobe
    chmod +x /tmp/mtlprobe
    rm -f /tmp/nvmtl.log

    printf '%s\n' '=== [3.1] mtlprobe (内置测试模式 NM_TEST_PLUGIN) ==='
    env NM_TEST_PLUGIN=/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver \
        NVMTL_LOG_PATH=/tmp/nvmtl.log \
        VK_LOADER_DEBUG=all \
        VK_DRIVER_FILES=/Library/GPUBundles/nvmtl/intel_icd.json \
        VK_ICD_FILENAMES=/Library/GPUBundles/nvmtl/intel_icd.json \
        /tmp/mtlprobe || printf '%s\n' "[mtlprobe test plugin exited with status $?]"

    printf '%s\n' '=== [3.2] mtlprobe (系统级 Metal 枚举模式) ==='
    env NVMTL_LOG_PATH=/tmp/nvmtl.log \
        VK_LOADER_DEBUG=all \
        VK_DRIVER_FILES=/Library/GPUBundles/nvmtl/intel_icd.json \
        VK_ICD_FILENAMES=/Library/GPUBundles/nvmtl/intel_icd.json \
        /tmp/mtlprobe || printf '%s\n' "[mtlprobe system copy exited with status $?]"

    if [[ -f /tmp/nvmtl.log ]]; then
        printf '%s\n' '=== /tmp/nvmtl.log 输出 ==='
        cat /tmp/nvmtl.log || true
    fi
fi

printf '%s\n' '=== Metal & Vulkan 实测结束后的驱动日志 ==='
sysctl -b debug.xegfx_log
printf '%s\n' 'Boundary: stage 7 (xg_accel_claim) + userspace xe-uapi-probe + Mesa ANV Vulkan + Metal NVMTLDriver.'
zsh "$base/collect.command"
printf '%s\n' '探测结束。驱动由 EFI 配置开机加载。 / Probe finished; EFI controls boot loading.'