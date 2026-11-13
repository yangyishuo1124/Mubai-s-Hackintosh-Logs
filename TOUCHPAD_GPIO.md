# 触摸板 GPIO 中断调查 / Touchpad GPIO interrupt investigation

## 内存资源映射兼容版已部署 / Memory resource mapping compatibility deployed

最新报告 ZIP 完整性通过。PTG0/PTG1 引脚组求值返回成功，GPP_F 为 26 引脚、偏移 0x800，GPP_E 为 25 引脚、偏移 0x9A0；已通过模式和引脚组校验。PTLProbeStage 停在 mapping GPIO registers，未出现 PTLMappingLength/PADBAR，按已部署代码可确认 mapDeviceMemoryWithIndex(0) 返回空。GPIO 控制器与触摸板 HID 仍未建立。

固件 GCRS 使用 IRQ + QWordMemory 资源格式。新驱动记录原有内存资源数量；仅当数量为零时，读取并严格验证 _CRS 的 57 字节结构、内存类型、固定边界、64 KiB 对齐与长度、零转换偏移和防溢出条件，再依据固件的完整 64 位地址创建 IODeviceMemory。未猜测物理地址，未放宽 PADBAR 或布局检查。缺失内存资源是否为实际原因仍待新报告验证。

The new report passes ZIP integrity validation. PTG0/PTG1 evaluation succeeds: GPP_F has 26 pins at offset 0x800 and GPP_E has 25 at 0x9A0. Schema and pad-group validation now pass. PTLProbeStage stops at mapping GPIO registers without PTLMappingLength/PADBAR; the deployed code establishes that mapDeviceMemoryWithIndex(0) returned null. GPIO controller and touchpad HID initialization remain unresolved.

Firmware GCRS uses an IRQ plus QWordMemory resource. The new driver records the existing memory count. Only when zero, it reads and strictly validates the 57-byte _CRS structure, memory type, fixed bounds, 64 KiB alignment/length, zero translation and overflow bounds, then creates IODeviceMemory from the complete firmware-provided 64-bit address. No physical address is guessed and PADBAR/layout checks remain enforced. Whether missing published memory resources explain the null mapping still awaits the next hardware report.

macOS build and static checks passed; active EFI is backed up, deployed and verified by readback, with ocvalidate passing. Forced polling stays disabled. Hardware validation is pending. / macOS 构建与静态检查通过，已备份并写入硬盘，读回一致且 ocvalidate 通过。继续关闭强制轮询，待实机验证。

[Build / 构建](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43425427132) · SHA-256: `22a97381c2ed65ff884aa32ee2bef6b7edc1aa44ca3af62696df4ec8a35f6b0e`

## 桥接成功，继续修复平台初始化 / Resource bridge works; platform initialization repair

用户确认关闭强制轮询后触摸板完全无响应。新报告中 PTLTPDIResult / PTLGINResult 均为 0，触摸板描述符选中 GPI1、引脚 46；说明 TPDI / G_IN 本地桥接成功。但仍停在平台准备阶段，未建立 GPIO 控制器或触摸板 HID。具体退出点尚未由旧阶段属性区分，不能断言引脚组读取就是已证实根因。

The user confirms no touchpad response with forced polling disabled. The new report has PTLTPDIResult / PTLGINResult equal to zero and selects GPI1, pin 46, establishing that the local TPDI / G_IN bridge works. Platform preparation still exits without a GPIO controller or touchpad HID. The old stage properties do not identify the precise exit point; pad-group evaluation is not a proven root cause.

继续修复：为本机 GPI1 的 GPPF / GPPE 包新增 PTG0 / PTG1 本地返回方法，驱动改用这些方法读取引脚组；补充寄存器属性校验、引脚组读取和 MMIO 映射阶段、组求值返回码、组内容、映射长度与 PADBAR 诊断。没有放宽寄存器范围或布局校验。macOS 构建与静态检查通过，AML 编译零错误/警告，已备份并写入硬盘，读回一致且 ocvalidate 通过。强制轮询继续关闭，尚待实机验证。

Continuing repair: added local PTG0 / PTG1 methods returning this machine's GPI1 GPPF / GPPE packages and switched pad-group reads to these methods. Added schema/group/MMIO stages, group evaluation results and contents, mapping length and PADBAR diagnostics. Register bounds and layout validation remain enforced. macOS build/static checks and AML compilation pass; backed up and deployed with matching readback and ocvalidate passing. Forced polling remains disabled; hardware validation is pending.

[Build / 构建](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43423985735) · Binary SHA-256: `ddafbd328a6c9a5d32cb0975f6ec888f06c9f02a1d59970aff296d4fd987e9ff`

