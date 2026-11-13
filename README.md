# ASUS Vivobook S16 S5650AA · Panther Lake Hackintosh

核显实验更新 / GPU experiment update: 不读取像素的 GOP 检查已实机通过：布局/PTE 一致、帧计数前进 18；CPU 显存访问继续阻断，stage 2 仍未完成，Metal 未可用。 / Pixel-free GOP checks pass on hardware: stable layout/PTEs and frame delta 18. CPU framebuffer access remains blocked; stage 2 is incomplete and Metal is unavailable. See [GPU investigation / 核显调查](GPU_PANTHER_LAKE.md).

**简体中文 / English** · 更新 / Updated: **2026-11-13**

这是我的 ASUS Vivobook S16 S5650AA 黑苹果适配记录与 OpenCore EFI。macOS Tahoe 26.0 已能进入桌面，显示使用 UEFI GOP 基础帧缓冲，尚无硬件图形加速。

My OpenCore EFI and adaptation logs for the ASUS Vivobook S16 S5650AA. macOS Tahoe 26.0 boots to the desktop using the UEFI GOP basic framebuffer. Hardware graphics acceleration is not available in this setup.

## 硬件与当前状态 / Hardware and current status

| 项目 / Component | 硬件 / Hardware | 当前状态 / Current status |
| :--- | :--- | :--- |
| 机型 / Model | ASUS Vivobook S16 S5650AA | 本仓库测试机 / Machine tested here |
| 处理器 / CPU | Core Ultra 7 356H, Panther Lake, 16C/16T | 16 核在线；Comet Lake CPUID 伪装 / All 16 cores online; Comet Lake CPUID spoof |
| 显卡 / GPU | Intel Arc, PCI `8086:B0A0` | GOP 桌面；无 Metal 加速 / GOP desktop; no Metal acceleration |
| 内存 / Memory | 32 GB LPDDR5X 7467 MT/s | 可用 / Working |
| 屏幕 / Display | 16-inch 3200×2000 OLED, panel rated 120 Hz | 原生分辨率 GOP；macOS 刷新率未确认 / Native-resolution GOP; macOS refresh rate unverified |
| 主硬盘 / Primary SSD | RS1D0TSSD710 1 TB NVMe | APFS 系统可启动 / Boots APFS system |
| 副硬盘 / Secondary SSD | Samsung PM981 256 GB | EFI 含禁用补丁，当前未启用 / Disable SSDT included but currently disabled |
| 键盘 / Keyboard | Built-in PS/2 | VoodooPS2Keyboard 可用 / Working |
| 触摸板 / Touchpad | TZY4E41, I²C TPD0 | GPIO 中断模式及输入已实测成功；休眠与长期稳定性待验证 / GPIO mode and input confirmed; sleep/wake and long-term stability pending |
| USB | Intel xHCI / Type-C | 已有设备可用；端口未全面验证 / Devices work; not all ports qualified |
| 电池 / Battery | Internal battery | 电量显示已修正，用户确认正常 / Percentage corrected and user-confirmed |
| 音频 / Audio | ALC235 + Intel SST `8086:E328` | 已识别内置音频；播放与录音待分别确认 / Built-in audio detected; playback/capture checks pending |
| Wi-Fi | RTL8852BE `10EC:B852` | 同轮对照：同一接入点 GUI 握手失败，驱动密码直连可上网；GUI 待修复 / Same-run comparison: GUI handshake fails, direct-password join to the same AP has working Internet; GUI unresolved |
| 蓝牙 / Bluetooth | Realtek USB `0BDA:B85B` | 用户确认恢复；配件未全面测试 / User-confirmed recovery; accessory coverage incomplete |

## 已保留的改动 / Retained changes

