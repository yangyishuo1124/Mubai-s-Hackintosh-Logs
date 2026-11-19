#!/bin/bash
# Metal 加速链路诊断采集 / Metal acceleration diagnostics collector
#
# 一次性把「Metal 到底卡在哪一环」的所有证据抓下来，写到 EFI 分区上，
# 这样在 Windows 侧可以直接读取，不用靠来回口述。
#
# 用法 / Usage:
#   sudo /bin/bash /Volumes/<ESP>/EFI/Diagnostics/collect-metal-diag.command
#
# 输出目录：<EFI>/Diagnostics/reports/metal-diag-<时间戳>/
set -u

here="$(cd "$(dirname "$0")" && pwd)"
efi_root="$(cd "$here/.." && pwd)"
gpu="$efi_root/Diagnostics/GPU"
stamp="$(date +%Y%m%d-%H%M%S)"
out="$here/reports/metal-diag-$stamp"

mkdir -p "$out" 2>/dev/null || { echo "无法创建 $out"; exit 1; }
exec > >(tee "$out/all.txt") 2>&1

echo "=============================================================="
echo " Metal 加速诊断 / Metal acceleration diagnostics"
echo " 时间: $(date)"
echo " 输出: $out"
echo "=============================================================="

section() { echo; echo "---------- $1 ----------"; }

# 打印 codesign 结果并保留真实退出码（不能用管道，否则拿到的是 sed 的状态）
show_codesign() {
    local f="$1" o rc
    o="$(codesign -v "$f" 2>&1)"; rc=$?
    [[ -n "$o" ]] && echo "$o" | sed 's/^/    /'
    if [[ $rc -eq 0 ]]; then echo "    签名有效"
    else echo "    **签名无效 (codesign exit=$rc)**"; fi
}

