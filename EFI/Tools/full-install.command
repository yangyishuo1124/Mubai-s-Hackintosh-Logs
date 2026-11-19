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
#   sudo /bin/bash /Volumes/<EFI>/EFI/Tools/full-install.command            # = --stage all
#   sudo /bin/bash .../full-install.command --stage display                # 只装 XeGfxIntelFB
#   sudo /bin/bash .../full-install.command --stage accel                 # 只装 Accel/AGDC
#
# 分阶段的意义：2026-11-18 的早期 boot panic 发生在 XeGfxIntelFB 接管 framebuffer
# （displayModeDidChange 路径）且 XeGfxAccel 同时被加载时。两者的组合没在实机验证过，
# 所以默认推荐分两步：先只装显示接管并验证开机，再装 Metal 加速桥。
set -euo pipefail

STAGE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage=*) STAGE="${1#--stage=}" ;;
        --stage)
            shift
            [[ $# -gt 0 ]] || { echo "--stage 需要一个值"; exit 2; }
            STAGE="$1" ;;
        -h|--help)
            echo "用法: full-install.command [--stage display|accel|all]"
            echo "  display : 只安装 XeGfxIntelFB（显示接管/背光/HiDPI/合盖），重建一次 AuxKC"
            echo "  accel   : 只安装 XeGfxAccel / XeGfxAGDC（Metal 加速桥），重建一次 AuxKC"
            echo "  all     : 两步一起做（默认，不推荐用于首次验证）"
            exit 0 ;;
        *) echo "未知参数：$1"; exit 2 ;;
    esac
    shift
done
case "$STAGE" in display|accel|all) ;; *) echo "非法 stage：$STAGE"; exit 2 ;; esac

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
    log "  提示：本 EFI 的实机验证基线是 macOS Sequoia 15.6 (24G84)，当前为 $(sw_vers -productVersion)"
    log "        15.x 同属 Darwin 24 分支，配置层面无需改动；但 15.7+ 尚未实机验证"
fi
if [[ "$STAGE" == "accel" || "$STAGE" == "all" ]]; then
    for f in "$GPU/vulkan/libvulkan_intel.dylib" "$GPU/metal/NVMTLDriver"; do
        [[ -f "$f" ]] || die "缺少 Metal 组件：$f（是否忘了先跑 prepare-metal-stack.command？）"
    done
    # RPATH 必须查 LC_RPATH（otool -l），不能查 otool -L 的依赖列表：
    # prepare-metal-stack.command 是用 install_name_tool -add_rpath @loader_path 加的
    # LC_RPATH，它不会出现在 otool -L 的输出里 —— 用 otool -L 检查会**永远**判失败。
    for f in "$GPU/vulkan/libvulkan_intel.dylib" "$GPU/vulkan/libvulkan.1.dylib" \
             "$GPU/vulkan/libdrm.2.dylib" "$GPU/metal/libnvmtl_translate.dylib"; do
        [[ -f "$f" ]] || continue
        rpath_text="$(otool -l "$f" 2>/dev/null | grep -A3 'LC_RPATH' || true)"
        if [[ "$rpath_text" != *@loader_path* ]]; then
            die "$(basename "$f") 缺少 @loader_path RPATH —— 请先运行 prepare-metal-stack.command"
        fi
        log "  RPATH OK：$(basename "$f")"
    done
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
if [[ "$STAGE" == "accel" ]] && [[ ! -d /Library/Extensions/XeGfxIntelFB.kext ]]; then
    log "  **警告**：/Library/Extensions/XeGfxIntelFB.kext 不存在。"
    log "     加速桥依赖显示接管提供 framebuffer，建议先跑一次 --stage display 再重启验证。"
fi

# ---------------------------------------------------------------- 3. 安装 XeGfxIntelFB
if [[ "$STAGE" == "display" || "$STAGE" == "all" ]]; then
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
fi

# ---------------------------------------------------------------- 5. 安装加速桥
if [[ "$STAGE" == "accel" || "$STAGE" == "all" ]]; then
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
fi

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
if [[ "$STAGE" == "display" ]]; then
    log "  本轮只装了显示接管。重启后验证："
    log "    - 屏幕由 XeGfxIntelFramebuffer 接管（非固件显示）"
    log "    - 背光可调、亮度 NVRAM 记忆生效、合盖息屏 / 开盖恢复"
    log "    - 系统设置可切 1280x800 HiDPI 与 2560x1600 1x @165Hz"
    log "  确认这些都正常后，再执行："
    log "    sudo bash <EFI>/EFI/Tools/full-install.command --stage accel"
    log "  装 Metal 加速桥并重建 AuxKC，然后再重启。"
    log "  **这一步存在 2026-11-18 记录过的早期 boot panic 风险**"
    log "  （framebuffer displayModeDidChange 路径），务必先确认显示接管稳定。"
elif [[ "$STAGE" == "accel" ]]; then
    log "  本轮装了 Metal 加速桥。重启后验证："
    log "    - kextstat 中出现 NMXAccel"
    log "    - debug.xegfx_stage = 7，呈现事务计数持续增长"
    log "    - 桌面合成走 Metal，窗口无毛玻璃变黑 / 缺圆角 / 头像菱形"
else
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
fi
log ""
log "备份目录：$BACKUP"