## 直接中断试验已部署 / Direct interrupt trial deployed

按用户要求，移除 `-vi2c-force-polling`，保留新 GPIO 驱动和本地 ACPI 桥接，直接进行中断启动试验。配置已备份、写入硬盘并读回校验，ocvalidate 通过。尚未启动实测；不能将触摸板有响应单独视为中断成功，需结合控制器启动、GPIO 模式和实际输入确认。失败后继续定位，不自动恢复轮询。

At the user's request, removed `-vi2c-force-polling` while retaining the new GPIO driver and local ACPI bridge for a direct interrupt boot trial. Configuration is backed up, deployed and verified by readback; ocvalidate passes. Hardware boot remains untested. Working input alone does not prove interrupts: verify controller startup, GPIO mode and actual input together. Continue diagnosis on failure without automatically restoring forced polling.

## ACPI 本地桥接修复已部署 / Local ACPI bridge repair deployed

新报告确认五个 GPIO 节点已进入启动并成功读取 `_DSD`，随后驱动用绝对路径求值 `TPDI` 返回 `0xe00002c2`（参数错误），因此提前退出。这定位到新增驱动的一处失败调用；不据此推断固件资源错误。

The new report confirms all five GPIO nodes enter startup and read `_DSD`, then the driver's absolute-path evaluation of `TPDI` returns `0xe00002c2` (bad argument), causing an early exit. This identifies a failing call in the added driver; it does not establish a firmware-resource defect.

新增并启用 `SSDT-PTL-GPIO.aml`，在各 GPIO 节点提供本地 `PTIR` / `PTGR` 方法，分别由 AML 读取根级 `TPDI`、调用固件 `G_IN`。驱动改用无参数的本地方法求值，并保留有界固件属性、路由和描述符以验证后续阶段。驱动与此 SSDT 必须配套使用。

Added and enabled `SSDT-PTL-GPIO.aml`, providing local `PTIR` / `PTGR` methods under each GPIO node. AML reads root-level `TPDI` and evaluates firmware `G_IN`; the driver calls these local methods without parameters. Bounded firmware properties, route and descriptor are retained for subsequent validation. This driver requires the accompanying SSDT.

[macOS build and static checks / macOS 构建及静态检查](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43421831586) passed. AML compiles with zero errors/warnings; active EFI readback matches the repository and ocvalidate passes. **Forced polling remains enabled. Controller startup and GPIO interrupts are not yet hardware-verified.**

构建及静态检查通过，AML 编译无错误或警告；已备份并写入硬盘，读回与仓库一致，ocvalidate 通过。**继续保留轮询，控制器启动及 GPIO 中断尚待实机验证。**

Driver SHA-256: `82b1fba6ef8d9c8aa89c19cc1748a052b4046fbb7697368d893387e114c2a45d`

下一次启动后运行现有 collect.command，先确认 PTLTPDIResult / PTLGINResult 与控制器启动，再决定切换中断。 / After the next boot, use the existing collector to check evaluation results and controller startup before switching to interrupts.

## 匹配调整与启动追踪版已部署 / Matching adjustment and startup trace deployed

继续适配：将新类的 IOProviderClass 对齐原有及上游 GPIO personalities 使用的 `IOService`；这是一项待实测的匹配调整，未证明是此前失败的根因。类内部仍严格要求 IOACPIPlatformDevice，并验证 Panther Lake 固件属性与触摸板资源来源。

Continuing implementation: the new class uses `IOService` as IOProviderClass, matching the existing/upstream GPIO personalities. This adjustment remains unverified on hardware and is not established as the previous failure's cause. The implementation still requires an IOACPIPlatformDevice internally and validates the Panther Lake firmware schema and touchpad resource source.

新增 probe/start 入口日志，并把 `PTLProbeStage`、`PTLDSDResult`、`PTLTPDIResult`、`PTLGINResult` 和 `PTLTouchpadSelected` 写到提供者 GPIO 节点。这样即使驱动对象启动失败，已有 GPI0–GPI5 采集仍能保留阶段及返回码。属性仅为内存中的诊断信息，不写 ACPI 固件或磁盘密码。

Added probe/start logs and provider-node properties `PTLProbeStage`, `PTLDSDResult`, `PTLTPDIResult`, `PTLGINResult`, and `PTLTouchpadSelected`. The existing GPI0–GPI5 collector can therefore retain stages and return codes even when driver startup fails. These are in-memory diagnostic properties, not firmware writes or password storage.

[构建和静态检查成功 / Build and checks passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43420006899)。已备份并替换硬盘 GPIO 驱动，读回与仓库一致，ocvalidate 通过。**保留强制轮询参数**，先验证新控制器能否启动，避免重复造成触摸板无响应。此次不是原驱动回退；当前使用新编译的匹配/追踪版本。尚未启动实测，GPIO 中断仍未修复。

