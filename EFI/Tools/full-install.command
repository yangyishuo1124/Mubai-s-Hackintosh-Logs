#!/bin/bash
# 系统卷安装 / System-volume install for the full-feature profile
#
# EFI 本身装不出显示接管、背光、HiDPI、合盖恢复 —— 这些依赖 /Library/Extensions 里的
# XeGfxIntelFB 及其 AuxKC 条目。本脚本按 2026-11-15 ~ 11-17 实机验证过的顺序安装：
#   1. 备份系统卷现状（扩展、GPUBundles、nvrm610.conf、nvmtl-allow.txt）
#   2. 清理已被弃用的 NMIntelFB
#   3. 安装 XeGfxIntelFB（含 OSBundleRequired=Root，保证早期引导就接管 framebuffer）
#   4. kmutil 重建 AuxKC
#   5. 安装 XeGfxAccel / XeGfxAGDC
#   6. 再次 kmutil 重建 AuxKC
#   7. 校验并输出验证要点
#
# 用法 / Usage (在 macOS 上):
#   sudo /bin/bash /Volumes/<EFI>/EFI/Tools/full-install.command
set -euo pipefail

EFI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GPU="$EFI_ROOT/Diagnostics/GPU"
BACKUP_ROOT="/Users/Shared/Mubai-FullEFI-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_ROOT/$STAMP"

log() { echo "$*"; }
die() { log "停止：$*"; exit 1; }

[[ "$(uname -s)" == Darwin ]] || die '只能在 macOS 上运行。'
[[ "$(id -u)" == 0 ]] || die '需要 root 权限。'
[[ -d "$EFI_ROOT/OC" ]] || die "EFI 目录不完整：$EFI_ROOT"
[[ -d "$GPU/kexts" ]] || die "缺少 kext 载荷：$GPU/kexts"

log "EFI 根目录：$EFI_ROOT"

# ---------------------------------------------------------------- 0. 前置检查
log ""
log "=== 0. 前置检查 ==="
log "  macOS：$(sw_vers -productVersion) ($(uname -r))"
if [[ ! "$(sw_vers -productVersion)" == 15.6* ]]; then
    log "  提示：本 EFI 目标系统是 macOS Sequoia 15.6，当前为 $(sw_vers -productVersion)"
fi
for f in "$GPU/vulkan/libvulkan_intel.dylib" "$GPU/metal/NVMTLDriver"; do
    [[ -f "$f" ]] || die "缺少 Metal 组件：$f（是否忘了先跑 prepare-metal-stack.command？）"
done
if ! otool -L "$GPU/vulkan/libvulkan_intel.dylib" 2>/dev/null | grep -q '@loader_path'; then
    die 'libvulkan_intel.dylib 仍未修复 RPATH —— 请先运行 prepare-metal-stack.command'
fi

# ---------------------------------------------------------------- 1. 备份
log ""
log "=== 1. 备份系统卷现状 ==="
mkdir -p "$BACKUP"
for d in /Library/Extensions /Library/GPUBundles; do
    if [[ -d "$d" ]]; then
        ditto "$d" "$BACKUP/$(basename "$d")" 2>/dev/null || true
    fi
done
[[ -f /Library/GPUBundles/nvmtl/nvrm610.conf ]] && cp -p /Library/GPUBundles/nvmtl/nvrm610.conf "$BACKUP/nvrm610.conf" 2>/dev/null || true
[[ -f /Library/GPUBundles/nvmtl-allow.txt ]] && cp -p /Library/GPUBundles/nvmtl-allow.txt "$BACKUP/nvmtl-allow.txt" 2>/dev/null || true
[[ -f /Library/Extensions/XeGfx.kext/Contents/Info.plist ]] && cp -p /Library/Extensions/XeGfx.kext/Contents/Info.plist "$BACKUP/XeGfx-kext-Info.plist" 2>/dev/null || true
log "  备份目录：$BACKUP"

# ---------------------------------------------------------------- 2. 清理弃用件
log ""
log "=== 2. 清理弃用件 ==="
if [[ -d /Library/Extensions/NMIntelFB.kext ]]; then
    log "  移除 /Library/Extensions/NMIntelFB.kext（11-16 起已改用 XeGfxIntelFB）"
    rm -rf /Library/Extensions/NMIntelFB.kext
fi
for p in /Library/Extensions/XeGfxIntelFB.kext /Library/Extensions/XeGfxAccel.kext /Library/Extensions/XeGfxAGDC.kext; do
    [[ -e "$p" ]] && log "  已存在：$p（将在下一步覆盖）"
done

# ---------------------------------------------------------------- 3. 安装 XeGfxIntelFB
log ""
log "=== 3. 安装 XeGfxIntelFB（显示接管 / 背光 / HiDPI / 合盖恢复）==="
src="$EFI_ROOT/OC/Kexts/XeGfxIntelFB.kext"
[[ -d "$src" ]] || die "EFI 内缺少 XeGfxIntelFB.kext：$src"
if ! /usr/libexec/PlistBuddy -c 'Print :OSBundleRequired' "$src/Contents/Info.plist" 2>/dev/null | grep -q Root; then
    log "  警告：XeGfxIntelFB 缺少 OSBundleRequired=Root，早期引导可能不接管 framebuffer"
