# Follow-up after first macOS test

## Observed

- Battery percentage is now normal with `SSDT-BATT-FIX-UNIT0.aml`; keep this patch.
- The touchpad stopped working after removing `-vi2c-force-polling`. The active internal EFI has the polling argument restored, with the battery patch retained. The user confirmed the touchpad works again after reboot.
- Wi-Fi scans. The graphical interface reports a join error. `networksetup -setairportnetwork en0 ...` was used to connect, but `en0` did not obtain an IP address. It is not yet clear whether the command established a full association or whether DHCP/network-service creation failed.
- The Realtek Bluetooth device remains visible under USB but is not usable. Firmware upload and `bluetoothd` state have not yet been observed.

## One-run diagnosis on the same laptop

`EFI/Diagnostics/collect.command` is installed on the internal EFI partition. In macOS Terminal, use `diskutil list` to find the approximately 467 MB FAT32 EFI partition labelled SYSTEM, then run:

```sh
sudo diskutil mount diskXs1
sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/collect.command
```

Replace `diskXs1` with that partition's identifier. The command saves its report under `EFI/Diagnostics/reports/` on the EFI partition. Reboot into Windows and the report can be read locally. It contains network names and hardware IDs, so review before posting publicly.

To test whether DHCP is simply not started for `en0`, after attempting the command-line join run:

```sh
ifconfig en0
ipconfig getifaddr en0
sudo ifconfig en0 up
sudo ipconfig set en0 DHCP
sleep 10
ipconfig getifaddr en0
ipconfig getpacket en0
```

The [AirPort_RTW89 porting notes](https://github.com/FranciumOS-org/Airport_RTW89/blob/main/docs/PORTING.md) document a case where macOS did not create a network service for a new interface and DHCP had to be started manually. This is a diagnostic lead, not yet the established cause on this machine.

For Bluetooth, the [firmware driver's installation notes](https://github.com/thegwchr/RealtekBluetoothFirmware/blob/main/docs/Installation.md) say that `RealtekFirmware` log entries distinguish a successful firmware upload from a device that was never matched. If upload succeeded but Bluetooth still fails, inspect `bluetoothd` and BlueToolFixup logs before changing the EFI again.

## First report readback

The user confirmed that the touchpad works again after restoring polling. The first report shows `en0` active on a WPA2 network, an IPv4 address, a DHCP ACK, DNS and a default route. The user did **not** manually run `ipconfig set en0 DHCP` on this boot; remembering the network password may have allowed automatic connection. The first report therefore does not support a persistent DHCP failure. The user confirmed web browsing works over this Wi-Fi. GUI switching to another network still reports a join error.

`BlueToolFixup` and `RealtekBluetoothFirmware` are loaded, but System Information contains no Bluetooth controller. The first diagnostics script accidentally called zsh's `log` builtin instead of `/usr/bin/log`, so the firmware and bluetoothd logs were not captured. The script has been corrected and now records USB IORegistry and network pings into a single ZIP.

The FAT32 report directory was corrupt after the first macOS write. A raw image of the EFI partition was saved locally before a filesystem repair. The repair completed, Windows reported the volume healthy, and the active `config.plist` hash remained unchanged. For the next run, unmount the EFI volume cleanly in macOS before rebooting:

```sh
sudo diskutil unmount /Volumes/SYSTEM
```

## Second report: Wi-Fi and Bluetooth narrowed down

The macOS 26.0 report captured after a failed graphical Wi-Fi join shows that the currently working saved WPA2 network completes its four-way handshake and gets a DHCP lease. A graphical join to another WPA2 network associates, receives the access point's first EAPOL message and sends an acknowledged reply, but never receives message 3. The access point deauthenticates with reason 15; the driver reports native join error `-2015`. This failure occurs before DHCP. The user clarified that the now-working 5 GHz network originally showed the same GUI failure and only acquired an IP after a command-line join saved its password and a reboot. The evidence therefore points to a first-join/saved-credential difference, not a 2.4 GHz-specific fault. The exact macOS-to-driver key handoff remains unproven.

The USB IORegistry contains the Realtek `0BDA:B85B` device as `Bluetooth USB Host Controller` with `FirmwareLoaded = Yes` and class 0xE0. Both RealtekBluetoothFirmware 1.0.2 and BlueToolFixup 2.7.2 are loaded. `system_profiler SPBluetoothDataType` hung and no `IOBluetoothHostController` was published. Firmware upload is therefore not the remaining blocker; `bluetoothd`/controller initialization is. The previous log predicate looked only for messages containing the word `bluetoothd`, which omitted messages emitted by the process itself. The collector now selects `process == "bluetoothd"`, captures kernel messages and skips the hanging System Profiler Bluetooth query.

No private Wi-Fi names, passwords, MAC addresses or raw reports are committed to this repository.

## Third report: Bluetooth initialization wait

The third report shows Realtek firmware `rtl8852bu` uploaded and the firmware service idle (`busy 0`). However, `bluetoothd` logs `Waiting for IOKitWaitQuiet()` during startup with no subsequent completion message in the captured boot log. This suggests a wait before controller initialization; it does not yet prove which device is blocking it, or that the daemon remains on that call. Apple's [IOKitWaitQuiet documentation](https://developer.apple.com/documentation/iokit/1514440-iokitwaitquiet) explains that the function waits until all IOService busy states are zero. A device unrelated to Bluetooth may therefore be involved.

The collector now records the complete IOService topology and nonzero busy counters, samples the Bluetooth daemon for three seconds, and captures its launchd state. It does not restart services or change boot configuration. The next report should distinguish a global device-initialization wait from a later Bluetooth transport failure. Battery correction and working touchpad polling are retained.

The latest ZIP passed its integrity check after refreshing the Windows EFI mount. The subsequent filesystem check reported no errors; this read failure alone is not evidence of new FAT corruption.
