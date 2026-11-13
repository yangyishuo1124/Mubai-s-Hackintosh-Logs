# Follow-up after first macOS test

[简体中文](HARDWARE_FOLLOWUP_2026-11-13.zh-CN.md) · [Bilingual home](README.md)

## Local GPIO ACPI bridge deployed

The new report confirms all five GPIO nodes enter startup and read `_DSD`, then the driver's absolute-path evaluation of `TPDI` returns `0xe00002c2` (bad argument), causing an early exit. This identifies a failing call in the added driver; it does not establish a firmware-resource defect.

Added and enabled `SSDT-PTL-GPIO.aml`, providing local `PTIR` / `PTGR` methods under each GPIO node. AML reads root-level `TPDI` and evaluates firmware `G_IN`; the driver calls these local methods without parameters. Bounded firmware properties, route and descriptor are retained for subsequent validation. This driver requires the accompanying SSDT.

Build and checks passed; backed up, deployed, read back and ocvalidate passed. Forced polling remains enabled; hardware validation is pending. See [GPIO details](TOUCHPAD_GPIO.md).

## New GPIO matching/trace build deployed with polling retained

Continuing at the user request: aligned provider matching and added probe/start tracing plus stage properties on GPIO nodes. macOS build/checks pass; active EFI deployment is readback-verified. Polling remains enabled to verify controller startup first. Interrupt repair is unconfirmed. See the [GPIO record](TOUCHPAD_GPIO.md).

## GPIO trial failed and rolled back

The user reports no input. The intended GPIO binary loaded, but no controller instance or touchpad HID driver appears. Original driver and forced polling are restored, with readback and ocvalidate passing; recovery awaits a reboot. Startup tracing is added to source; future controller diagnosis must retain polling. See the [GPIO record](TOUCHPAD_GPIO.md).

## GPIO platform trial compiled and deployed

Added Panther Lake ACPI-property support and runtime touchpad-controller selection. GitHub macOS compilation and static checks pass. Original files are backed up; the active GPIO kext is replaced and forced polling removed. Readback and ocvalidate pass. No hardware boot test yet; this is not a confirmed repair. See the [implementation record](TOUCHPAD_GPIO.md).

## GPIO test: declared class absent from the binary

All five GPIO nodes enumerate, but boot logs show five failures to allocate VoodooGPIOTigerLakeLP, whose class name is absent from the current VoodooGPIO 1.1 binary. The personality and binary are inconsistent; the touchpad explicitly remains Polling. This blocks startup before register configuration, but adding Tiger Lake support alone would not establish Panther Lake compatibility. See the [GPIO investigation](TOUCHPAD_GPIO.md). No EFI changes or repeated collection requested; interrupts remain unresolved.

## Touchpad GPIO: platform layout mismatch identified

See the [bilingual GPIO investigation](TOUCHPAD_GPIO.md). Existing INTC10BB matching points at Tiger Lake while firmware register offsets differ; interrupts remain unresolved. Only diagnostic collection is extended; working polling, boot configuration and drivers are retained.

## Read-only credential check: neither query found a matching item

The user ran the new comparison helper. Its report contains `LOGIN: NOT_FOUND` and `SYSTEM: NOT_FOUND`. These results cover only the target account/kind query against the traditional login/system keychains. No password was retrieved and no password comparison occurred. They establish neither an absent saved password, correct/incorrect credentials, keychain corruption nor exclusion of credential handling. Other stores, record attributes and duplicates were not enumerated. No network, keychain, driver or boot setting was changed; GUI joining remains unresolved.

Do not repeat the same check or clear network settings on this evidence. Existing logs cannot validate the actual PMK handed from the GUI path to the driver. Distinguishing system credential handoff from driver handling requires new observation at that boundary rather than assigning blame from a handshake timeout. An instrumented driver is one option, but requires building and separate hardware validation; none has been deployed.

## Credential and key-lifetime review: read-only comparison helper

