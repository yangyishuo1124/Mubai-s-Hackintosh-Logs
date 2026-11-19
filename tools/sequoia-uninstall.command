#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(uname -s)" == Darwin ]] || exit 1
[[ "$EUID" == 0 ]] || exec /usr/bin/sudo /bin/bash "$PWD/回退.command"
ROOT='/Users/Shared/Mubai-Sequoia-backups'
LATEST="$(find "$ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
[[ -n "$LATEST" && "$LATEST" == "$ROOT/"* && -f "$LATEST/efi-uuid.txt" ]] || { echo '没有找到有效备份。'; exit 1; }
UUID="$(cat "$LATEST/efi-uuid.txt")"
[[ "$UUID" == '6EB82BC1-3211-41D4-9ABE-5D9D78B7ACF3' ]] || exit 1
/usr/sbin/diskutil mount "$UUID"
INFO="$(mktemp)"
/usr/sbin/diskutil info -plist "$UUID" > "$INFO"
MOUNT="$(/usr/libexec/PlistBuddy -c 'Print :MountPoint' "$INFO")"
rm "$INFO"
[[ "$MOUNT" == /Volumes/* && -d "$MOUNT/EFI" ]] || exit 1
CURRENT="$ROOT/before-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$CURRENT"
for n in OC Diagnostics Boot; do
    [[ ! -e "$MOUNT/EFI/$n" ]] || /usr/bin/ditto "$MOUNT/EFI/$n" "$CURRENT/$n"
done
for n in OC Diagnostics Boot; do
    rm -rf "$MOUNT/EFI/$n"
    if [[ -d "$LATEST/EFI/$n" ]]; then
        /usr/bin/ditto "$LATEST/EFI/$n" "$MOUNT/EFI/$n"
        /usr/bin/diff -qr "$LATEST/EFI/$n" "$MOUNT/EFI/$n" >/dev/null
    fi
done
sync
echo "已恢复安装前 EFI：$LATEST"
read -r -p '按回车关闭。' _
