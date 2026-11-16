# ASUS Vivobook S16 S5650AA · Panther Lake Hackintosh

**简体中文 / English** · 更新 / Updated: **2026-11-17**

这是我的 ASUS Vivobook S16 S5650AA 黑苹果适配记录与 OpenCore EFI。当前实机运行 **macOS Sequoia 15.6 (24G84)**（OpenCore `REL-108-2026-09-27`，SMBIOS `MacBookPro16,2`），已实现静默直通启动、`XeGfxIntelFramebuffer` 接管显示与背光（2560×1600 @ 165 Hz / Metal 3）、**开机亮度 NVRAM 记忆**、**防 S3 睡死（`pmset` 持久化）**、触摸板 GPIO 中断、Wi-Fi/蓝牙/摄像头与 `en0` Apple ID 注入；**合盖再开盖背光恢复**、**WindowServer 桌面 Metal 渲染异常**与**缩放分辨率**仍待进一步适配。

My OpenCore EFI and adaptation logs for the ASUS Vivobook S16 S5650AA. The machine currently runs **macOS Sequoia 15.6 (24G84)** (OpenCore `REL-108-2026-09-27`, SMBIOS `MacBookPro16,2`) with silent direct boot, `XeGfxIntelFramebuffer` display & backlight control (2560×1600 @ 165 Hz / Metal 3), **boot brightness NVRAM persistence**, **anti-S3-sleep-death (`pmset` persisted at boot)**, GPIO-mode touchpad, Wi-Fi/Bluetooth/Webcam, and `en0` built-in/ROM injection for Apple ID. **Lid-open backlight restore**, **WindowServer Metal composition glitches**, and **scaled/HiDPI resolutions** remain open.

---

## 硬件与当前状态 / Hardware and current status

| 项目 / Component | 硬件 / Hardware | 当前状态 / Current status |
| :--- | :--- | :--- |
| 机型 / Model | ASUS Vivobook S16 S5650AA | 本仓库实机 / Machine tested here (`MacBookPro16,2`) |
| 操作系统 / OS | macOS Sequoia 15.6 (`24G84`) | 可静默直通启动（`ShowPicker=false`, `ScanPolicy=257`）/ Silent direct boot |
| 处理器 / CPU | Core Ultra 7 356H, Panther Lake, 16C/16T | 16 核在线；Comet Lake CPUID 伪装 + `ProcessorType=3841` / All 16 cores online |
| 显卡 / GPU | Intel Arc (PTL Xe2), PCI `8086:B0A0` | `XeGfx (0.0.47)` + `XeGfxAccel (0.9)` + `XeGfxAGDC (0.1.1)` + `XeGfxIntelFB (0.9)` 已加载；Metal 3 报告正常。默认 `nvaccelfb=1` 走软件合成可用；切换 `debug.nvaccelfb=3` 可启动 `WindowServer` Metal 合成（`NVMTL_FBFETCH_WS=1` 已启用），但存在掉帧、缺圆角、半透明变黑与锁屏头像菱形等渲染异常 / Kexts loaded & Metal 3 reported. Software compositing (`nvaccelfb=1`) works; `debug.nvaccelfb=3` enables Metal `WindowServer` (`NVMTL_FBFETCH_WS=1` on) but still hits frame drops, missing corners, black blur, and diamond avatar glitches |
| 屏幕与背光 / Display & Backlight | 16-inch OLED (`ATNA60HS01-0`) | `XeGfxIntelFramebuffer` 已接管 `2560×1600 @ 165.00 Hz`；**开机 NVRAM 亮度记忆已修复并实机验证**（拦截开机早期 `255` 覆盖）；合盖再开盖后的背光恢复仍待修复；仅原生 `2560×1600` 分辨率，缩放/HiDPI 待补全 pipe scaler / **Boot brightness NVRAM persistence verified**; lid-open restore still broken; native `2560×1600` only (scaled/HiDPI needs pipe scaler) |
| 内存 / Memory | 32 GB LPDDR5X 7467 MT/s | 正常识别 / Working |
| 主硬盘 / Primary SSD | 1 TB NVMe | APFS 系统可启动 / Boots macOS Sequoia 15.6 |
| 副硬盘 / Secondary SSD | Samsung PM981 256 GB | `SSDT-Disable-PM981.aml` 已启用，但实机仍挂载为 `external` 盘（ACPI 路径待按真实设备路径调整） / Enabled in config, still enumerates as external (ACPI path mismatch) |
| 键盘 / Keyboard | Built-in PS/2 | VoodooPS2Keyboard 可用 / Working |
| 触摸板 / Touchpad | TZY4E41, I²C `TPD0` | **GPIO 中断模式已实机确认**（`VoodooI2C 2.9.1` + `VoodooI2CHID`） / Confirmed GPIO interrupt mode |
| 摄像头 / Camera | ASUS FHD webcam (`0x3277:0x0101`) | XHCI HS02（`WCAM`/`CIR` + `A2UP`）修复后已正常识别 / Detected after HS02 fix |
| USB / Type-C | Intel xHCI / Type-C (`0xe331`, `0xe37d`) | `UTBMap` 已适配 `MacBookPro16,2`，常规 USB 设备可用；Type-C 视频输出与全端口未全面验证 / USB works; Type-C display & full port coverage pending |
| 电池 / Battery | Internal battery | `AppleSmartBattery` 电量/充电/循环次数正常（`SSDT-BATT-FIX-UNIT0.aml`） / Working |
| 音频 / Audio | ALC235 + Intel SST `8086:E328` | `AppleALC (1.9.8)` 已识别 `Built-in Input` 与 `Built-in Output`；实际外放、耳机孔与录音待确认 / Detected; playback, jack switch & mic capture pending |
| Wi-Fi | RTL8852BE `10EC:B852` (`en0`) | 已联网（`AirPort_RTW89`），已注入真实 MAC ROM（`0c:cd:d0:e6:e1:8f`）与 `built-in` 属性以支持 Apple ID / Connected; real ROM & built-in injected for Apple ID |
| 蓝牙 / Bluetooth | Realtek USB `0BDA:B85B` | `RealtekBluetoothFirmware (1.0.2)` + `BlueToolFixup (2.7.2)` 已启用并可配对设备 / Working; long-term audio accessory tests pending |
| 睡眠 / 防睡死 / Sleep | `pmset disablesleep 1`（开机脚本持久化） | Panther Lake 固件仅支持 S0ix（不支持 ACPI S3，S3 必报 `Sleep Wake failure in EFI 0x1f`）；已通过开机脚本持久化 `pmset -a sleep 0 standby 0 autopoweroff 0 powernap 0 proximitywake 0 tcpkeepalive 0 disablesleep 1`，合盖不再睡死 / S3 unsupported by PTL firmware; anti-sleep `pmset` persisted at boot, lid-close no longer freezes |

