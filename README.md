# ASUS Vivobook S16 (S5650AA) - Intel Panther Lake Hackintosh

OpenCore EFI configuration for **ASUS Vivobook S16 S5650AA**, powered by Intel's 15th/16th Gen **Core Ultra 7 356H (Panther Lake)** architecture.

Successfully boots macOS into the graphical desktop / Recovery environment using pure UEFI GOP basic software rasterization.

---

## Hardware Specifications

| Component | Hardware Details | Status |
| :--- | :--- | :--- |
| **Model** | ASUS Vivobook S16 (S5650AA) | Fully Verified |
| **Processor** | Intel Core Ultra 7 356H (Panther Lake, 16C / 16T) | **Working** (Comet Lake CPUID spoof `0x0A0655`) |
| **Integrated GPU** | Intel Arc Graphics (Xe2, PCI ID `8086:B0A0`) | **Working** (Basic Framebuffer / GOP VESA) |
| **Memory** | 32 GB LPDDR5X 7467 MT/s | **Working** |
| **Display** | 16-inch 3.2K (3200x2000) 120Hz OLED Panel | **Working** (Native resolution GOP display) |
| **Storage 1** | RS1D0TSSD710 1TB NVMe (Maxio MAP1608 controller) | **Working** (APFS root filesystem mounted) |
| **Storage 2** | Samsung PM981 256GB NVMe (Secondary slot) | **Disabled** via `SSDT-Disable-PM981.aml` (Prevents panic) |
| **Keyboard** | ASUS Built-in Keyboard (`\_SB.PC00.PS2K`) | **Working** (`VoodooPS2Keyboard.kext`) |
| **Touchpad** | ASUS Precision Touchpad (`\_SB.PC00.I2C0.TPD0`) | **Testing GPIO interrupt** (`VoodooI2C` + `VoodooI2CHID`; polling boot argument removed) |
| **USB Controllers** | Intel Panther Lake xHCI & Type-C Subsystems | **Working** (`SSDT-EC-USBX-LAPTOP.aml`) |
| **Audio** | Realtek ALC235 on Intel SST Bus (`8086:E328`, Class `040100`) | **USB DAC / Type-C Audio / Bluetooth** (Intel SST DSP has no macOS AppleHDA stack) |
| **Wireless / BT** | Realtek RTL8852BE Wi-Fi 6 (`10EC:B852`) & Realtek BT (`0BDA:B85B`) | **Testing** (AirPort_RTW89 0.6.0, RealtekBluetoothFirmware 1.0.2, BlueToolFixup 2.7.2) |

---

## Current EFI update (2026-11-13)

The internal ESP was backed up locally before this update. The checked-in `EFI/OC/config.plist` and changed kexts were copied from the internal ESP after writeback. Static validation with OpenCore 1.0.8 `ocvalidate` passed. **Boot and hardware behavior have not yet been retested in macOS.**

- Wi-Fi: updated AirPort_RTW89 from 0.5.0 to 0.6.0 Beta. The reported symptom was network scanning followed by “Unable to join network.”
- Bluetooth: added RealtekBluetoothFirmware 1.0.2 and BlueToolFixup 2.7.2 for USB ID `0BDA:B85B`. Firmware upload and controller operation require macOS log verification.
- Battery: added `SSDT-BATT-FIX-UNIT0.aml` to correct the ACPI power unit from mAh to mWh for values already calculated in mWh. This may not be the sole cause of the 4% display.
- Touchpad: removed `-vi2c-force-polling` to test GPIO interrupt mode. Keep a USB mouse available for recovery.
- Audio: unchanged. Intel SST `8086:E328` and Realtek ALC235 remain undetected in macOS; Tahoe also lacks the old AppleHDA stack.

See [`HARDWARE_TEST_2026-11-13.md`](HARDWARE_TEST_2026-11-13.md) for verification steps and rollback.

---

## What Works & Key Breakthroughs

1. **CPU & Kernel Bring-up Past `EXITBS:START`**:
   - Panther Lake firmware defaults to x2APIC processor definitions in MADT/APIC ACPI tables, which causes macOS XNU to immediately freeze at `EXITBS:START`.
   - Solved using [`APIC-legacy.aml`](ACPI_Source/APIC-legacy.aml) (converting ACPI APIC structures to classic Local APIC), dropping firmware MADT & DMAR, and applying `SSDT-PLUG-ALT.aml` with 16 core processor objects.
   - Comet Lake CPUID spoof (`0x0A0655`) + `ProvideCurrentCpuInfo = True` + `AppleXcpmCfgLock = True` + `AppleXcpmExtraMsrs = True`.
2. **ACPI & Embedded Controller (EC) Deadlock Elimination**:
   - ASUS motherboards designate the real hardware EC as `\_SB.PC00.LPCB.H_EC`.
   - macOS `AppleUSBHostResources` and `TypeCBPC` probe indefinitely for an ACPI device strictly named `EC`.
   - Resolved using [`SSDT-EC-USBX-LAPTOP.aml`](ACPI_Source/SSDT-EC-USBX-LAPTOP.aml), injecting a compliant macOS-only `Device (EC)` alongside USB power properties.
