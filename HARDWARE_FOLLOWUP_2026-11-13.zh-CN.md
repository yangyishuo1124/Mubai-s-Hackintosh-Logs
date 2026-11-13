# 2026-11-13 后续诊断与修复记录

[English](HARDWARE_FOLLOWUP_2026-11-13.md) · [中英双语首页](README.md)

## 触摸板 GPIO：发现平台布局不匹配

详见 [GPIO 调查](TOUCHPAD_GPIO.md)。现有 INTC10BB 被加入 Tiger Lake 匹配列表，但 BIOS 寄存器偏移不匹配；尚未修复中断。只增强诊断采集，保留当前可用轮询，未修改配置或驱动。

## 只读凭据检查实测：两处查询均未找到

用户运行新增比较脚本后，报告显示 `LOGIN: NOT_FOUND`、`SYSTEM: NOT_FOUND`。这仅说明按目标账户名和 AirPort network password 类型查询传统登录/系统钥匙串时未找到匹配项；没有取得密码，也没有执行实际密码比较。不能据此断言密码未保存、密码正确/错误、钥匙串损坏或凭据因素已排除。其他存储、记录属性或重复项未枚举。检查未修改网络、钥匙串、驱动或启动配置，GUI 问题仍未修复。

不继续重复相同检查，也不据此清空网络配置。现有日志无法验证 GUI 交给驱动的实际 PMK；进一步区分系统凭据交接与驱动处理，需要针对该边界的新观测，而非继续从握手超时猜测责任。诊断驱动可以提供观测，但需要构建和单独实机验证，尚未部署。

## 凭据与密钥生命周期核查：新增只读比较工具

沿 `decodeHostAssoc → nativeAssociate → glue_join_request → mlme_connect` 核查本地上游 `76d23fe`：GUI 的 PMK 进入公共连接路径，直连先自行派生 PMK 后进入同一路径；`glue.want.pmk` 和 `mlme.pmk` 在返回前同步复制，因此未发现“请求返回清空临时缓冲区就破坏当前握手密钥”的直接证据。两次 GUI 与直连的无线日志均标为 WPA2，未见本次选择不同 AKM 的日志证据。此静态结论不验证原始 PMK 内容、解码偏移或并发行为。

故障窗口未见能证明读取 Wi-Fi 密码失败的日志。开机阶段 WiFiAgent 未就绪的钥匙串信息、Captive Portal 网页认证凭据未找到，不能当作目标 Wi-Fi 密码损坏的证据。私有 MAC 创建在请求开始时成功，失败结束后对空网络的 EINVAL 也不足以证明它导致握手失败。不清理全局网络配置或钥匙串。

新增只读 `wifi-credential-check.command`，隐藏输入已验证密码，在内存中与登录/系统钥匙串各自一条匹配项比较，仅记录状态。无连接操作、密码写入、密钥字节/散列输出。重复项、其他存储与机场进程实际选择仍不可由此确认；MATCH 不验证驱动收到的 PMK，DIFFERENT 仅提出保存记录差异的线索，读取受限视为未知。使用方式和结果限制见双语首页。语法和五类模拟分支通过，尚未在 macOS 实测。仅添加诊断文件，启动配置和驱动不变，GUI 尚未修复。

## 同轮 GUI / 驱动直连对照完成

最新报告在同次启动中记录两次 GUI/native WPA2 连接：同一接入点均收到 M1、回复 M2 且路由器确认收到，随后路由器原因码 15 断开，驱动报 -2015。之后一次密码直连指向完全相同的 BSSID 和频道，成功安装密钥、native link up，采集时保持连接、有 IPv4，公网 ping 3/3 通过。标识仅在本地比对，不公开；ZIP 完整性检查通过。

这证明此前 GUI 失败的目标可以通过驱动密码直连上网，可作已观察到的绕过方案，排查范围收窄到 native 关联请求、凭据和状态处理的差异。但仍不能证明传入 PMK 字节错误或解码偏移有误，也可能涉及请求标志、RSN 或状态差异。两次 GUI 请求都实际执行连接并在下一次请求前失败，因此本次日志不支持“重复请求快捷分支吞掉请求”是原因，不应将此前代码疑点认定为根因或部署猜测性修复。

脚本已不再强制 DHCP，本轮没有重现五秒掉线；这种时间相关性仍不足以证明此前就是 DHCP 命令导致。仅有 IPv4 不能证明新租约，但链路持续连接和通信成功已证明当前可用。本轮不改启动配置、驱动或辅助脚本，只更新双语文档，不要求额外测试。

## 源码核查与被动观察地址

检查本地上游快照 `76d23fe` 的 POWER、DISASSOCIATE、ASSOCIATE、CIPHER_KEY 处理及外部 PMK 更新路径。native DISASSOCIATE 在非连接过程中会直接调用 glue_leave；核心以太网接口 enable/disable 只控制输出线程，单凭它们不能解释无线离网。断开附近的 POWER-on 日志也不足以指出随后由谁请求离网。由于没有捕获原始请求和调用栈，仍不能宣称已还原完整调用链。

关联请求解码器按 cipher 字段区分 PMK 与密码，GUI 的 WPA2 PMK 路径和驱动从密码派生密钥的路径不同。后到的 PMK 更新只接受外部认证连接，检查密钥时序时应考虑此限制，但现有日志没有证明本机发生了该分支相关的晚到密钥。尚不能认定密钥内容有错或解码偏移错误。

