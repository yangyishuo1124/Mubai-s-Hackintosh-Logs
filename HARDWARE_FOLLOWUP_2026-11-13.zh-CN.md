# 2026-11-13 后续诊断与修复记录

[English](HARDWARE_FOLLOWUP_2026-11-13.md) · [中英双语首页](README.md)

本文按测试顺序记录当时的现象、推断和改动；较早章节中的“未解决”可能已被后续测试更新。

## 首次反馈

- 电池使用 `SSDT-BATT-FIX-UNIT0.aml` 后显示正常，保留补丁。
- 去掉 `-vi2c-force-polling` 后触摸板失效；加回参数并重启后用户确认恢复，电池补丁保留。
- Wi-Fi 能扫描但 GUI 连接报错。用户使用 `networksetup -setairportnetwork en0 ...` 后，当时仍未取得 IP，尚不能判断关联与 DHCP 分别进展到哪里。
- Realtek 蓝牙只出现在 USB 下，当时未采到固件上传和 bluetoothd 状态。

## 在同一台笔记本上采集报告

用 `diskutil list` 找到约 467 MB、标签 SYSTEM 的 EFI 分区，以实际编号替换 `diskXs1`：

```sh
sudo diskutil mount diskXs1
sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/collect.command
sudo diskutil unmount /Volumes/SYSTEM
```

报告保存在 `EFI/Diagnostics/reports/`，重启 Windows 后可直接读取。原始报告可能含网络名、MAC、硬件标识，不上传仓库。

当时用于排除 DHCP 未启动的命令如下；这只是诊断手段，不是已证实的根因或修复：

```sh
ifconfig en0
ipconfig getifaddr en0
sudo ifconfig en0 up
sudo ipconfig set en0 DHCP
sleep 10
ipconfig getifaddr en0
ipconfig getpacket en0
```