- **CPU / ACPI**：`APIC-legacy.aml` 将固件 x2APIC 转为传统 Local APIC，配合 `SSDT-PLUG-ALT.aml`、CPUID `0x0A0655`、`ProvideCurrentCpuInfo` 和 XCPM 配置。macOS 报告 16 核在线；通用 PLUG 表本身声明 64 个 Processor 对象。
  **CPU / ACPI:** Converted x2APIC MADT to legacy Local APIC, with SSDT-PLUG-ALT, CPUID `0x0A0655`, ProvideCurrentCpuInfo and XCPM settings. macOS reports 16 online cores; the generic PLUG table declares 64 Processor objects.
- **电池**：保留 `SSDT-BATT-FIX-UNIT0.aml`，纠正 `_BIF` / `_BIX` 电量单位。
  **Battery:** Retain the `_BIF` / `_BIX` unit correction in SSDT-BATT-FIX-UNIT0.
- **触摸板**：固件资源桥接与 64 位内存资源兼容修复后，已实测 GPIO 中断模式、GPI1 引脚 46，用户确认输入恢复；未恢复强制轮询。休眠及长期稳定性待验证。详见 [GPIO 记录](TOUCHPAD_GPIO.md)。
  **Touchpad:** Firmware resource bridges and 64-bit memory-resource compatibility now give confirmed GPIO mode on GPI1 pin 46 with user-confirmed input. Forced polling remains disabled. Sleep/wake and long-term stability remain unverified. See the [GPIO record](TOUCHPAD_GPIO.md).
- **蓝牙**：RealtekBluetoothFirmware 1.0.2 + BlueToolFixup 2.7.2。移除 MCEReporterDisabler 中额外加载真实 AppleMCEReporter 的规则后，busy 状态清零，bluetoothd 通过 IOKitWaitQuiet 并启动控制器。
  **Bluetooth:** Removing the extra real AppleMCEReporter personality cleared busy services and allowed bluetoothd to pass IOKitWaitQuiet and start its controller, with RealtekBluetoothFirmware 1.0.2 and BlueToolFixup 2.7.2.
