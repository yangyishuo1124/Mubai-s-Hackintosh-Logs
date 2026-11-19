#!/bin/bash
# 系统卷回退 / System-volume rollback for the full-feature profile
#
# 恢复 full-install.command 备份的 /Library/Extensions 与 /Library/GPUBundles，
# 并重建 AuxKC。用于「停在苹果标志 / 早期 boot panic / 桌面无显示」时回退。
#
# 用法 / Usage (在 macOS 上):
#   sudo /bin/bash /Volumes/<EFI>/EFI/Tools/full-rollback.command            # 最近一次备份
#   sudo /bin/bash /Volumes/<EFI>/EFI/Tools/full-rollback.command 20261118-102511
set -euo pipefail

BACKUP_ROOT="/Users/Shared/Mubai-FullEFI-backups"

log() { echo "$*"; }
die() { log "停止：$*"; exit 1; }

[[ "$(uname -s)" == Darwin ]] || die '只能在 macOS 上运行。'
[[ "$(id -u)" == 0 ]] || die '需要 root 权限。'
[[ -d "$BACKUP_ROOT" ]] || die "没有备份目录：$BACKUP_ROOT"

if [[ $# -ge 1 ]]; then
    BACKUP="$BACKUP_ROOT/$1"
else
    BACKUP="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
fi
[[ -n "$BACKUP" && -d "$BACKUP" ]] || die '找不到有效备份。'
[[ "$BACKUP" == "$BACKUP_ROOT/"* ]] || die '备份路径越界。'
log "回退源：$BACKUP"

log ""
log "=== 1. 移除实验性 GPU 扩展 ==="
for name in XeGfxIntelFB XeGfxAccel XeGfxAGDC NMIntelFB; do
    if [[ -d "/Library/Extensions/$name.kext" ]]; then
        rm -rf "/Library/Extensions/$name.kext"
        log "  已移除 $name.kext"
    else
        log "  不存在：$name.kext"
    fi
done

log ""
log "=== 2. 恢复备份 ==="
if [[ -d "$BACKUP/Extensions" ]]; then
    for name in "$BACKUP/Extensions"/*.kext; do
        [[ -d "$name" ]] || continue
        base="$(basename "$name")"
        rm -rf "/Library/Extensions/$base"
        ditto "$name" "/Library/Extensions/$base"
        chown -R root:wheel "/Library/Extensions/$base"
        log "  已恢复 $base"
    done
fi
if [[ -d "$BACKUP/GPUBundles" ]]; then
    rm -rf /Library/GPUBundles
    ditto "$BACKUP/GPUBundles" /Library/GPUBundles
    log '  已恢复 /Library/GPUBundles'
fi
[[ -f "$BACKUP/nvrm610.conf" ]] && cp -p "$BACKUP/nvrm610.conf" /Library/GPUBundles/nvmtl/nvrm610.conf 2>/dev/null || true
[[ -f "$BACKUP/nvmtl-allow.txt" ]] && cp -p "$BACKUP/nvmtl-allow.txt" /Library/GPUBundles/nvmtl-allow.txt 2>/dev/null || true

log ""
log "=== 3. 重建 AuxKC ==="
/usr/bin/kmutil install --volume-root / --update-all 2>&1 | tail -n 20 || \
    /usr/bin/kmutil create -n aux --volume-root / 2>&1 | tail -n 20 || \
    log '  提示：AuxKC 重建失败，重启后由 kextd 自动刷新'

log ""
log "=== 4. 结果 ==="
kextstat 2>/dev/null | grep -E 'XeGfx|NMX|NMIntel' | sed 's/^/  /' || log '  （无相关 kext 已加载）'
log ""
log "回退完成。**EFI 侧也要切回 SAFE profile**，否则引导期仍会注入加速桥："
log "  Windows:  python tools\\efi_profile.py --profile safe --efi <挂载的 EFI 路径>"
log "  macOS  :  python3 <EFI>/EFI/Tools/efi_profile.py --profile safe --efi <EFI 路径>"
