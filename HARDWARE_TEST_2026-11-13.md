# Hardware test after the 2026-11-13 internal EFI update

[简体中文](HARDWARE_TEST_2026-11-13.zh-CN.md) · [Bilingual home](README.md)

> Historical initial test plan. Battery and polling touchpad operation were subsequently confirmed, Bluetooth recovered, and audio devices now enumerate. GUI Wi-Fi joins remain unresolved. See the latest [follow-up](HARDWARE_FOLLOWUP_2026-11-13.md).

The internal ESP received the contents checked into this commit. The previous working EFI was backed up locally before the write. Every changed payload was read back and SHA-256 compared; OpenCore 1.0.8 `ocvalidate` passed against the ESP's `config.plist`. A successful boot and device operation have **not** yet been observed after this update.

## Tests to run in macOS

1. Confirm the system reaches the desktop. Keep a USB mouse ready because the touchpad now tests GPIO interrupt mode.
2. Wi-Fi: forget the previously failed network, then try a WPA2 2.4 GHz network or phone hotspot. Report whether the join succeeds, fails immediately, asks for a password again, or joins without an IP address. The driver is AirPort_RTW89 0.6.0 Beta.
3. Bluetooth: check System Information > Bluetooth and try pairing a device. The USB entry alone does not prove that firmware uploaded. Check the boot log for `RealtekFirmware` and `firmware download complete`.
4. Battery: compare the macOS menu percentage with Windows or the firmware gauge at nearly the same time. Capture `ioreg -lw0 -r -c AppleSmartBattery` and `pmset -g batt`. The new ACPI patch corrects units but may not solve the 4% symptom.
5. Touchpad: confirm cursor, clicks, gestures, sleep/wake, and idle CPU use. Check the VoodooI2C IORegistry/log for GPIO interrupt mode. If it fails, restore the prior EFI or add `-vi2c-force-polling` back to `boot-args`.
6. Audio is still unresolved. Windows identifies Intel SST `8086:E328` and Realtek ALC235. Do not infer support from AppleALC codec layout IDs alone; the host controller and Tahoe audio stack also need verification.

The diagnostics helper is `tools/collect_macos_diagnostics.command`. Run it with `zsh /path/to/collect_macos_diagnostics.command` within 30 minutes of a failed Wi-Fi join. Its output can contain network names and hardware identifiers; review it before sharing.

## Rollback

Restore the complete pre-update EFI backup to the ESP. The backup contains the working AirPort_RTW89 0.5.0 configuration, no Realtek Bluetooth additions, and `-vi2c-force-polling`. If only touchpad interrupt mode fails, adding that boot argument back is the smaller rollback.

## Future update flow

For each EFI update: inspect the current internal ESP, back it up, change the internal ESP, read back and validate the changed files, then copy the actual ESP changes into this repository and push them. Report separately what was checked on disk and what was verified after a macOS boot.