---

## 近期关键改动 / Key changes (2026-11-15 ~ 2026-11-17)

- **OpenCore 与引导 / Boot**：升级并同步至 Sequoia 15.6 EFI；配置 `ShowPicker=false`、`ScanPolicy=257`、移除 `-v` 与调试日志，启用 `DisableRtcChecksum`；清理 EFI 根目录冗余日志与临时脚本。
- **防睡死与电源 / Anti-sleep-death**：在 `EFI/Diagnostics/gpu-display-capture.command` 开机脚本中持久化 `pmset` 禁用睡眠参数，规避 Panther Lake 固件无 S3 导致的 `Sleep Wake failure in EFI 0x00000000 0x0000001f` 睡死问题。
- **亮度记忆修复 / Boot Brightness Fix**：更新 `patches/patch_xegfxintelfb.py`，修复 `BlHandler::doUpdate` 提前清除 `fHasSavedBl` 标志导致开机早期 `brightness=255` 覆盖 NVRAM 记忆值的问题；重建 `/Library/KernelCollections/AuxiliaryKernelExtensions.kc`（`kmutil create -n aux ... --allow-missing-kdk`）后实机重启验证开机亮度记忆成功。
- **桌面 Metal 诊断 / Desktop Metal Diagnostics**：在 `nvrm610.conf` 加入 `NVMTL_FBFETCH_WS=1` 并验证 `WindowServer` 已开启 `framebuffer fetch ON`，定位到剩余 `bytesPerRow` 非 32B 对齐拷贝不同步、`clear-only pass` 及 PTL Xe2 渲染异常问题。

---

## 待办与已知问题 / Remaining issues & TODO

1. **合盖再开盖背光恢复**：排查合盖/开盖后面板 DPCD `0x300`/`0x344`/`0x354` 或面板电源状态重置导致背光异常的原因。
2. **修复 WindowServer 桌面 Metal 渲染异常**：修复 `NVMTLObjects.m` 中 `bytesPerRow` 非 32B 对齐的替身纹理重同步、`clear-only pass` depth/stencil 清理及 Panther Lake (`8086:B0A0`) `WindowServer` 合成异常（掉帧、缺圆角、毛玻璃变黑、锁屏头像菱形），以在不依赖“降低透明度”的前提下正常使用桌面硬件加速。
3. **缩放分辨率（HiDPI）**：在 `XeGfxIntelFB` 中补全 `IOFBScalerInfo` / Intel pipe scaler 支持，使系统设置提供 `1280×800` HiDPI 等缩放选项。
4. **外设与交互复测**：验证 Fn+亮度快捷键、内置扬声器/耳机孔/麦克风实际表现、Type-C 视频输出及 PM981 真实 ACPI 禁用路径。

---

## 使用与回退 / Use and rollback

这是本机实测 EFI，不保证其他机器直接可用。替换前请务必备份当前 EFI 并保留可启动恢复介质；配置包含本机 SMBIOS 与 `ROM` 字段，其他使用者请自行生成新的 SMBIOS 标识。

This EFI is tuned for this specific machine. Always back up your EFI and keep bootable recovery media before making changes, and generate your own SMBIOS identifiers if reusing this configuration.
