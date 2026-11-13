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
echo 'In Wi-Fi settings, temporarily turn OFF Auto-Join for the OLD saved network.'
echo 'Do not forget/delete it. You can restore Auto-Join after the test.'
echo 'Close the Wi-Fi menu and System Settings during this test.'
printf 'Press Return when ready: '
IFS= read -r ready
echo 'Disconnecting the current network before the direct join test.'
"$here/rtw89ctl" rejoin off || true
if ! "$here/rtw89ctl" leave; then
    echo 'Could not disconnect. Collecting the current state.'
    /bin/zsh "$here/collect.command"
    exit 1
fi
sleep 3
before_join="$("$here/rtw89ctl" status)"
if printf '%s\n' "$before_join" | grep -Eq '^link[[:space:]]+(connected|joining)'; then
    echo 'macOS reconnected before the test. Disable Auto-Join for the old network and retry.'
    /bin/zsh "$here/collect.command"
    exit 1
fi
# rtw89ctl prompts for the password itself; do not store it in this script.
"$here/rtw89ctl" join "$network"
join_result=$?
echo "Direct join exit status: $join_result"
if [[ "$join_result" -eq 0 ]]; then
    echo 'Handshake accepted; observing automatic addressing without reconfiguring en0.'
    address=''
    for attempt in {1..10}; do
        sleep 2
        link_status="$("$here/rtw89ctl" status)"
        if ! printf '%s\n' "$link_status" | grep -Eq '^link[[:space:]]+connected'; then
            echo 'The link dropped after authentication.'
            join_result=2
            break
        fi
        address="$(ipconfig getifaddr en0 2>/dev/null)"
        if [[ -n "$address" ]]; then
            echo "Current IPv4 address: $address (not proof of a new lease)"
            break
        fi
    done
    if [[ "$join_result" -eq 0 && -z "$address" ]]; then
        echo 'Authentication completed, but no IPv4 address appeared within 20 seconds.'
        join_result=3
    fi
fi
"$here/rtw89ctl" status
echo 'Collecting diagnostics, including failed joins.'
/bin/zsh "$here/collect.command"
exit "$join_result"
