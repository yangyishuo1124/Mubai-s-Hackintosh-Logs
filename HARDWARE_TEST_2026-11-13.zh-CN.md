# 2026-11-13 首轮 EFI 更新后的硬件测试

[English](HARDWARE_TEST_2026-11-13.md) · [中英双语首页](README.md)

> 本文是首轮测试方案的历史记录，不代表当前状态。后续已确认电池正常、触摸板轮询恢复、蓝牙恢复、音频设备出现；Wi-Fi GUI 首次连接仍未解决。详见[后续记录](HARDWARE_FOLLOWUP_2026-11-13.zh-CN.md)。

内部 EFI 分区已写入当次提交中的文件，写入前已在本地备份旧版可用 EFI。所有变更文件均读回并比对 SHA-256，OpenCore 1.0.8 的 ocvalidate 检查通过。该阶段尚未验证更新后的启动和硬件功能。

## 当时计划在 macOS 进行的测试

1. 确认进入桌面。触摸板当时测试 GPIO 中断模式，需准备 USB 鼠标。
2. Wi-Fi：忘记此前连接失败的网络，再试 WPA2 网络或手机热点，记录立即失败、重复要求密码、连接成功或连接后无 IP 等表现。驱动为 AirPort_RTW89 0.6.0 Beta。当时建议尝试 2.4 GHz；后续证据不支持把问题归因于频段。
3. 蓝牙：检查“系统信息 → 蓝牙”并尝试配对。仅出现 USB 条目不能证明固件上传成功，需检查启动日志中的 RealtekFirmware 和固件完成信息。
4. 电池：尽量在相近时间比较 macOS 与 Windows/固件的电量，采集 `ioreg -lw0 -r -c AppleSmartBattery` 与 `pmset -g batt`。当时的新补丁只纠正单位，尚不能保证修复 4% 问题；后续用户确认正常。
5. 触摸板：验证移动、点击、手势、睡眠唤醒与空闲 CPU 占用，检查 VoodooI2C 日志及 IORegistry。中断模式失败时恢复旧 EFI 或加回 `-vi2c-force-polling`。后续确已恢复轮询。
6. 音频：当时未解决，Windows 识别 Intel SST `8086:E328` 和 ALC235。不能只凭 AppleALC 支持该 codec 就判定控制器可用，Tahoe 的音频栈也需验证。

当时的工具是 `tools/collect_macos_diagnostics.command`，在连接失败后 30 分钟内通过 zsh 运行。输出可能含网络名与硬件标识，公开前需检查。当前建议使用 EFI 分区上的 `EFI/Diagnostics/collect.command`，见首页。

## 当时的回退方案

将更新前的完整 EFI 备份恢复到分区。该备份使用 AirPort_RTW89 0.5.0，没有新增 Realtek 蓝牙组件，并保留 `-vi2c-force-polling`。若仅触摸板中断模式失败，加回此参数是较小的回退范围。不要把这份历史回退配置误当成最新推荐配置。

## 后续固定更新流程

检查当前内部 EFI → 本地备份 → 修改硬盘 EFI → 读回校验与配置检查 → 将实际修改同步到仓库并推送。分别说明磁盘文件验证结果和 macOS 实机启动、设备功能结果。
