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
| **Touchpad** | ASUS Precision Touchpad (`\_SB.PC00.I2C0.TPD0`) | **Working** (`VoodooPS2Mouse.kext` via BIOS PS/2 emulation) |
| **USB Controllers** | Intel Panther Lake xHCI & Type-C Subsystems | **Working** (`SSDT-EC-USBX-LAPTOP.aml`) |
| **Audio** | Realtek ALC256 / Intel Smart Sound | Work in progress |
| **Wireless / BT** | Intel Wi-Fi / Realtek Wi-Fi | Work in progress |

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
   - Touchpad is driven by hardware BIOS PS/2 mouse emulation via `VoodooPS2Mouse.kext` (avoids I2C polling lockups).

---

## What Does Not Work (Yet)

- **Hardware GPU Acceleration (Metal)**:
  - The desktop renders using CPU software rasterization (Basic Framebuffer).
  - Awaiting future developments in community drivers (such as XeGfx / WTLIntelGfx).
- **Native I²C Multitouch Gestures**:
  - `VoodooI2C` currently causes bus deadlocks with Panther Lake I2C controllers. Basic tracking and clicking work via PS/2 emulation.
- **Wi-Fi / Bluetooth**:
  - Wi-Fi 7 (Intel BE200/BE211) or newer Realtek chipsets require experimental kext research.

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
