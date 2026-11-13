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
echo 'Close the Wi-Fi menu and System Settings during this test.'
echo 'Disconnecting the current network before the direct join test.'
"$here/rtw89ctl" rejoin off || true
if ! "$here/rtw89ctl" leave; then
    echo 'Could not disconnect. Collecting the current state.'
    /bin/zsh "$here/collect.command"
    exit 1
fi
sleep 1
# rtw89ctl prompts for the password itself; do not store it in this script.
"$here/rtw89ctl" join "$network"
join_result=$?
echo "Direct join exit status: $join_result"
if [[ "$join_result" -eq 0 ]]; then
    sleep 5
    ipconfig set en0 DHCP
    sleep 10
    ipconfig getifaddr en0
fi
"$here/rtw89ctl" status
echo 'Collecting diagnostics, including failed joins.'
/bin/zsh "$here/collect.command"
exit "$join_result"