The new driver is backed up and deployed in the active EFI, with repository/readback agreement and ocvalidate passing. **Forced polling remains enabled** while testing controller startup, to avoid repeating the no-input condition. This is the newly compiled matching/trace version, not the original rollback driver. Hardware boot remains untested and GPIO interrupts remain unresolved.

Binary SHA-256: `f7e6c45c9c2fd1140011549d8b53d6a35a90d5ff64e0b7463b0ae935cfd593f8`

下次运行原采集脚本即可读取新阶段属性；无需先关闭轮询。 / Run the existing collector after the next boot to capture these properties; do not disable polling first.

## 中断试验失败，已回退 / Interrupt trial failed; polling restored

用户反馈触摸板完全无响应。新报告 ZIP 完整性通过；loaded-kext UUID 与本次构建二进制完全一致，确认加载了试验驱动。五个 GPIO ACPI 节点仍枚举，但没有成功的 Panther Lake 控制器实例或其启动日志；I2C nub 未完成注册，HID 触摸板驱动未挂载。不能据此声称中断已建立、只是流畅度问题，也无法仅凭现有日志分清匹配失败与 `_DSD` 早期返回。

The user reports no touchpad response. The report passes ZIP integrity validation; the loaded GPIO UUID exactly matches the compiled trial, confirming the intended binary was loaded. All five ACPI GPIO nodes still enumerate, but there is no successful Panther Lake controller instance or startup log. The I2C nub does not finish registering and the touchpad HID driver is absent. Interrupt setup was not established; this is not merely a smoothness issue. Current logs do not distinguish matching from an early `_DSD` return.

已保存失败版本，恢复原 GPIO 驱动、原配置与强制轮询，读回验证和 ocvalidate 通过。用户反馈的失败状态保留，不将回退后的触摸板恢复视为已经实测。源码增加启动入口、`_DSD`、`TPDI` 与 `G_IN` 返回日志供后续定位。下一诊断版必须保留轮询，先确认控制器启动再考虑中断切换；不要直接重试相同中断配置。

The failed trial is preserved locally. Original GPIO driver, configuration and forced polling are restored; readback and ocvalidate pass. Recovery after the rollback still awaits a boot, and the failed result remains recorded. Source tracing now covers start entry and `_DSD`, `TPDI`, and `G_IN` returns. Any subsequent diagnostic deployment must retain polling until controller startup is established; do not repeat the same interrupt configuration.

## 已部署实验性修复 / Experimental implementation deployed

已新增真正的 `VoodooGPIOPantherLake` 类，以固定上游源码 `44fc744d26b3e4971d6d8f0027d75c25e1388637` 为基准。每个实例使用独立的平台数据，从 BIOS `_DSD` 读取寄存器偏移、引脚组数量与尺寸，检查版本、步长、映射范围和 PADBAR，遇到不支持布局则拒绝启动。复用当前上游核心已有的 `is_offset` 支持；此前文档中“核心固定 GPI_IS”的描述仅适用于所读旧快照，不能套用于本次固定源码。

Added a real `VoodooGPIOPantherLake` class against pinned upstream `44fc744d26b3e4971d6d8f0027d75c25e1388637`. Platform data is per instance. Firmware `_DSD` supplies register offsets and group counts/sizes, with revision, stride, mapping bounds and PADBAR validation. Unsupported layouts refuse to start. This pinned core already supports `is_offset`; earlier notes about a fixed GPI_IS describe the previously reviewed snapshot and do not apply to this build.

现有 I2C 实现只寻找首个 GPIO 服务。为避免选错，本机专用适配读取运行时 `TPDI[0]`，调用 BIOS `G_IN` 生成触摸板 GPIO 描述符，只允许其资源路径指向的 GPIO 节点发布服务；其他节点不启动。未硬编码猜测触摸板引脚，也未将 GPIO 控制器 IRQ 14 当作触摸板引脚。此策略仅针对本机固件的触摸板，不提供其他 GPIO 设备的通用支持。

The existing I2C implementation selects the first GPIO service. This machine-specific implementation reads runtime `TPDI[0]`, evaluates firmware `G_IN`, and publishes only the controller named by that touchpad descriptor. Other nodes do not start. No guessed pin or substitution of controller IRQ 14 is used. This strategy targets this firmware's touchpad rather than providing general support for other GPIO devices.