[AirPort_RTW89 移植记录](https://github.com/FranciumOS-org/Airport_RTW89/blob/main/docs/PORTING.md) 提到过网络服务未创建、需手动启动 DHCP 的情况，但本机仍须用报告验证。[蓝牙驱动安装说明](https://github.com/thegwchr/RealtekBluetoothFirmware/blob/main/docs/Installation.md) 建议通过 RealtekFirmware 日志区分未匹配与固件上传成功；上传成功后继续查 bluetoothd 和 BlueToolFixup。

## 第一份报告：自动连接已能上网

触摸板轮询恢复。en0 已关联 WPA2 网络，取得 IPv4、DHCP ACK、DNS 和默认路由。用户没有手动运行 DHCP 命令，确认可以打开网页，但 GUI 切换其他网络仍失败。因此不能认定为持续 DHCP 故障；保存密码可能使自动连接走通。

两个蓝牙补丁已加载，但没有可用控制器。最初脚本误调用 zsh 的 log 内建命令，修正为 `/usr/bin/log`，并加入 USB IORegistry 和网络 ping，将报告打为 ZIP。

首次 macOS 写入后的 FAT32 报告目录确有损坏。先保存 EFI 原始镜像，再修复文件系统；Windows 随后报告健康，config.plist 校验值不变。之后要求重启前干净卸载 EFI 分区。

## 第二份报告：Wi-Fi 失败在握手，蓝牙固件已上传

已保存的 WPA2 网络完成四次握手并拿到 DHCP。GUI 连接其他网络时，关联成功，收到路由器 EAPOL M1，回复 M2 且对端确认收到，但没有 M3，最终路由器以原因码 15 断开，驱动报 `-2015`。失败发生在 DHCP 之前。

用户澄清：目前可用的 5 GHz 网络原先也有完全相同的失败，命令行保存密码并重启后才可用。因此方向是首次连接与已保存凭据路径的区别，不能归因于 2.4 GHz；具体密钥传递问题尚未证明，也不能认定用户密码错误。

USB IORegistry 中 `0BDA:B85B` 显示为 Bluetooth USB Host Controller，`FirmwareLoaded = Yes`、设备类别 0xE0。RealtekBluetoothFirmware 1.0.2 和 BlueToolFixup 2.7.2 已加载，但无 IOBluetoothHostController；蓝牙系统概述查询会卡住。问题转向控制器初始化。日志筛选改为按 bluetoothd 进程选择，跳过会卡住的查询，并采集内核消息。

## 第三份报告：等待 IOKit 就绪

rtl8852bu 固件上传成功，固件服务 busy 0。bluetoothd 最后一条初始化消息是 `Waiting for IOKitWaitQuiet()`，没有完成消息。按 [Apple 文档](https://developer.apple.com/documentation/iokit/1514440-iokitwaitquiet)，该调用等待所有 IOService 的 busy 状态归零，因此其他设备也可能阻塞蓝牙。

工具加入完整设备树、非零 busy 条目、三秒进程采样和 launchd 状态；不重启服务、不改启动配置。刷新 Windows 挂载后 ZIP 完整，文件系统检查未发现新错误，不能仅凭一次读取失败就判定 FAT 再次损坏。

## 第四份报告：进程采样确认等待

三秒采样全在 `IOKitWaitQuiet → io_service_wait_quiet → mach_msg2_trap`。两份设备树中 CP01–CP15 的 AppleACPICPU 连续 busy 约 297 秒，CP00 已空闲。这证明有初始化状态阻塞，不代表处理器硬件故障、核心不可用或性能异常，用户也报告 CPU 正常。

MADT 有 16 个启用的 Local APIC，通用 PLUG 表声明 64 个 Processor 对象。这个差异值得核查，但不足以认定是原因；当时没有修改 CPU 拓扑、MADT、供电或启动参数。工具加入 macOS 核心数量和详细 CPU 属性采集。

## 第五份报告与 MCE 匹配规则试验

macOS 显示 16 个物理/逻辑核心全部在线，每个 AppleACPICPU 都是 Running，支持用户对 CPU 正常的观察；但 CP01–CP15 的 IOKit busy 状态仍在。

原无二进制的 MCEReporterDisabler 有两条匹配规则：高优先级的空 IOService，以及将真实 AppleMCEReporter 加载到 AppleACPICPU 上的额外规则。报告确认真实 AppleIntelMCEReporter 已加载，CP00 挂着空屏蔽服务，其他 CPU 服务未完成匹配。这是具体疑点，试验前尚非已证明根因。

备份 OC 和 BOOT 后，只从 MCEReporterDisabler 的 Info.plist 删除额外的 AppleMCEReporter 规则，保留 Disabler。CPU 定义、核心数、MADT、供电、启动参数与 config.plist 都未改变。当时标记为待启动验证；若回归，可从本地 `before-mce-match-test-*` 备份恢复 Info.plist。

## SimpleHDA 首轮音频试验

按用户要求下载 [SimpleHDA 1.0.1 RELEASE](https://github.com/laobamac/SimpleHDA/releases/tag/v1.0.1)，全部文件通过包内 SHA256.json 校验。备份当前 EFI 后，启用 AppleALC 1.9.8，再加载 SimpleHDA；现有 Lilu 1.7.2 和 DisableLinkeditJettison 满足要求。SimpleHDA 限制在 Darwin 25.x，首次以 `alcid=3` 测试，此时未加控制器 ID 或类别伪装。layout 3 是 ALC235 支持的候选，尚非本机验证布局。

未安装可选 HAL 包，上游支持普通 IOAudio 路径。本轮不改 macOS 系统卷；前一轮 MCE 试验当时也还待验证。

### 复测：蓝牙恢复，音频尚未识别

用户确认蓝牙可用。报告中非零 busy 条目清空，bluetoothd 完成 IOKitWaitQuiet 并启动控制器，保留 MCE 规则修改。SimpleHDA 与 AppleALC 已加载，但没有 HDA codec 或 IOAudio 设备。控制器改名 HDEF，工具补采 HDAS 和 HDEF。单有驱动加载通知不能证明成功挂载设备。

下一轮在 `PciRoot(0x0)/Pci(0x1F,0x3)` 注入兼容 ID `ca510000`（8086:51CA），保留 layout 3 和 SimpleHDA。[Meteor Lake 项目](https://github.com/VedCloud/Meteor-Lake-Xe-LPG-Metal-Graphics) 有使用该 ID 的记录，但当时未验证适用于 Panther Lake E328。未改 PCI 类别，因为恢复的控制器驱动匹配规则已覆盖相关两类。修改前配置保存在本地 `before-audio-controller-trial-*`。

Wi-Fi 仍是自动连接能完成握手，GUI 新连接在 DHCP 前失败；当时最新上游版本仍为 0.6.0-BETA。新增 `wifi-direct.command` 通过 rtw89ctl 的隐藏密码提示直连，再请求 DHCP。这只是未验证的绕过手段，并非 GUI 修复，密码不嵌入脚本。

### 最新复测：音频设备已出现，修正 Wi-Fi 对照测试

用户报告音频设备出现。报告有 `0x10EC0235` 的 IOHDACodecDevice 和发布 Built-in Audio 的 AppleHDADriver，保留 SimpleHDA、AppleALC、layout 3 和兼容 ID。扬声器播放、耳机输出与麦克风录音仍待分别确认；蓝牙恢复已由用户确认。

两次 Wi-Fi 直连均以 `-16`（EBUSY）返回，尚未开始新的关联/握手。旧网络仍连接，有 DHCP 地址，网关 ping 成功。因此不能用这次结果比较 GUI 与驱动的密码处理。

第一版脚本漏了断开旧网络；已改成关闭驱动自动重连、执行 leave、短暂等待后 join。测试时关闭 Wi-Fi 菜单和系统设置，减少并发扫描。成功或失败都会自动采集报告。密码仍只输入到 rtw89ctl 的隐藏提示中。本次只修改辅助脚本，没有改启动配置或音频/蓝牙驱动，GUI 首次连接仍未修复。

这次 ZIP 在重新挂载 Windows EFI 分区后通过完整性检查，无需文件系统修复。原始报告及私人网络标识不上传。

## 当前复测与回退

在“声音”中检查输入输出；若有设备，低音量分别测试扬声器、耳机口和麦克风，再运行采集工具。工具记录设备、codec、控制器及 coreaudiod / AppleHDA / SimpleHDA 日志。仅驱动加载不算音频功能通过。

若需完全退回 SimpleHDA 前配置，恢复本地 `before-simplehda-*` 中的 config.plist；即使新 kext 目录还在，该备份也不会启用 SimpleHDA 或 AppleALC。只撤销兼容 ID 时使用更近的 `before-audio-controller-trial-*` 配置备份。