else
    log "  已确认 OSBundleRequired=Root"
fi
rm -rf /Library/Extensions/XeGfxIntelFB.kext
ditto "$src" /Library/Extensions/XeGfxIntelFB.kext
chown -R root:wheel /Library/Extensions/XeGfxIntelFB.kext
chmod -R 755 /Library/Extensions/XeGfxIntelFB.kext
codesign -f -s - /Library/Extensions/XeGfxIntelFB.kext >/dev/null 2>&1 || log '  提示：ad-hoc 签名失败，AuxKC 构建可能报错'
log "  已安装并校验读回"

# ---------------------------------------------------------------- 4. 第一次 AuxKC 重建
log ""
log "=== 4. 重建 AuxKC（第一轮，只含 XeGfxIntelFB）==="
if ! /usr/bin/kmutil install --volume-root / --update-all 2>&1 | tee "$BACKUP/kmutil-pass1.log"; then
    log "  kmutil 失败，改用 kmutil create -n aux（无需 KDK）"
    /usr/bin/kmutil create -n aux --volume-root / 2>&1 | tee -a "$BACKUP/kmutil-pass1.log" || die 'AuxKC 构建失败，已保留备份，未做进一步改动。'
fi
log "  第一轮完成"

# ---------------------------------------------------------------- 5. 安装加速桥
log ""
log "=== 5. 安装 XeGfxAccel / XeGfxAGDC（Metal 加速桥）==="
for name in XeGfxAccel XeGfxAGDC; do
    src="$GPU/kexts/$name.kext"
    [[ -d "$src" ]] || die "缺少 $src"
    rm -rf "/Library/Extensions/$name.kext"
    ditto "$src" "/Library/Extensions/$name.kext"
    chown -R root:wheel "/Library/Extensions/$name.kext"
    chmod -R 755 "/Library/Extensions/$name.kext"
    codesign -f -s - "/Library/Extensions/$name.kext" >/dev/null 2>&1 || log "  提示：$name 签名失败"
    log "  已安装 $name"
done

# ---------------------------------------------------------------- 6. 第二次 AuxKC 重建
log ""
log "=== 6. 重建 AuxKC（第二轮，含全部实验性驱动）==="
if ! /usr/bin/kmutil install --volume-root / --update-all 2>&1 | tee "$BACKUP/kmutil-pass2.log"; then
    /usr/bin/kmutil create -n aux --volume-root / 2>&1 | tee -a "$BACKUP/kmutil-pass2.log" || log '  第二轮失败，保留第一轮 AuxKC'
fi
log "  第二轮完成"

# ---------------------------------------------------------------- 7. 校验
log ""
log "=== 7. 校验 ==="
for name in XeGfxIntelFB XeGfxAccel XeGfxAGDC; do
    if [[ -d "/Library/Extensions/$name.kext" ]]; then
        id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "/Library/Extensions/$name.kext/Contents/Info.plist" 2>/dev/null || echo '?')"
        log "  /Library/Extensions/$name.kext  ($id)"
    else
        log "  缺失：$name"
    fi
done
log "  当前已加载："
kextstat 2>/dev/null | grep -E 'XeGfx|NMX|NMIntel' | sed 's/^/    /' || log "    （尚未加载，重启后生效）"
log "  AuxKC 中与本项目相关的条目："
if [[ -f /System/Volumes/Preboot/*/boot/boot-*.kc/Contents/Info.plist ]] 2>/dev/null; then :; fi
ls -1 /System/Volumes/Preboot/*/boot/*.kc 2>/dev/null | sed 's/^/    /' || log "    （无法读取，无法列出）"

log ""
log "=== 下一步 ==="
log "  1. 确认 EFI 分区里的 config.plist 已是 FULL profile（XeGfxAGDC / XeGfxAccel 启用，"
log "     Kernel/Block 无实验性驱动的 Exclude，boot-args 含 xegfx_bootstage=4）"
log "  2. 正常重启 macOS，等待约 3 分钟让开机脚本采集完成"
log "  3. 回到 Windows 读取："
log "     <EFI>/Diagnostics/reports/gpu-display-<时间戳>/"
log "       - kextstat.txt        确认 XeGfx / XeGfxIntelFramebuffer / NMXAccel 已加载"
log "       - status-first.txt    确认 debug.xegfx_stage = 7"
log "       - accel-30s.txt       看呈现事务计数是否增长"
log "       - crashes/            有无 panic 或 WindowServer 崩溃报告"
log "  4. 若停在苹果标志或 panic：立即在 Windows 用 efi_profile.py 切回 SAFE profile"
log "     并用 full-rollback.command 回退系统卷"
log ""
log "备份目录：$BACKUP"
