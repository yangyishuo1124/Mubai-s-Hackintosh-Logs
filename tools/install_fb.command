#!/bin/zsh
set -e
SRC="/Volumes/SYSTEM/EFI/OC/Kexts/XeGfxIntelFB.kext"
DST="/Library/Extensions/XeGfxIntelFB.kext"
echo "Installing $SRC -> $DST ..."
sudo /bin/rm -rf "$DST"
sudo /bin/cp -R "$SRC" "$DST"
sudo /usr/sbin/chown -R root:wheel "$DST"
sudo /bin/chmod -R 755 "$DST"
echo "Rebuilding Auxiliary Kext Collection (AuxKC)..."
sudo /usr/bin/kmutil install --volume-root / --update-all
echo "Done! Please reboot into macOS."