- **音频**：[SimpleHDA 1.0.1](https://github.com/laobamac/SimpleHDA) + AppleALC 1.9.8，`alcid=3`，控制器兼容 ID `8086:51CA`（`ca510000`）。ALC235 和 AppleHDADriver 已枚举；未改系统卷，未安装可选 HAL 包。
  **Audio:** SimpleHDA 1.0.1 + AppleALC 1.9.8, `alcid=3`, controller compatibility ID `8086:51CA` (`ca510000`). ALC235 and AppleHDADriver enumerate. No system-volume changes or optional HAL installation.
- **Wi-Fi**：[AirPort_RTW89 0.6.0 Beta](https://github.com/FranciumOS-org/Airport_RTW89)。GUI 失败停在 WPA2 M2 后，未收到 M3，原因码 15 / 错误 `-2015`，发生于 DHCP 之前。频段原因未成立。
  **Wi-Fi:** GUI failures stop after WPA2 M2 with no M3, followed by reason 15 / error `-2015`, before DHCP. A frequency-band cause has not been established.

## 核显驱动调查 / GPU driver investigation

包含 B0A0 的实验性裸机 xe 驱动已完整构建并通过复核；EFI 开机加载和 stage 1 已实测成功；stage 2 返回 -22，DSMBASE MMIO 修订版探测触发黑屏重启，已停止重复探测并增强崩溃采集，尚无加速。当前桌面仍为 GOP。源码、验证阶段和限制见 [Panther Lake 核显记录](GPU_PANTHER_LAKE.md)。

The experimental bare-metal xe fork containing B0A0 now builds and passes verification. EFI boot loading and stage 1 are confirmed. Stage 2 returned -22; the DSMBASE MMIO probe caused a black-screen reboot, so repeat probing is disabled while crash evidence is collected; no acceleration yet. The desktop still uses GOP. See the [Panther Lake GPU record](GPU_PANTHER_LAKE.md) for sources, stages and limits.

## 下次 Wi-Fi 测试 / Next Wi-Fi test

**最新结果：**已完成同轮同接入点对照，GUI 两次 M2 超时，驱动密码直连随后完成握手、取得 IP 且公网 ping 3/3 成功。直接连接目前可作绕过方案；GUI 尚未修复。先前五秒掉线在这次未重现，但不能单凭一次结果证明其原因。

**Latest result:** The same-run, same-AP comparison is complete: two GUI M2 timeouts followed by successful direct-password authentication, IPv4 and 3/3 public-IP pings. Direct joining is now an observed workaround; GUI joining is not fixed. The earlier five-second drop did not recur, which alone does not establish its cause.

脚本先断开旧连接以避免此前的 `-16`（EBUSY），并已移除强制 DHCP。最新同轮对照中，被动观察版本直连此前 GUI 失败的目标后保持连接并通过公网测试。GUI 尚未修复；以下保留直连方法供参考，不必重复相同测试。

The helper first leaves the old link to avoid the earlier `-16` (EBUSY), and no longer forces DHCP. In the latest same-run comparison, this passive version remains connected to the previously GUI-failing target and passes public-IP pings. GUI joining remains unresolved; the direct-join procedure below is retained for reference, without requiring repeated identical tests.

先在 Wi-Fi 设置中临时关闭**旧的已保存网络**的“自动加入”，不必忘记网络，测试后可恢复。用 `diskutil list` 找到约 467 MB、名为 SYSTEM 的 EFI 分区，替换 `diskXs1`。按脚本提示操作，并关闭 Wi-Fi 菜单和设置窗口：

Temporarily disable **Auto-Join for the old saved network** in Wi-Fi settings; do not forget it, and restore Auto-Join after testing if desired. Use `diskutil list` to identify the approximately 467 MB SYSTEM EFI partition and replace `diskXs1`. Follow the script prompts and close the Wi-Fi menu and System Settings:

```sh
sudo diskutil mount diskXs1
sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/wifi-direct.command
sudo diskutil unmount /Volumes/SYSTEM
```

按提示在本机输入网络名和密码。脚本不保存密码，成功或失败都会自动采集报告。只需诊断时，挂载后运行：

Enter the network name and password locally. The wrapper does not store the password and collects a report on success or failure. To collect diagnostics only, run after mounting:

```sh
sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/collect.command
sudo diskutil unmount /Volumes/SYSTEM
```

报告位于 `EFI/Diagnostics/reports/`，可能含网络名、MAC 和硬件标识。原始报告留在本地，不提交 GitHub。

Reports under `EFI/Diagnostics/reports/` may contain network names, MAC addresses and hardware identifiers. Raw reports remain local and are not committed to GitHub.

## 只读凭据检查 / Read-only credential check

为区分保存密码差异与系统/驱动交接问题，新增 `wifi-credential-check.command`。挂载 SYSTEM 后，在已登录的 macOS 用户终端运行，**这一条不用 sudo**：

To distinguish a saved-password discrepancy from a system/driver handoff problem, run the new helper in the logged-in macOS user's Terminal after mounting SYSTEM. **Do not use sudo for this command**:

```sh
bash /Volumes/SYSTEM/EFI/Diagnostics/wifi-credential-check.command
```

输入目标网络名和已直连成功的密码（隐藏输入）。脚本仅在内存中比较登录/系统钥匙串各自查询到的一条匹配记录；密码不会显示、写文件、计算散列或上传。若弹出系统访问确认，可选本次“允许”，不必选“始终允许”。不改连接、网络配置、密码或钥匙串访问规则。

Enter the target network name and the password that worked with direct joining (hidden input). The helper compares one matching item from each of the login/system keychains in memory. Passwords are never displayed, written to files, hashed or uploaded. If macOS requests access, a one-time Allow is sufficient; Always Allow is unnecessary. The script does not change connections, network settings, passwords or keychain access rules.

结果保存在 `EFI/Diagnostics/reports/wifi-credentials-*.txt`，仅含状态：`MATCH` 一致、`DIFFERENT` 不同、`NOT_FOUND` 本次查询未找到、`UNREADABLE` 无法读取、`KEYCHAIN_UNAVAILABLE` 路径不可用。不同不证明 airportd 实际用了该记录；一致不证明传给驱动的 PMK 正确；未找到/无法读取也不能说明系统没保存密码。其他钥匙串、重复记录及受保护存储未枚举。已过语法及五类模拟分支检查，尚未在 macOS 实测；这是诊断工具，不是修复。

Only result labels are saved in `EFI/Diagnostics/reports/wifi-credentials-*.txt`: `MATCH`, `DIFFERENT`, `NOT_FOUND`, `UNREADABLE`, or `KEYCHAIN_UNAVAILABLE`. A discrepancy does not prove airportd used that item, a match does not validate the PMK passed to the driver, and missing/unreadable results do not establish an absent saved password. Other keychains, duplicate records and protected stores are not enumerated. Syntax and five mocked branches pass; macOS integration is untested. This is a diagnostic tool, not a repair.

## 使用与回退 / Use and rollback

这是本机测试 EFI，不保证其他机器可用。替换前备份 EFI 并保留可启动恢复介质。配置包含机器身份字段，其他使用者需生成自己的 SMBIOS 标识。

This EFI is tested on this laptop; other machines are unverified. Back up your EFI and keep bootable recovery media. The configuration includes machine identity fields; other users must generate their own SMBIOS identifiers.

将 `EFI/BOOT` 和 `EFI/OC` 放到目标 EFI 分区，通过 OpenCore 启动。必要时按空格显示辅助工具。跨系统重启后设备异常时，可尝试完全关机再启动。发生回归时恢复对应本地备份。

Copy `EFI/BOOT` and `EFI/OC` to the target EFI partition and boot through OpenCore. Press Space to show auxiliary tools when needed. A full shutdown and cold boot may help device state after switching operating systems. Restore the corresponding local backup if a change regresses operation.

更新流程：检查硬盘 EFI → 本地备份 → 修改 → 读回校验、配置检查 → 同步实际文件到 GitHub。文件校验与实机功能验证分别记录。

Update workflow: inspect active EFI → back up locally → modify → read back and validate → sync actual files to GitHub. File validation and device operation are recorded separately.

## 测试记录 / Test records

| 记录 / Record | 中文 | English |
| :--- | :--- | :--- |
| 首轮测试（历史） / Initial test (historical) | [硬件测试](HARDWARE_TEST_2026-11-13.zh-CN.md) | [Hardware test](HARDWARE_TEST_2026-11-13.md) |
| 后续诊断与修复 / Follow-up | [后续记录](HARDWARE_FOLLOWUP_2026-11-13.zh-CN.md) | [Follow-up](HARDWARE_FOLLOWUP_2026-11-13.md) |

历史章节保留当时判断；最新状态以本页和后续记录末尾为准。第三方说明与许可证保留原文，见 `third_party/`。

Historical sections retain the conclusions at that time. Use this page and the latest follow-up entries for current status. Upstream notices and licenses remain unchanged under `third_party/`.

## 致谢 / Credits

[Acidanthera](https://github.com/acidanthera)、[Dortania](https://dortania.github.io/)、[FranciumOS](https://github.com/FranciumOS-org/Airport_RTW89)、[SimpleHDA](https://github.com/laobamac/SimpleHDA)、[RealtekBluetoothFirmware](https://github.com/thegwchr/RealtekBluetoothFirmware)、[Lem's Hardware Lab](https://github.com/lems-hardware/lhl-hackintosh-docs)，以及老吴黑苹果工作室的初始参考环境。

Thanks to the projects above and 老吴黑苹果工作室 for the initial reference environment.
