#!/bin/bash
set -euo pipefail
[ "$(id -u)" = 0 ] || exec sudo /bin/bash "$0" "$@"
HERE=$(cd "$(dirname "$0")" && pwd)
rm -rf /Library/Extensions/XeGfxIntelFB.kext
cp -R "$HERE/GPU/kexts/XeGfxIntelFB.kext" /Library/Extensions/
chown -R root:wheel /Library/Extensions/XeGfxIntelFB.kext
kmutil install --update-all --volume-root /
echo 'Done! Reboot macOS now.'
