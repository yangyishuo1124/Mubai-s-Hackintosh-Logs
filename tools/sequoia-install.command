#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
HERE="$PWD"
die() { echo "停止：$*"; exit 1; }
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || die '仅适用于本机 Intel macOS。'
[[ "$(sw_vers -productVersion)" == 15.6* && "$(uname -r)" == 24.* ]] || die '必须是 Sequoia 15.6 / Darwin 24。'
[[ "$EUID" == 0 ]] || exec /usr/bin/sudo /bin/bash "$HERE/安装.command"
/usr/bin/shasum -a 256 -c SHA256SUMS.txt || die '安装包文件校验失败，未修改系统。'
# This package is for a clean installation, not an automatic repair of Tahoe.
for p in '/Library/LaunchDaemons/org.mubai.gpu-capture.plist' '/Library/Extensions/XeGfx.kext' '/Library/Extensions/XeGfxAccel.kext' '/Library/Extensions/XeGfxAGDC.kext' '/Library/Extensions/XeGfxIntelFB.kext' '/Library/Extensions/NMIntelFB.kext' '/Library/GPUBundles/NVMTLDriver.bundle'; do
    [[ ! -e "$p" ]] || die "发现旧 GPU 安装残留：$p。请先保留现场，不能覆盖混装。"
done
UUID='6EB82BC1-3211-41D4-9ABE-5D9D78B7ACF3'
/usr/sbin/diskutil mount "$UUID" || die '没有找到本机原 EFI 分区；未选择其他磁盘。'
info="$(mktemp)"
/usr/sbin/diskutil info -plist "$UUID" > "$info"
EFI_MOUNT="$(/usr/libexec/PlistBuddy -c 'Print :MountPoint' "$info")"
kind="$(/usr/libexec/PlistBuddy -c 'Print :Content' "$info")"
rm "$info"
[[ "$kind" == EFI && "$EFI_MOUNT" == /Volumes/* ]] || die 'EFI 分区核验失败。'
TARGET="$EFI_MOUNT/EFI"
[[ -d "$TARGET" ]] || die 'EFI 目录缺失。'
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/Users/Shared/Mubai-Sequoia-backups/$STAMP"
mkdir -p "$BACKUP/EFI"
for n in OC Diagnostics Boot; do
    [[ ! -e "$TARGET/$n" ]] || /usr/bin/ditto "$TARGET/$n" "$BACKUP/EFI/$n"
done
for n in OC Diagnostics Boot; do
    if [[ -e "$TARGET/$n" ]]; then /usr/bin/diff -qr "$TARGET/$n" "$BACKUP/EFI/$n" >/dev/null || die '备份校验失败。'; fi
done
echo "$EFI_MOUNT" > "$BACKUP/efi-mount.txt"
printf '%s\n' "$UUID" > "$BACKUP/efi-uuid.txt"
# Restore exactly the three named OpenCore scopes; EFI/Microsoft is never touched.
restore_on_error() {
    echo '安装失败，正在恢复 EFI 备份。'
    for n in OC Diagnostics Boot; do
        rm -rf "$TARGET/$n"
        [[ ! -d "$BACKUP/EFI/$n" ]] || /usr/bin/ditto "$BACKUP/EFI/$n" "$TARGET/$n"
    done
}
trap restore_on_error ERR
for n in OC Diagnostics Boot; do
    rm -rf "$TARGET/$n"
    /usr/bin/ditto "$HERE/EFI/$n" "$TARGET/$n"
    /usr/bin/diff -qr "$HERE/EFI/$n" "$TARGET/$n" >/dev/null
done
sync
trap - ERR
echo "EFI 安装并校验完成；备份：$BACKUP"
echo '当前使用固件显示；Tahoe 专用 GPU 加速桥未安装。未修改系统驱动缓存或注册开机 GPU 服务。'
echo '请正常重启验证；安装成功不代表已经通过实机启动验证。'
read -r -p '按回车关闭。' _
