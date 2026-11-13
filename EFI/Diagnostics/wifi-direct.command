#!/bin/zsh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
if [[ "$EUID" -ne 0 ]]; then
    echo "Run with: sudo zsh $0"
    exit 1
fi
printf 'Wi-Fi network name: '
IFS= read -r network
[[ -n "$network" ]] || exit 1
# rtw89ctl prompts for the password itself; do not store it in this script.
"$here/rtw89ctl" join "$network" || exit $?
sleep 5
ipconfig set en0 DHCP
sleep 10
ipconfig getifaddr en0
echo 'Run collect.command afterwards, whether the connection succeeded or failed.'
