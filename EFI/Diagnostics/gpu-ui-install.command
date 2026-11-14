#!/bin/bash
# One-shot framebuffer adoption. Based on upstream build/xeintelfb-pkg/install.sh.
# Does not restart WindowServer, change scanout gates, or reboot the machine.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
BASE='/Library/Application Support/MubaiGPUUI'
KC=/Library/KernelCollections/AuxiliaryKernelExtensions.kc
DEST=/Library/Extensions/XeGfxIntelFB.kext
MODE=${1:-install}
die() { echo "GPU UI: $*" >&2; exit 1; }
notify_user() {
    local user uid
    if user=$(/usr/bin/stat -f %Su /dev/console 2>/dev/null); then
        if [ "$user" != root ] && [ "$user" != loginwindow ]; then
            uid=$(/usr/bin/id -u "$user")
            /bin/launchctl asuser "$uid" /usr/bin/sudo -u "$user" /usr/bin/osascript \
                -e "display notification \"$1\" with title \"GPU 桌面修复\"" >/dev/null 2>&1 || true
        fi
    fi
}
[ "$(uname -s)" = Darwin ] || die 'macOS required'
[ "$(id -u)" = 0 ] || die 'run as root'
mkdir -p "$BASE" "$HERE/reports"
BK="$BASE/attempt-$(date +%Y%m%d-%H%M%S)-$$"
mkdir "$BK"
exec > >(tee "$HERE/reports/gpu-ui-install-$(date +%Y%m%d-%H%M%S).txt") 2>&1
echo "mode=$MODE backup=$BK"

if [ "$MODE" = rollback ]; then
    [ -f "$BASE/installed-backup" ] || die 'no completed installation to roll back'
    OLD=$(cat "$BASE/installed-backup")
    case "$OLD" in "$BASE"/attempt-*) ;; *) die 'invalid backup path' ;; esac
    [ -d "$OLD" ] || die 'backup missing'
    [ ! -e "$DEST" ] || mv "$DEST" "$BK/removed-XeGfxIntelFB.kext"
    [ ! -e "$OLD/previous-XeGfxIntelFB.kext" ] || ditto "$OLD/previous-XeGfxIntelFB.kext" "$DEST"
    if [ -f "$OLD/AuxiliaryKernelExtensions.kc" ]; then
        cp -p "$OLD/AuxiliaryKernelExtensions.kc" "$KC.mubai-restore"
        mv -f "$KC.mubai-restore" "$KC"
    elif [ -f "$OLD/no-aux-before" ]; then
        [ ! -e "$KC" ] || mv "$KC" "$BK/removed-AuxiliaryKernelExtensions.kc"
    else
        die 'backup does not describe original collection'
    fi
    nvram "boot-args=$(cat "$OLD/boot-args-before")"
    mv "$BASE/installed-backup" "$BK/rolled-back-pointer"
    echo 'ROLLED BACK. Restart normally to apply.'
    exit 0
fi
[ "$MODE" = install ] || die 'unknown mode'
[ ! -f "$BASE/installed-backup" ] || die 'already installed; inspect logs instead of reinstalling'
PAYLOAD="$HERE/GPU/kexts/XeGfxIntelFB.kext"
(cd "$HERE" && shasum -a 256 -c gpu-ui-payload.sha256) || die 'payload checksum mismatch'
plutil -lint "$PAYLOAD/Contents/Info.plist"
plutil -extract IOKitPersonalities.XeGfxIntelFramebuffer.IOPCIMatch raw -o - "$PAYLOAD/Contents/Info.plist" | grep -qi b0a08086 || die 'Panther Lake match missing'
ACTIVE_ARGS=$(sysctl -n kern.bootargs)
for flag in -xeintelfbnoedid -xeintelfbnohwc; do
    case " $ACTIVE_ARGS " in *" $flag "*) ;; *) die "safety boot argument not active: $flag" ;; esac