[macOS 构建与全部静态检查成功 / Successful macOS build and checks](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43408608536)。源码补丁、固定 SDK 版本和构建流程均在本仓库，见 `patches/voodoogpio-pantherlake.patch` 和 `.github/workflows/gpio-build.yml`。产物检查确认为 x86_64 Mach-O kext，包含新类和运行时触摸板选择逻辑。

Binary SHA-256: `8d77b986df3625c854d69c93c2f8f477a509096a4aa8650109b8d250fc6d0cf1`

已备份原配置和原 GPIO kext，替换硬盘 EFI 中嵌套的 VoodooGPIO，移除强制轮询参数；其他驱动和 ACPI 不变。文件读回与仓库一致，ocvalidate 通过。原驱动失效签名资源已移到备份，未保留在新驱动中。硬盘另存 `OC/config-polling-fallback.plist`；Windows 本地完整回退备份含 `Restore-Polling.ps1`。这是已编译、已部署的试验版，尚未实际启动验证，不能声称中断或流畅度已修好。

Original configuration and GPIO kext are backed up. The nested GPIO driver in the active EFI is replaced and forced polling removed; other drivers and ACPI remain unchanged. Readback matches the repository and ocvalidate passes. Stale signature resources are preserved in the backup outside the new kext. The active EFI also contains `OC/config-polling-fallback.plist`; the full local Windows backup includes `Restore-Polling.ps1`. This is a compiled and deployed trial, not a hardware-validated interrupt or smoothness repair.

下次启动后先检查指针、点击、滚动，再运行现有采集脚本。需要同时看到新 GPIO 控制器启动、触摸板 `Interrupt Mode = GPIO`、输入正常，才确认切换成功。编译成功不证明实际寄存器行为、休眠恢复或中断稳定性。

After the next boot, check pointer motion, clicks and scrolling, then run the existing collector. Confirmation requires the new controller starting, touchpad `Interrupt Mode = GPIO`, and working input. Compilation does not prove register behavior, sleep/wake or interrupt stability.

## 最新实测：声明的驱动类不存在 / Latest test: declared class unavailable

最新报告 ZIP 完整性通过。五个 GPIO ACPI 节点 GPI0、GPI1、GPI3、GPI4、GPI5 均已枚举，各有 UID 与 IRQ 14 资源。启动日志五次报 `Couldn’t alloc class VoodooGPIOTigerLakeLP`（原日志使用 ASCII 撇号）。核对当前 VoodooGPIO 1.1 二进制，未找到该类名称，而其他六个 personality 的类名均存在。由配置声明、运行时分配失败和二进制检查共同确认：现有 Tiger Lake personality 与驱动二进制不一致，尚未进入有效 GPIO 控制器初始化。这比寄存器布局差异更早阻断启动。

The latest ZIP passes integrity validation. GPI0, GPI1, GPI3, GPI4 and GPI5 enumerate with UID and IRQ 14 resources. Boot logs show five failures to allocate VoodooGPIOTigerLakeLP. The current VoodooGPIO 1.1 binary lacks that class-name string, while the other six personality class names are present. The declared personality, runtime allocation failures and binary inspection together establish an inconsistent Tiger Lake personality/binary package, blocking effective controller initialization before the register-layout issue is reached.

触摸板 nub 明确报告 Polling，I2C 地址 0x2C，400 kHz，HID 描述符地址 0x20。GPIO 控制器的共享 IRQ 14 不等于触摸板引脚，更不能直接把触摸板改成 IRQ 14。现有报告未提供运行时已求值的完整 TPD0 GPIO 资源，因此触摸板 GPIO 引脚仍未确证。标准位置没有完整 Xcode，也未报告 Command Line Tools 目录；不排除其他安装路径。

The touchpad nub explicitly reports Polling, I2C address 0x2C, 400 kHz and HID descriptor address 0x20. The controller's shared IRQ 14 is not the touchpad pin and must not be substituted as its interrupt. These reports do not expose the complete evaluated TPD0 GPIO resource, so the runtime pin remains unconfirmed. Full Xcode was not found at its standard path, and no Command Line Tools directory was reported; other locations were not checked.

下一步是获取/实现与二进制一致的 Panther Lake GPIO 平台支持，并验证资源、映射、引脚与中断处理。仅补同名 Tiger Lake 类仍不解决硬件布局差异。不通过换成其他旧平台类名来强行启动。本轮只记录结果，未改 EFI、未部署新驱动，不要求重复本轮采集；中断仍未修复。

The next implementation step is a coherent Panther Lake GPIO driver with validated resources, mappings, pins and interrupt handling. Adding the missing Tiger Lake class alone does not resolve the layout mismatch. Do not force an older platform class to start. This update records evidence only, changes no EFI files and deploys no new driver. Repeating this collection is unnecessary; interrupts remain unresolved.

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