section "1. 系统环境"
echo "sw_vers:"; sw_vers 2>&1
echo "uname -a:"; uname -a 2>&1
echo "内核集合:"; ls -1 /System/Volumes/Preboot/*/boot/*.kc 2>/dev/null || echo "(读不到)"
ioreg -rd1 -c IOPlatformExpertDevice 2>/dev/null | grep -i '"time"' | head -2 | sed 's/^/  /'

section "2. 本机工具是否存在"
for t in install_name_tool codesign otool kmutil /usr/bin/python3; do
    if command -v "$t" >/dev/null 2>&1; then
        echo "  $t -> $(command -v "$t")"
    else
        echo "  $t -> **缺失**"
    fi
done
echo "/usr/bin/python3 直接运行:"
/usr/bin/python3 -c 'import sys; print("  python3 OK", sys.version.split()[0])' 2>&1 | head -3

section "3. 重跑 prepare-metal-stack.command（完整输出）"
echo "脚本: $efi_root/Tools/prepare-metal-stack.command"
/bin/bash "$efi_root/Tools/prepare-metal-stack.command" 2>&1
echo "prepare 退出码: $?"
echo "--- /tmp/prepare-metal-stack.log ---"
cat /tmp/prepare-metal-stack.log 2>&1 || echo "(没有日志)"

section "4. EFI 上 Metal 栈的 RPATH 与签名"
for f in "$gpu/vulkan/libvulkan_intel.dylib" "$gpu/vulkan/libvulkan.1.dylib" \
         "$gpu/vulkan/libdrm.2.dylib" "$gpu/metal/libnvmtl_translate.dylib" \
         "$gpu/metal/NVMTLDriver"; do
    echo "--- $(basename "$f") ---"
    [[ -f "$f" ]] || { echo "  (不存在)"; continue; }
    echo "  LC_RPATH:"; otool -l "$f" 2>/dev/null | grep -A2 LC_RPATH | sed 's/^/    /'
    echo "  install name:"; otool -D "$f" 2>/dev/null | tail -n +2 | sed 's/^/    /'
    echo "  依赖:"; otool -L "$f" 2>/dev/null | tail -n +2 | sed 's/^/    /'
    echo "  codesign:"; show_codesign "$f"
done
echo "--- 修复标记 ---"
ls -l "$gpu/.rpath-fixed" 2>&1 || echo "  (没有 .rpath-fixed 标记)"

section "5. 系统卷 /Library/Extensions 里的实验性 kext"
for k in XeGfxIntelFB XeGfxAccel XeGfxAGDC NMIntelFB; do
    p="/Library/Extensions/$k.kext"
    echo "--- $k ---"
    if [[ -d "$p" ]]; then
        echo "  存在: $p"
        echo -n "    id: "; /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$p/Contents/Info.plist" 2>&1
        echo -n "    OSBundleRequired: "
        /usr/libexec/PlistBuddy -c 'Print :OSBundleRequired' "$p/Contents/Info.plist" 2>&1 || echo "(无)"
        echo "    签名:"; show_codesign "$p"
    else
        echo "  **缺失**"
    fi
done

section "6. /Library/GPUBundles/nvmtl 的实际内容"
ls -l /Library/GPUBundles/nvmtl 2>&1 | sed 's/^/  /'
echo "--- intel_icd.json ---"
cat /Library/GPUBundles/nvmtl/intel_icd.json 2>&1 | sed 's/^/  /'
for f in /Library/GPUBundles/nvmtl/libvulkan_intel.dylib /Library/GPUBundles/nvmtl/libvulkan.dylib \
         /Library/GPUBundles/nvmtl/libdrm.2.dylib /Library/GPUBundles/nvmtl/libnvmtl_translate.dylib; do
    echo "--- $f ---"
    [[ -f "$f" ]] || { echo "  (不存在)"; continue; }
    echo "  LC_RPATH:"; otool -l "$f" 2>/dev/null | grep -A2 LC_RPATH | sed 's/^/    /'
    echo "  依赖:"; otool -L "$f" 2>/dev/null | tail -n +2 | sed 's/^/    /'
    echo "  codesign:"; show_codesign "$f"
done

section "7. 已加载的 kext"
echo "kextstat | grep -Ei 'xegfx|nmx|nmintel|watchthelight':"
kextstat 2>/dev/null | grep -Ei 'xegfx|nmx|nmintel|watchthelight' | sed 's/^/  /' || echo "  (无)"
echo "kmutil showloaded | grep -i watchthelight:"
kmutil showloaded 2>/dev/null | grep -i watchthelight | sed 's/^/  /' || echo "  (无或命令不可用)"

section "8. 加速桥运行时状态"
echo "ioreg 中 xegfx/nvaccelfb 相关属性:"
ioreg -l -w0 2>/dev/null | grep -Ei 'xegfx|nvaccelfb|xefb|agdc|nmx' | head -40 | sed 's/^/  /' || echo "  (无)"
echo "IOAccelDevice 节点:"
ioreg -c IOAccelDevice 2>/dev/null | head -20 | sed 's/^/  /'

section "9. WindowServer 拒绝名单与调试开关"
echo "/Library/GPUBundles/nvmtl-allow.txt:"; cat /Library/GPUBundles/nvmtl-allow.txt 2>&1 | sed 's/^/  /'
echo "/Library/Extensions/nvmtl-allow.txt:"; cat /Library/Extensions/nvmtl-allow.txt 2>&1 | sed 's/^/  /'
echo "nvrm610.conf:"; cat /Library/GPUBundles/nvmtl/nvrm610.conf 2>&1 | sed 's/^/  /'

section "10. 崩溃报告"
ls -lt /Library/Logs/DiagnosticReports/ 2>/dev/null | head -25 | sed 's/^/  /'
echo "--- WindowServer / panic 相关 ---"
ls -1 /Library/Logs/DiagnosticReports/ 2>/dev/null | grep -Ei 'windowserver|panic|kernel' | head -15 | sed 's/^/  /'

section "11. 开机采集服务"
echo "/Library/LaunchDaemons/org.mubai.gpu-capture.plist:"
ls -l /Library/LaunchDaemons/org.mubai.gpu-capture.plist 2>&1 | sed 's/^/  /'
echo "launchctl:"; launchctl print system/org.mubai.gpu-capture 2>&1 | head -12 | sed 's/^/  /'
echo "/Library/Logs/MubaiGPUCapture.log:"; tail -30 /Library/Logs/MubaiGPUCapture.log 2>&1 | sed 's/^/  /'
echo "/Library/Logs/MubaiGPUCapture-error.log:"; tail -20 /Library/Logs/MubaiGPUCapture-error.log 2>&1 | sed 's/^/  /'

section "12. 结束"
echo "诊断完成。输出目录：$out"
echo "回到 Windows 后可直接读取：Z:\EFI\Diagnostics\reports\metal-diag-$stamp\all.txt"
