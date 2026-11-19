#!/bin/bash
# Metal 栈 RPATH 修复 / Fix @rpath in the Metal stack
#
# 为什么必须先跑这一步：
#   EFI/Diagnostics/GPU/vulkan/libvulkan_intel.dylib 等产物来自 CI 构建，**没有 LC_RPATH**，
#   且通过 @rpath/libdrm.2.dylib 等 @rpath 引用依赖。2026-11-17 19:26 的桌面接入失败就是这个
#   原因：@rpath 无法解析 -> Vulkan 初始化失败 -> CoreDisplay 断言 -> WindowServer SIGABRT 循环。
#   本脚本用 install_name_tool 补 @loader_path RPATH 并重新签名，然后**逐个验证**依赖可解析。
#
# 用法 / Usage:
#   sudo /bin/bash /Volumes/<EFI>/EFI/Tools/prepare-metal-stack.command
#   （脚本自动以自身位置推断 EFI 根目录）
set -euo pipefail

EFI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GPU="$EFI_ROOT/Diagnostics/GPU"
LOG="/tmp/prepare-metal-stack.log"
: > "$LOG"

log() { echo "$*" | tee -a "$LOG"; }
die() { log "停止：$*"; exit 1; }

[[ "$(uname -s)" == Darwin ]] || die '只能在 macOS 上运行。'
[[ -d "$GPU/vulkan" && -d "$GPU/metal" ]] || die "找不到 Metal 栈目录：$GPU"

command -v install_name_tool >/dev/null || die '缺少 install_name_tool'
command -v codesign >/dev/null || die '缺少 codesign'

log "EFI 根目录：$EFI_ROOT"
log "=== 修复前状态 ==="
for f in "$GPU/vulkan/libvulkan_intel.dylib" "$GPU/vulkan/libvulkan.1.dylib" \
         "$GPU/vulkan/libdrm.2.dylib" "$GPU/metal/libnvmtl_translate.dylib" "$GPU/metal/NVMTLDriver"; do
    [[ -f "$f" ]] || continue
    log "--- $(basename "$f") ---"
    otool -l "$f" 2>/dev/null | grep -A2 LC_RPATH | sed 's/^/    /' | tee -a "$LOG" || true
    otool -L "$f" 2>/dev/null | grep -E '@rpath|@loader_path' | sed 's/^/    /' | tee -a "$LOG" || true
done

# ---------------------------------------------------------------- RPATH 修复
log ""
log "=== 添加 @loader_path RPATH ==="
for f in "$GPU/vulkan/libvulkan_intel.dylib" "$GPU/vulkan/libvulkan.1.dylib" \
         "$GPU/vulkan/libdrm.2.dylib" "$GPU/metal/libnvmtl_translate.dylib"; do
    [[ -f "$f" ]] || continue
    if otool -l "$f" 2>/dev/null | grep -q 'LC_RPATH'; then
        log "  已有 RPATH，补充 @loader_path：$(basename "$f")"
        install_name_tool -add_rpath @loader_path "$f"
    else
        log "  新增 @loader_path：$(basename "$f")"
        install_name_tool -add_rpath @loader_path "$f"
    fi
done

# libvulkan.1.dylib 以 libvulkan.dylib 名称部署到 /Library/GPUBundles/nvmtl/，
# 其 install name 仍是 @rpath/libvulkan.1.dylib，会解析不到自己 —— 改成部署后的实际名称。
if [[ -f "$GPU/vulkan/libvulkan.1.dylib" ]]; then
    log "  重设 libvulkan.1.dylib 的 install name 为 @rpath/libvulkan.dylib"
    install_name_tool -id @rpath/libvulkan.dylib "$GPU/vulkan/libvulkan.1.dylib"
fi

# libdrm.2.dylib 在 CI 里被 build 成绝对路径依赖，部署到 nvmtl/ 后必须改成相对名。
if [[ -f "$GPU/vulkan/libdrm.2.dylib" ]]; then
    log "  重设 libdrm.2.dylib 的 install name 为 @rpath/libdrm.2.dylib"
    install_name_tool -id @rpath/libdrm.2.dylib "$GPU/vulkan/libdrm.2.dylib"
fi

log ""
log "=== 重新签名 ==="
for f in "$GPU/vulkan"/*.dylib "$GPU/metal"/*.dylib; do
    [[ -f "$f" ]] || continue
    codesign -f -s - "$f" >/dev/null 2>&1 || die "签名失败：$f"
    codesign -v "$f" >/dev/null 2>&1 || die "签名校验失败：$f"
    log "  已签名 $(basename "$f")"
done

# ---------------------------------------------------------------- 依赖验证
log ""
log "=== 依赖解析验证（@rpath 必须能在同目录找到对应文件）==="
fail=0
check() {
    local bin="$1"; shift
    [[ -f "$bin" ]] || return 0
    local dir; dir="$(cd "$(dirname "$bin")" && pwd)"
    local dep resolved
    while IFS= read -r dep; do
        [[ -n "$dep" ]] || continue
        resolved="${dep#@rpath/}"
        if [[ -f "$dir/$resolved" ]]; then
            log "  OK   $(basename "$bin") -> $dep  =>  $dir/$resolved"
        else
            log "  FAIL $(basename "$bin") -> $dep  =>  $dir/$resolved  不存在"
            fail=1
        fi
    done < <(otool -L "$bin" 2>/dev/null | tail -n +2 | awk '{print $1}' | grep -E '^@rpath/')
}
check "$GPU/vulkan/libvulkan_intel.dylib"
check "$GPU/vulkan/libvulkan.1.dylib"
check "$GPU/vulkan/libdrm.2.dylib"
check "$GPU/metal/libnvmtl_translate.dylib"

log ""
log "=== 空环境加载测试（不使用 DYLD_LIBRARY_PATH）==="
if [[ -f "$GPU/vulkan/libvulkan_intel.dylib" ]]; then
    if env -i /usr/bin/python3 -c "
import ctypes,sys
try:
    ctypes.CDLL(sys.argv[1])
    print('    ctypes 加载通过')
except OSError as e:
    print('    ctypes 加载失败:', e)
    sys.exit(1)
" "$GPU/vulkan/libvulkan_intel.dylib" 2>&1 | tee -a "$LOG"; then
        log "  空环境加载通过"
    else
        log "  空环境加载失败 —— 不要继续部署，回退到 SAFE profile"
        fail=1
    fi
fi

log ""
if [[ "$fail" -ne 0 ]]; then
    log "==> 仍有未解析依赖 / 加载失败。**不要部署这套 EFI**。"
    log "    请把 $LOG 带回 Windows 分析，或改用 SAFE profile。"
    exit 1
fi

# ---------------------------------------------------------------- 修复标记
# 写下标记文件，让 Windows 侧的部署脚本知道这个 EFI 分区上的 Metal 栈已经被修过，
# 避免下次重新部署 EFI 时把修好的 dylib 覆盖回未修复的版本（即 2026-11-17 19:26
# 那个 WindowServer SIGABRT 循环的元凶）。
MARKER="$GPU/.rpath-fixed"
{
    echo "fixed-at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "host: $(hostname)"
    for f in "$GPU/vulkan"/*.dylib "$GPU/metal"/*.dylib; do
        [[ -f "$f" ]] || continue
        echo "$(basename "$f"): $(shasum -a 256 "$f" | awk '{print $1}')"
    done
} > "$MARKER"
chmod 644 "$MARKER"
log "已写入修复标记：$MARKER"

log "==> Metal 栈 RPATH 修复完成，可以继续执行 full-install.command。"
log "    日志：$LOG"