Reviewed local upstream `76d23fe` through `decodeHostAssoc → nativeAssociate → glue_join_request → mlme_connect`. GUI-supplied PMKs and directly derived PMKs reach the shared connection path; `glue.want.pmk` and `mlme.pmk` are synchronously copied before returning. This does not support a simple theory that clearing temporary request buffers destroys the active handshake key. Both GUI attempts and the direct attempt are logged as WPA2, without a logged AKM selection difference in this comparison. Static review does not validate incoming PMK contents, decoding offsets or concurrency.

The failure window contains no log proving a failure to read the Wi-Fi password. Startup WiFiAgent readiness messages and missing Captive Portal credentials do not establish corruption of the target Wi-Fi password. Private-MAC creation succeeds at request start; an EINVAL against a null network after association failure does not establish causation either. Global network settings and keychains remain intact.

Added `wifi-credential-check.command`: hidden input of the known-working password, compared in memory with one matching item from each of the login/system keychains. Only result labels are recorded. It neither connects nor writes passwords, and emits no secret bytes or hashes. Duplicate records, other stores and airportd's actual item selection remain outside its evidence. MATCH does not validate the driver's PMK; DIFFERENT is only a saved-item discrepancy, and unavailable reads are inconclusive. Usage and limitations are in the bilingual home page. Syntax and five mocked branches pass; macOS integration remains untested. Only a diagnostic file is added; boot configuration and drivers remain unchanged, and GUI joining is unresolved.

## Same-run GUI/direct comparison completed

The latest report captures two GUI/native WPA2 joins to the same AP, each receiving M1 and sending acknowledged M2 replies before AP deauthentication reason 15 and native error -2015. A later direct-password request in that same boot targets the exact same BSSID and channel, completes key installation/native link up, remains connected at collection, has IPv4, and passes public-IP pings 3/3. Identifiers were compared locally and are not published. The ZIP passed its integrity check.

This establishes an observed direct-password workaround on the previously GUI-failing AP and narrows investigation to differences in native association/credential/state handling. It does not prove the incoming PMK bytes or their offsets are wrong; request flags/RSN and state differences remain possible. Both GUI attempts actually execute the join path and fail before the next attempt, so the duplicate-request shortcut is not supported as the explanation for these recorded attempts. Do not promote that earlier code concern to the root cause or deploy a speculative fix.

The passive-address helper no longer forces DHCP, and this run has no five-second disconnect. That correlation does not prove the prior forced DHCP caused the drop. A new lease is not inferred solely from the IPv4 value; ongoing link state and successful traffic establish usable connectivity. No boot configuration, kext or helper changes were made in this review. Only bilingual documentation was updated; no further test is requested.

## Source review and passive address observation

Reviewed the local upstream snapshot at `76d23fe`, particularly native POWER, DISASSOCIATE, ASSOCIATE and CIPHER_KEY handling, plus the external-PMK setter. The native DISASSOCIATE path explicitly calls glue_leave when not joining. The core Ethernet interface enable/disable methods only control output threading, so they alone do not explain a radio disconnect. A POWER-on log near a disconnect does not identify which subsequent caller requested leaving. No raw native request or caller stack was captured, so a proven call chain is still unavailable.

The association decoder reads the PMK/passphrase according to its cipher field; native WPA2 PMK and driver-derived-password joins use separate entry points. The late PMK setter is restricted to external-authentication connections, which is worth bearing in mind when inspecting key timing, but there is no logged late-key delivery proving that branch matters here. Neither a malformed key nor a decoder-offset error has been established.

The helper's forced `ipconfig set en0 DHCP` is removed to avoid injecting interface reconfiguration into the observation. After a successful join it now checks link state and existing IPv4 for up to 20 seconds, reports a link drop separately (exit 2) from no IPv4 (exit 3), and still collects diagnostics. An existing IPv4 is not described as a new lease. Only the helper changed after local backup and readback; config.plist, driver binaries, audio and Bluetooth were retained. Shell syntax and repository whitespace checks passed; macOS runtime behavior remains untested. No further reboot/test was requested at this stage. This correction does not claim to fix GUI joining.