已移除脚本中强制执行的 `ipconfig set en0 DHCP`，避免观察时主动重配置接口。握手成功后最多被动观察 20 秒，将链路断开（退出码 2）与没有 IPv4（退出码 3）区分，仍自动采集报告；已有 IPv4 不被称作新租约。备份、写入并读回校验后，仅辅助脚本改变，config.plist、驱动、音频和蓝牙保持原样。脚本语法与仓库空白检查通过，macOS 运行效果未验证。本阶段不要求再次重启测试，也不宣称 GUI 已修复。

## 最新目标测试：认证成功，随后链路断开

新报告的驱动直连目标，与此前 GUI 在 M2 后超时的接入点一致（在本地按 BSSID 比对，不公开标识）。本次关联、WPA2 密钥安装及 native link up 均成功，说明密码直连可以完成该目标的认证，证据不再仅限于先前可用的旧接入点。但本次驱动环形日志没有同轮新的 GUI 失败，因此仍是跨报告比较，不是严格的同轮 A/B 对照。

约 5.1 秒后，驱动记录 macOS 的 Wi-Fi 开启操作、MLME 主动离网和 native link down。最终接口 inactive，没有 IPv4 或 DHCP 报文，公网 ping 失败；该次断开未记录路由器发来的 deauthentication。时间紧邻脚本等待五秒后执行 `ipconfig set en0 DHCP` 的阶段，系统日志也有 iff_up 和 DHCP media inactive。因此接口重配置/重置是认证后掉线的具体疑点，但还不能证明是 DHCP 命令导致。

需分开排查 GUI 密钥交接/状态，以及直连后的接口处理。握手成功不等于可以上网，也不能单凭它证明 PMK 解码错误。本轮仅更新双语文档，不改 EFI 或脚本、不要求新增测试。原始标识和报告保留本地，ZIP 完整性检查通过。

## 最新报告：驱动密码直连成功

新报告捕获到驱动直连请求，随后关联成功、WPA2 握手完成，未再出现 EBUSY。后续采集时有 IPv4 地址，网关与公网 IP 的 ping 各 3/3 成功。这验证了直连脚本及该接入点上的密码直连路径。单凭 IP 地址不能判断是否新发放了租约，但连接后的通信已由 ping 独立证明。

需保留的限制：直连成功的接入点与本次启动早先自动连接的接入点相同；报告没有该目标对应的一次新 GUI 失败。因此不能据此证明 GUI 的 PMK 解析有错，也不能保证直连能解决所有此前失败的网络。密钥传递/状态与目标选择仍是 GUI 故障的候选方向。本轮不要求继续测试、不改 EFI 或脚本，只更新双语公开记录。原始 ZIP 完整性检查通过并留在本地。

## 上游 issue 核查（2026-11-13；暂停测试）

- [Issue #2](https://github.com/FranciumOS-org/AirPort_RTW89/issues/2)：另一位 RTL8852BE 用户在 Ventura 下报告正确密码也无法连接 WPA2。维护者要求更新版本并提供日志；没有已验证修复，也没有对应的 M2/M3 证据。同卡和相似表现不能证明同一根因。
- [Issue #4](https://github.com/FranciumOS-org/AirPort_RTW89/issues/4) 与 [PR #5](https://github.com/FranciumOS-org/AirPort_RTW89/pull/5)：Sonoma 的 856 字节关联请求未被解码，维护者称 0.5.0 已修复。该错误发生在无线关联之前；本机 Tahoe 已进入 WPA2 M2，失败阶段不同。
- [Issue #7](https://github.com/FranciumOS-org/AirPort_RTW89/issues/7) 与未合并的 [PR #16](https://github.com/FranciumOS-org/AirPort_RTW89/pull/16)：上游确有定向扫描结果交付、旧 BSSID 缓存选择与热点重试问题。因此静态排查应同时核查目标选择和密钥处理，但现有证据不能认定这是本机原因；扫描补丁不等于已验证的 M2/M3 修复。
- [Issue #17](https://github.com/FranciumOS-org/AirPort_RTW89/issues/17)：RTL8852CE 首次热点连接失败，USB 共享网络后可连，且列表不同步。网卡和操作路径不同，所查讨论中没有明确修复。

本轮未找到“保存密码后重启自动连接可用、GUI 首次连接在 M2 后失败”的完整同症状已验证方案。PMK 传递、解析和状态仍是待证实假设；扫描缓存与目标选择是值得静态核查的另一方向。本轮不改 EFI、驱动或测试脚本，也未向上游发 issue 或评论。

## 最新直连复测：macOS 自动连接抢先占用网卡

新报告显示，macOS 自动连回旧的已保存网络并完成 WPA2 握手，约五秒后直连命令返回 `-16`（EBUSY）。旧网络已取得 DHCP 地址，网关与公网 IP 的 ping 均通过。因此还没测到目标网络的密码握手，不能把这次结果算作新的认证失败。驱动的 `rejoin off` 只控制驱动自身重连，不会关闭 macOS 的已保存网络自动加入。

脚本现要求先临时关闭旧网络的“自动加入”，不删除已保存密码；执行 leave 后检查连接是否仍已断开。若 macOS 抢先连回，停止测试并采集证据，避免无效对照。测试后可恢复自动加入。这是测试流程纠正，不是 GUI Wi-Fi 修复。本轮只改辅助脚本，保留现有音频、蓝牙和启动配置；ZIP 完整性检查通过，原始报告不提交。

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
