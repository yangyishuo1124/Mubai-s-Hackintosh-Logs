#!/bin/bash
# Read-only comparison. Never print, export, hash or persist either password.
set +x
set +v
set -u
umask 077
unset expected stored
trap 'unset expected stored' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$(uname -s)" != Darwin ]]; then
    echo 'Run this on macOS in your logged-in desktop session.'
    exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
    echo 'Run with bash, WITHOUT sudo, so the correct user keychain is checked.'
    exit 1
fi
if [[ ! -t 0 ]]; then
    echo 'An interactive Terminal is required for hidden password input.'
    exit 1
fi
here="$(cd "$(dirname "$0")" && pwd)"
echo 'Read-only check: no Wi-Fi connection, password or network setting is changed.'
echo 'Enter the GUI-failing network and the password that worked with direct join.'
echo 'Passwords are compared in memory; only result labels are saved.'
printf 'Network name: '
IFS= read -r network || exit 1
[[ -n "$network" ]] || exit 1
printf 'Known working Wi-Fi password (hidden): '
IFS= read -r -s expected || { printf '\n'; exit 1; }
printf '\n'
[[ -n "$expected" ]] || { echo 'Empty input; stopped.'; exit 1; }
echo 'macOS may ask to allow access to this network password. Choose Allow once, not Always Allow.'
echo 'If access is denied or cancelled, the result is UNREADABLE, not DIFFERENT.'

summary='Wi-Fi credential comparison v1 (read-only)'
emit() {
    printf '%s\n' "$1"
    summary="${summary}"$'\n'"$1"
}
check_keychain() {
    local label="$1" keychain="$2" query_error query_rc read_rc
    if [[ ! -f "$keychain" ]]; then
        emit "$label: KEYCHAIN_UNAVAILABLE"
        return
    fi
    # Query metadata first; neither attributes nor raw errors go into the report.
    query_error="$(LC_ALL=C /usr/bin/security find-generic-password \
        -D 'AirPort network password' -a "$network" "$keychain" 2>&1 >/dev/null)"
    query_rc=$?
    if [[ "$query_rc" -ne 0 ]]; then
        if [[ "$query_error" == *'specified item could not be found'* ]]; then
            emit "$label: NOT_FOUND"
        else
            emit "$label: UNREADABLE (query exit $query_rc)"
        fi
        return
    fi
    # -w writes the selected secret to stdout, captured only in this shell variable.
    stored="$(/usr/bin/security find-generic-password \
        -D 'AirPort network password' -a "$network" -w "$keychain" 2>/dev/null)"
    read_rc=$?
    if [[ "$read_rc" -ne 0 ]]; then
        emit "$label: UNREADABLE (read exit $read_rc)"
    elif [[ "$stored" == "$expected" ]]; then
        emit "$label: MATCH"
    else
        emit "$label: DIFFERENT"
    fi
    unset stored
}

check_keychain LOGIN "$HOME/Library/Keychains/login.keychain-db"
check_keychain SYSTEM /Library/Keychains/System.keychain
unset expected stored network
emit 'MATCH compares one matching item with the typed password; it does not verify the PMK sent to the driver.'
emit 'DIFFERENT suggests a stale/different selected item; it does not prove which item airportd used.'
emit 'NOT_FOUND covers this query only; other keychains, duplicate items and protected stores are not enumerated.'
emit 'UNREADABLE/KEYCHAIN_UNAVAILABLE is inconclusive. No repair or deletion was performed.'
mkdir -p "$here/reports" 2>/dev/null || true
report="$here/reports/wifi-credentials-$(date +%Y%m%d-%H%M%S).txt"
if printf '%s\n' "$summary" > "$report" 2>/dev/null; then
    printf 'Result saved: %s\n' "$report"
else
    echo 'Could not save the result here. The result labels above are sufficient.'
fi