## Latest target test: authentication succeeds, link is then lost

The new direct join reaches the AP that previously showed GUI M2 timeouts in earlier reports (matched privately by BSSID). Association and WPA2 key installation complete, followed by native link up. This establishes that direct-password authentication can work with that AP, beyond the previously working saved AP. The current driver ring does not contain a fresh GUI join failure in this same run, so this is a cross-report comparison, not a controlled same-run A/B test.

Approximately 5.1 seconds later, the ring records a macOS Wi-Fi-on operation, local MLME leaving, and native link down. The final interface is inactive, without an IPv4 address or DHCP packet; public-IP pings fail. No AP-originated deauthentication is recorded at that disconnect. The timing closely matches the helper's five-second wait followed by `ipconfig set en0 DHCP`, and system logs show an iff_up event and DHCP media-inactive status. An interface reconfiguration/reset is therefore a concrete suspect for loss after authentication; causation by the DHCP command is not yet proven.

GUI credential handoff/state and post-direct-join interface handling should be investigated separately. A completed handshake does not establish usable networking, and does not by itself prove a PMK decoder bug. Only bilingual documentation was updated; no EFI or helper changes and no additional test request were made. Raw identifiers and reports remain local; ZIP integrity passed.

## Latest report: direct-password join succeeds

The newest report captures a direct driver join request followed by association and a completed WPA2 handshake, without EBUSY. The subsequent report has an IPv4 address and successful gateway/public-IP pings (3/3 each). This validates the direct-join helper and a working direct-password connection on the tested AP. The IPv4 address alone does not establish a newly issued lease; connectivity after the join is independently demonstrated by pings.

Important limit: the successful direct join uses the same AP as the saved-network autojoin earlier in this boot. There is no fresh failed GUI join to that target in this report. It therefore does not prove a GUI PMK parsing bug, nor establish that direct joining fixes every previously failing target. Credential handoff/state and target selection remain hypotheses for the GUI issue. No further tests were requested and no EFI or helper files were modified in this review; only public bilingual status documentation was updated. The raw ZIP passed integrity checking and remains local.

## Upstream issue review (2026-11-13; testing paused)