3. **Display & Graphical Interface on Unsupported Xe2 iGPU**:
   - There is currently no native hardware Metal acceleration driver for Intel Panther Lake Xe2 graphics.
   - The display is driven by Apple's software rasterizer over the native UEFI GOP framebuffer (`AppleCLCD` / `PE_Video`).
   - Clean `DeviceProperties` (no toxic property injection that tricks `IONDRVSupport` into crashing).
4. **Input Devices (Keyboard & Touchpad)**:
   - Built-in keyboard is fully driven by `VoodooPS2Keyboard.kext`.
   - The previously booted EFI used `VoodooI2C`/`VoodooI2CHID` in forced polling mode. The current EFI removes `-vi2c-force-polling` to test the firmware GPIO interrupt resource. This has not yet been verified after reboot.

---

## What Does Not Work (Yet) & Technical Notes

- **Hardware GPU Acceleration (Metal) & "About This Mac"**:
  - The desktop currently renders using CPU software rasterization (Basic Framebuffer / GOP VESA) as Intel Xe2 Battlemage/Celestial graphics lacks a native Apple Metal driver.
  - In modern macOS (Ventura, Sonoma, Sequoia), **"About This Mac"** (System Settings -> About) relies heavily on SwiftUI and Metal. Without Metal, this window can display as a blank/white frame.
  - **Workaround to view hardware specs**: Hold the **Option (`Alt`)** key and click the Apple logo () -> **"System Information..."** (`系统信息.app`). This legacy AppKit utility renders immediately without Metal and accurately details the full CPU, RAM, NVMe, PCI, and USB device trees.
- **Internal Audio (Intel Smart Sound Technology)**:
  - Panther Lake routes the Realtek ALC235 codec through an **Intel Smart Sound Technology (Intel SST) DSP controller** (`PCI\VEN_8086&DEV_E328`, PCI Class `040100`).
  - macOS's `AppleHDAController` strictly binds to legacy High Definition Audio (PCI Class `040300`). Apple never implemented an Intel SST DSP firmware loader or SoundWire stack.
  - **Recommended Solution**: Plug in any class-compliant USB-C / USB audio dongle or DAC (e.g. Apple's official USB-C to 3.5mm adapter, ~$9). macOS includes native `AppleUSBAudio` drivers that work out of the box with zero configuration and volume control. Bluetooth headphones also work once Bluetooth is loaded.
- **Native I²C Multitouch Gestures**:
  - The current EFI tests GPIO interrupt mode. If the touchpad stops responding or CPU usage rises, restore the backed-up EFI or add `-vi2c-force-polling` back to `boot-args`.
- **Internal Battery Indicator**:
  - `SMCBatteryManager` is enabled. The previous EFI showed 4% while Windows reported a much higher charge. The current EFI tests an ACPI `_BIF`/`_BIX` power-unit correction (`SSDT-BATT-FIX-UNIT0.aml`); the actual percentage still needs a macOS readback.

---

## Recommended BIOS Settings

- **Disable**:
  - Fast Boot
  - Secure Boot
  - Intel Platform Trust Technology (PTT) / TPM (optional)
  - Intel VMD (RAID/RST) -> Switch to AHCI / Standard NVMe
  - Intel VT-d (can be disabled in BIOS or dropped via OpenCore ACPI Delete DMAR)
- **Enable**:
  - Hyper-Threading
  - Above 4G Decoding

---

## Boot Instructions

> [!IMPORTANT]
> **Cold Boot Recommendation**:
> On initial installation or after changing EFI configurations, always perform a **Cold Boot** (completely power down the laptop, wait 5–10 seconds, then press the power button). A warm soft reboot may leave the motherboard EC / touchpad controller in an uninitialized state.

1. Copy the `EFI` folder to your USB drive or internal ESP partition (`EFI/BOOT` and `EFI/OC`).
2. Boot into the OpenCore picker.
3. Press **Spacebar** and choose **`Reset NVRAM`** on the first boot to clear any cached NVRAM parameters.
4. Select your macOS boot entry or Recovery entry.

---

## Credits & Acknowledgements

- **[Acidanthera](https://github.com/acidanthera)**: OpenCore Bootloader, Lilu, VirtualSMC, VoodooPS2Controller.
- **[lemlnn / Lem's Hardware Lab](https://github.com/lems-hardware/lhl-hackintosh-docs)**: Groundbreaking research and documented boot attempts on Framework 13 Pro Panther Lake hardware.
- **[Dortania](https://dortania.github.io/)**: OpenCore Install Guide and comprehensive Hackintosh documentation.
- **老吴黑苹果工作室**: Base recovery reference environment.
