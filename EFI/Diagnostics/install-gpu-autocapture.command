#!/bin/zsh
# One-time visible installer. Installs read-only boot capture, then enables stage 4.
set -eu
if [[ "$(id -u)" != 0 ]]; then
    exec /usr/bin/sudo /bin/zsh "$0" "$@"
fi
[[ "$(uname -s)" == Darwin ]] || exit 1
here="${0:A:h}"
[[ "$here" == /Volumes/*/EFI/Diagnostics ]] || { print '请从已挂载的 EFI 运行 / Run from the mounted EFI'; exit 1; }
[[ -f "$here/gpu-display-capture.command" ]] || exit 1
config="$here/../OC/config.plist"
key=':NVRAM:Add:7C436110-AB2A-4BBB-A880-FE41995C9F82:boot-args'
args="$(/usr/libexec/PlistBuddy -c "Print $key" "$config")"
[[ "$args" != *xegfx_bootstage=* ]] || { print '开机参数已存在，请先核查 / Boot stage argument already present'; exit 1; }
base='/Library/Application Support/MubaiGPUCapture'
plist='/Library/LaunchDaemons/org.mubai.gpu-capture.plist'
[[ ! -e "$plist" && ! -e "$base" ]] || { print '已存在安装，请先核查 / Existing installation'; exit 1; }
mkdir -p "$base" "$here/reports"
cp -p "$config" "$base/config-before-autocapture.plist"
cat > "$base/capture.zsh" <<'CAPTURE'
#!/bin/zsh
set -u
for n in {1..30}; do
    /usr/sbin/diskutil mount SYSTEM >/dev/null 2>&1 || true
    if [[ -f /Volumes/SYSTEM/EFI/Diagnostics/gpu-display-capture.command ]]; then
        /bin/zsh /Volumes/SYSTEM/EFI/Diagnostics/gpu-display-capture.command
        exit $?
    fi
    sleep 2
done
exit 1
CAPTURE
cat > "$plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.mubai.gpu-capture</string>
<key>ProgramArguments</key><array><string>/bin/zsh</string><string>/Library/Application Support/MubaiGPUCapture/capture.zsh</string></array>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>/Library/Logs/MubaiGPUCapture.log</string>
<key>StandardErrorPath</key><string>/Library/Logs/MubaiGPUCapture-error.log</string>
</dict></plist>
PLIST
chown -R root:wheel "$base"
chmod 755 "$base" "$base/capture.zsh"
chown root:wheel "$plist"
chmod 644 "$plist"
/usr/bin/plutil -lint "$plist"
/bin/launchctl bootstrap system "$plist"
# Enable boot initialization only after the capture service is installed and loaded.
if ! /usr/libexec/PlistBuddy -c "Set $key $args xegfx_bootstage=4" "$config" || ! /usr/bin/plutil -lint "$config"; then
    cp -p "$base/config-before-autocapture.plist" "$config"
    print '启动参数修改失败，已恢复 / Boot configuration restored'
    exit 1
fi
print '自动采集已安装，开机 stage 4 已启用。正常重启 macOS，等待两分钟再回 Windows。'
print 'Capture service installed; boot stage 4 enabled. Reboot macOS, wait two minutes, then return to Windows.'
