# 触摸板 GPIO 中断调查 / Touchpad GPIO interrupt investigation

## 当前结论 / Current finding

本机仍使用用户确认可用的强制轮询模式，中断尚未修复。上次仅移除 `-vi2c-force-polling` 后触摸板失效；本次不重复部署该配置。

The machine retains the user-confirmed forced-polling mode. GPIO interrupts are not repaired. Removing `-vi2c-force-polling` previously disabled input; that configuration is not being redeployed.

Windows 当前枚举五个正常的 `ACPI\INTC10BB` GPIO 实例（UID 0、1、3、4、5）与 TZY4E41 I2C HID。现有 EFI 的 VoodooGPIO Info.plist 把 INTC10BB 加到了 VoodooGPIOTigerLakeLP 的匹配列表。这只改变匹配，不增加 Panther Lake 寄存器或引脚表支持。最新 macOS IOService 树未显示 VoodooGPIO 控制器实例，尚无中断路由成功证据。

Windows currently enumerates five healthy ACPI\INTC10BB GPIO instances (UIDs 0, 1, 3, 4, 5) and the TZY4E41 I2C HID. The existing EFI adds INTC10BB to the VoodooGPIOTigerLakeLP matching personality. A match change does not implement Panther Lake register or pin support. The latest macOS IOService tree shows no VoodooGPIO controller instance, so successful interrupt routing is not established.

## 布局差异 / Layout mismatch

| Register | 本机 BIOS GPI0 `_DSD` / Local firmware | 上游 Tiger Lake-LP / Upstream |
|---|---|---|
| PAD_OWN | 0x130 | 0x020 |
| PADCFGLOCK | 0x290 | 0x080 |
| HOSTSW_OWN | 0x2C0 | 0x0B0 |
| GPI interrupt status | 0x300 | 0x100 |
| GPI interrupt enable | 0x310 | 0x120 |

本机 GPI0 描述 Community0，包含 GPP_V 与 GPP_C，各 24 pads，配置偏移分别 0x800、0x980。其他 community 需要分别解析。上游核心还存在固定 `GPI_IS = 0x100`；仅改 personality 或子类常量不足以支持本机。

Local GPI0 describes Community0 with GPP_V and GPP_C, 24 pads each, at configuration offsets 0x800 and 0x980. Other communities require their own parsing. The upstream core also uses a fixed `GPI_IS = 0x100`; changing a personality or subclass constants alone is insufficient.

参考 / References: [Tiger Lake layout](https://github.com/VoodooI2C/VoodooGPIO/blob/master/VoodooGPIO/TigerLake-LP/VoodooGPIOTigerLakeLP.hpp), [GPIO core](https://github.com/VoodooI2C/VoodooGPIO/blob/master/VoodooGPIO/VoodooGPIOIntel.cpp), [Linux ACPI property based platform driver](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/intel/pinctrl-intel-platform.c).

## 接下来需要确认 / Remaining work

1. 确认实际 TPD0 `_CRS` 选择 GPIO 还是 APIC；OEM I2C 表按 TPTD[5] 动态选择，TPDI 初始值可在初始化时改变，不能把初始常量直接当作运行时引脚。 / Confirm the evaluated TPD0 resource uses GPIO or APIC. Firmware selects dynamically using TPTD[5]; initial TPDI constants do not establish the runtime pin.
2. 核对目标 GPIO community 的 macOS 枚举、资源映射和启动错误。 / Check macOS enumeration, resource mapping and startup errors for the target community.
3. 若确认缺失平台支持，需实现按 ACPI UID/属性识别的平台驱动、寄存器偏移与 pin/group 映射，并在 macOS 编译验证。不能直接套用 Tiger Lake 的 MMIO 写入。 / If platform support is missing, implement ACPI UID/property based platform handling, register offsets and pin/group mappings, then build and validate on macOS. Tiger Lake MMIO writes must not be substituted blindly.

本次只增强采集：完整 IOACPIPlane、GPI0–GPI5、TPD0、启动期 VoodooI2C/VoodooGPIO 日志，以及标准路径的构建工具目录是否存在。不读写 GPIO 寄存器，不改 boot-args、SSDT 或驱动。不要求先切换中断再测试。Windows 无完整 macOS/Xcode 构建环境，目前没有已编译的平台修复产物。

This update only extends collection with IOACPIPlane, GPI0–GPI5, TPD0, boot-time VoodooI2C/VoodooGPIO logs, and presence of build-tool directories at standard locations. It does not access GPIO registers or change boot arguments, SSDTs or drivers, and does not require switching to interrupt mode for collection. The Windows host lacks a full macOS/Xcode build environment; no compiled platform repair exists yet.
