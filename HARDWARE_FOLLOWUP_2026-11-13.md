# Follow-up after first macOS test

## Observed

- Battery percentage is now normal with `SSDT-BATT-FIX-UNIT0.aml`; keep this patch.
- The touchpad stopped working after removing `-vi2c-force-polling`. The active internal EFI has the polling argument restored, with the battery patch retained. This rollback still needs a macOS reboot test.
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

The user confirmed that the touchpad works again after restoring polling. The first report shows `en0` active on a WPA2 network, an IPv4 address, a DHCP ACK, DNS and a default route. The user did **not** manually run `ipconfig set en0 DHCP` on this boot; remembering the network password may have allowed automatic connection. The first report therefore does not support a persistent DHCP failure. Internet reachability and GUI switching to a different network still need confirmation.

`BlueToolFixup` and `RealtekBluetoothFirmware` are loaded, but System Information contains no Bluetooth controller. The first diagnostics script accidentally called zsh's `log` builtin instead of `/usr/bin/log`, so the firmware and bluetoothd logs were not captured. The script has been corrected and now records USB IORegistry and network pings into a single ZIP.

The FAT32 report directory was corrupt after the first macOS write. A raw image of the EFI partition was saved locally before a filesystem repair. The repair completed, Windows reported the volume healthy, and the active `config.plist` hash remained unchanged. For the next run, unmount the EFI volume cleanly in macOS before rebooting:

```sh
sudo diskutil unmount /Volumes/SYSTEM
```