- [Issue #2](https://github.com/FranciumOS-org/AirPort_RTW89/issues/2): another RTL8852BE user reports correct-password WPA2 join failures on Ventura. The maintainer asks for an update and logs; the thread has no verified fix or matching M2/M3 evidence. Same card/similar symptom does not prove the same cause.
- [Issue #4](https://github.com/FranciumOS-org/AirPort_RTW89/issues/4) and [PR #5](https://github.com/FranciumOS-org/AirPort_RTW89/pull/5): Sonoma's 856-byte association request was not decoded. The maintainer reports a 0.5.0 fix. That failure never reached radio association, unlike this Tahoe machine, which reaches WPA2 M2.
- [Issue #7](https://github.com/FranciumOS-org/AirPort_RTW89/issues/7) and open [PR #16](https://github.com/FranciumOS-org/AirPort_RTW89/pull/16): directed-scan delivery, stale BSSID selection and hotspot retries are genuine upstream investigation areas. They justify checking target selection alongside credential handling, but no evidence currently establishes these as this machine's cause. An open scan/selection patch is not a verified WPA2 M2/M3 fix.
- [Issue #17](https://github.com/FranciumOS-org/AirPort_RTW89/issues/17): RTL8852CE first hotspot join failure with a USB-tethering workaround and inconsistent network lists. Different card/workflow, no established repair in the reviewed discussion.

No reviewed thread establishes the exact saved-autojoin-versus-first-GUI-join failure here or provides a confirmed repair for it. PMK handoff/decoding/state remains a hypothesis, not a diagnosis; target-selection/cache behavior remains an alternative worth checking statically. No EFI, kext or test-helper changes were made for this review. No issue or comment was posted upstream.

## Latest direct-join retest: macOS autojoin races the helper

The next report shows macOS automatically rejoining the old saved network and completing WPA2 approximately five seconds before the direct join command returns -16 (EBUSY). A DHCP lease, gateway ping and public-IP ping are successful on that old network. This does not test the target network's password handshake, and is not a new authentication failure. Driver `rejoin off` controls the driver's own retries; it does not disable macOS saved-network autojoin.

The helper now asks the user to temporarily disable Auto-Join for the old saved network, without deleting its credentials, and checks that the link remains disconnected after leave. If macOS reconnects, it stops and collects evidence instead of proceeding with an invalid comparison. This is a test correction, not a GUI Wi-Fi repair. Restore Auto-Join after testing if desired. Only the diagnostic helper changed; the working audio/Bluetooth and boot configuration were retained. The ZIP passed integrity validation; no raw reports were committed.

> Entries below are chronological. Earlier unresolved states are superseded by later retests: Bluetooth recovered and audio devices enumerate; speaker/jack/microphone checks and the GUI Wi-Fi fix remain pending.

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

## Fourth report: wait confirmed by process sample

The Bluetooth daemon's three-second sample is entirely in `IOKitWaitQuiet -> io_service_wait_quiet -> mach_msg2_trap`. Both IOService snapshots show CP01 through CP15 / AppleACPICPU continuously busy for approximately 297 seconds, while CP00 is idle. These CPU services account for the nonzero busy branches captured in the report. This establishes an initialization-state blocker; it does not establish defective CPU hardware, missing usable cores, or a performance problem. The user reports normal CPU operation.

The active MADT contains 16 enabled Local APIC entries. The current generic SSDT-PLUG-ALT declares 64 Processor objects. This discrepancy warrants checking, but is not by itself proof that the SSDT causes the wait. No CPU topology, MADT, power-management setting or boot argument was changed. The collector now also records macOS online CPU counts and detailed AppleACPICPU properties to avoid inferring core availability from busy counters alone. Raw process samples and device trees remain local.

## Fifth report and MCE matching experiment (not yet boot-verified)

macOS reports all 16 physical/logical CPUs online and active; every AppleACPICPU reports `Running`. The user's observation of normal CPU operation is supported. CP01-CP15 nevertheless remain busy in IOKit, and the Bluetooth daemon sample remains in IOKitWaitQuiet.

The existing codeless MCEReporterDisabler has two personalities: a high-priority dummy IOService and an additional personality that loads the real AppleMCEReporter against AppleACPICPU. The real AppleIntelMCEReporter binary is loaded in the report. CP00 has the dummy disabler child, while the other CPU services have no children and remain unmatched/busy. The extra real-reporter match is a concrete competing-match suspect, not a proven root cause.

After backing up the active OC and BOOT folders locally, only the extra `AppleMCEReporter` personality was removed from `EFI/OC/Kexts/MCEReporterDisabler.kext/Contents/Info.plist`. The dummy `Disabler` personality is unchanged. No processor definitions, core counts, MADT, power-management settings, boot arguments or config.plist bytes were changed. This is a reversible Bluetooth initialization experiment, not a confirmed repair. If it regresses booting, restore that Info.plist from the local `before-mce-match-test-*` backup. After booting, run the existing collector and check whether the busy CPU services clear, Bluetooth passes IOKitWaitQuiet, and a usable controller appears. Wi-Fi first-join and internal audio are still unresolved.

## SimpleHDA audio trial (not yet boot-verified)

At the user's request, the official [SimpleHDA 1.0.1 RELEASE](https://github.com/laobamac/SimpleHDA/releases/tag/v1.0.1) package was downloaded and all files checked against its SHA256.json manifest. The active OC, BOOT and diagnostics were backed up locally before installation. SimpleHDA is loaded after the now-enabled AppleALC 1.9.8, with Lilu 1.7.2 already enabled and DisableLinkeditJettison already true. The supplied SimpleHDA entry restricts it to Darwin 25.x. Initial `alcid=3` is a supported ALC235 candidate, not a validated layout for this laptop. No controller device-id/class spoofing was added.

The optional HAL package was not installed: the upstream project supports the ordinary IOAudio path without it. No macOS system-volume changes are made by this EFI trial. The preceding MCE matching experiment remains in place and is also awaiting a boot test.

### Retest: Bluetooth recovered; audio and GUI Wi-Fi unresolved

The user confirms Bluetooth works. The latest report has no nonzero IOService busy entries; bluetoothd completes IOKitWaitQuiet and starts its controller. Retain the MCE personality correction. SimpleHDA and AppleALC load, but no HDA codec or IOAudio device appears; the controller is now named HDEF. The collector now captures both HDAS and HDEF. The driver notification for AppleHDAController alone does not establish successful attachment.

The next audio experiment injects only compatibility device-id `ca510000` (8086:51CA) at PciRoot(0x0)/Pci(0x1F,0x3), retaining layout 3 and the existing SimpleHDA stack. This compatibility ID has been reported in a Meteor Lake AppleALC setup (https://github.com/VedCloud/Meteor-Lake-Xe-LPG-Metal-Graphics), but its suitability for Panther Lake E328 is unverified. No PCI class override is added: the restored AppleHDAController already matches both multimedia/HDA class forms. The prior config is backed up locally under `before-audio-controller-trial-*`; restore it if this trial regresses booting.

Wi-Fi still completes the handshake on saved autojoin but fails before DHCP on a fresh GUI join. The latest upstream release is still 0.6.0-BETA. `EFI/Diagnostics/wifi-direct.command` uses the supplied rtw89ctl password-prompt join path, then requests DHCP on en0. Run `sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/wifi-direct.command`, enter the network name and password locally, then run the collector. This bypass is an unverified workaround, not a GUI fix. No password is embedded or saved by the wrapper. Raw reports remain local.

### Latest retest: audio enumeration confirmed; direct Wi-Fi test corrected

The user reports that audio devices now appear. The new report contains an IOHDACodecDevice with vendor/codec ID 0x10EC0235 and an AppleHDADriver publishing Built-in Audio. Retain SimpleHDA, AppleALC, layout 3 and the 51CA compatibility ID. Speaker playback, headphone output and microphone capture have not yet been separately confirmed. Bluetooth recovery remains confirmed by the user.

Both direct Wi-Fi join attempts returned -16 (EBUSY) before a new association/handshake. The saved network stayed connected, with a DHCP lease and successful gateway pings. This test therefore does not compare direct-password authentication against GUI authentication yet. The first wrapper incorrectly attempted join without leaving the existing network. It now switches driver rejoin off, calls leave, waits briefly, then asks rtw89ctl to join. Close the Wi-Fi menu and System Settings during the test to reduce concurrent GUI scans. The wrapper now runs the collector after both success and failure; the password is still entered only into rtw89ctl's hidden prompt. The boot configuration and audio/Bluetooth kexts were not changed in this update. GUI first-join failure remains unresolved.

The latest report ZIP passed its integrity check after dismounting and refreshing the Windows EFI mount. No filesystem repair was required for this readback. Raw reports and private network identifiers were not uploaded.

After reboot, check Sound settings for outputs and inputs; if present, test the built-in speakers at low volume, the headphone jack and microphone separately. Then run `EFI/Diagnostics/collect.command` as before. It now captures audio device/codec/controller IORegistry and coreaudiod/AppleHDA/SimpleHDA logs. Driver loading alone is not a passing audio result. If booting regresses, restore config.plist from the local `before-simplehda-*` backup; its configuration does not enable SimpleHDA or AppleALC, even if the new kext folder remains on disk. Raw reports stay local.
