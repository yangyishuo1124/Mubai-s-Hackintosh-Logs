#!/bin/zsh
# Process filter only; no kext loading, display gates or WindowServer restart.
set -eu
[[ "$(uname -s)" == Darwin && "$(id -u)" == 0 ]] || exit 1
base='/Library/Application Support/MubaiGPUWindowServerPolicy'
mkdir -p "$base" /Library/GPUBundles /Library/Extensions
for target in /Library/GPUBundles/nvmtl-allow.txt /Library/Extensions/nvmtl-allow.txt; do
    if [[ -f "$target" ]] && ! /usr/bin/cmp -s "$target" <(printf '%s\n' '-WindowServer' '*'); then
        cp -p "$target" "$base/$(echo "$target" | tr / _)-$(date +%Y%m%d-%H%M%S).before"
    fi
    printf '%s\n' '-WindowServer' '*' > "$target.mubai-new"
    chown root:wheel "$target.mubai-new"
    chmod 644 "$target.mubai-new"
    mv -f "$target.mubai-new" "$target"
    /usr/bin/cmp -s "$target" <(printf '%s\n' '-WindowServer' '*')
    echo "VERIFIED: $target denies WindowServer; other process names allowed."
done
/bin/launchctl getenv NVMTL_ENABLE > "$base/NVMTL_ENABLE.txt" 2>&1 || true
echo 'Policy installed: WindowServer denied; all other process names allowed.'