done
nvram boot-args > "$BK/boot-args-query" 2>&1 || die 'cannot read NVRAM boot arguments'
sed 's/^boot-args[[:space:]]*//' "$BK/boot-args-query" > "$BK/boot-args-before"
[ ! -e "$KC" ] || cp -p "$KC" "$BK/AuxiliaryKernelExtensions.kc"
[ -e "$KC" ] || touch "$BK/no-aux-before"
[ ! -e "$DEST" ] || ditto "$DEST" "$BK/previous-XeGfxIntelFB.kext"
NEW="$KC.mubai-ui-new"
[ ! -e "$NEW" ] || die 'unfinished collection exists; inspect before retry'
MUTATED=0
COMMITTED=0
restore_failed_install() {
    rc=$?
    if [ "$COMMITTED" = 0 ] && [ "$MUTATED" = 1 ]; then
        [ ! -e "$DEST" ] || mv "$DEST" "$BK/failed-XeGfxIntelFB.kext"
        [ ! -e "$BK/previous-XeGfxIntelFB.kext" ] || ditto "$BK/previous-XeGfxIntelFB.kext" "$DEST"
        nvram "boot-args=$(cat "$BK/boot-args-before")" || true
        echo 'Installation failed; old collection kept and extension restored. No automatic retry.'
        notify_user '安装未完成，已保留原显示驱动。请回 Windows 检查日志。'
    fi
    exit "$rc"
}
trap restore_failed_install EXIT
MUTATED=1
[ ! -e "$DEST" ] || mv "$DEST" "$BK/replaced-XeGfxIntelFB.kext"
ditto "$PAYLOAD" "$DEST"
chown -R root:wheel "$DEST"
chmod -R 755 "$DEST"
# The PTL PCI-match plist was adapted after the original build. Seal that
# installed copy again rather than hand an outdated resource seal to kmutil.
codesign --force --sign - "$DEST" > "$BK/codesign.log" 2>&1 || { cat "$BK/codesign.log"; die 'ad-hoc signing failed'; }
codesign --verify --deep --strict "$DEST" >> "$BK/codesign.log" 2>&1 || die 'installed signature invalid'
args=$(cat "$BK/boot-args-before")
for flag in -xeintelfbnoedid -xeintelfbnohwc; do
    case " $args " in *" $flag "*) ;; *) args="$args $flag" ;; esac
done
nvram "boot-args=$args"
KARG=(--allow-missing-kdk)
[ ! -f /System/Library/Kernels/kernel ] || KARG+=(--kernel /System/Library/Kernels/kernel)
/usr/bin/kmutil create -n aux --volume-root / "${KARG[@]}" \
    -B /System/Library/KernelCollections/BootKernelExtensions.kc \
    -S /System/Library/KernelCollections/SystemKernelExtensions.kc \
    --repository /Library/Extensions -A "$NEW" -z > "$BK/kmutil.log" 2>&1 || { cat "$BK/kmutil.log"; die 'collection build failed'; }
/usr/bin/kmutil inspect -a x86_64 -A "$NEW" > "$BK/new-inspect.txt" 2>&1 || die 'cannot inspect new collection'
grep -q 'org.watchthelight.XeGfxIntelFB' "$BK/new-inspect.txt" || die 'framebuffer missing from new collection'
# Preserve every identifier in the previous auxiliary collection.
ids() { awk '{for(i=1;i<=NF;i++) if($i ~ /^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)+$/) print $i}' "$1" | LC_ALL=C sort -u; }
if [ -f "$BK/AuxiliaryKernelExtensions.kc" ]; then
    /usr/bin/kmutil inspect -a x86_64 -A "$BK/AuxiliaryKernelExtensions.kc" > "$BK/old-inspect.txt" 2>&1 || die 'cannot inspect previous collection'
    ids "$BK/old-inspect.txt" > "$BK/old-ids.txt"
    ids "$BK/new-inspect.txt" > "$BK/new-ids.txt"
    LC_ALL=C comm -23 "$BK/old-ids.txt" "$BK/new-ids.txt" > "$BK/missing-ids.txt"
    [ ! -s "$BK/missing-ids.txt" ] || { cat "$BK/missing-ids.txt"; die 'previous extensions missing from new collection'; }
fi
printf '%s\n' "$BK" > "$BASE/installed-backup.new"
mv -f "$NEW" "$KC"
COMMITTED=1
mv -f "$BASE/installed-backup.new" "$BASE/installed-backup"
echo 'INSTALLED; REBOOT REQUIRED. Desktop acceleration is not yet verified.'
echo 'Framebuffer installed with EDID and hardware cursor MMIO disabled.'
echo 'No WindowServer restart and no scanout-gate change were performed.'
notify_user '安装完成。请正常重启一次 macOS，使桌面显示修复生效。'
