#!/bin/zsh
set -e
if [ -d "/Library/Extensions/XeGfxIntelFB.kext" ]; then
  echo "Removing stale /Library/Extensions/XeGfxIntelFB.kext so OpenCore EFI kext is used..."
  sudo /bin/rm -rf /Library/Extensions/XeGfxIntelFB.kext
  echo "Rebuilding Auxiliary Kext Collection (AuxKC)..."
  sudo /usr/bin/kmutil install --volume-root / --update-all
  echo "Done! Please reboot into macOS."
else
  echo "/Library/Extensions/XeGfxIntelFB.kext is already absent."
fi
