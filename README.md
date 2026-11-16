# ASUS Vivobook S16 S5650AA · Panther Lake Hackintosh

**简体中文 / English** · 更新 / Updated: **2026-11-16**

这是我的 ASUS Vivobook S16 S5650AA 黑苹果适配记录与 OpenCore EFI。当前实机运行 **macOS Sequoia 15.6 (24G84)**（OpenCore `REL-108-2026-09-27`，SMBIOS `MacBookPro16,2`），已实现静默直通启动、`XeGfxIntelFramebuffer` 接管显示与背光（2560×1600 @ 165 Hz / Metal 3）、触摸板 GPIO 中断、Wi-Fi/蓝牙/摄像头与 `en0` Apple ID 注入；**WindowServer 桌面硬件加速呈像**（目前被 NVMTL allowlist 拒绝）与**睡眠/唤醒循环**仍待打通与验证。

My OpenCore EFI and adaptation logs for the ASUS Vivobook S16 S5650AA. The machine currently runs **macOS Sequoia 15.6 (24G84)** (OpenCore `REL-108-2026-09-27`, SMBIOS `MacBookPro16,2`) with silent direct boot, `XeGfxIntelFramebuffer` display & backlight control (2560×1600 @ 165 Hz / Metal 3), GPIO-mode touchpad, Wi-Fi/Bluetooth/Webcam, and `en0` built-in/ROM injection for Apple ID. **WindowServer desktop acceleration** (currently denied by the NVMTL allowlist) and **sleep/wake cycle verification** remain pending.

---

## 硬件与当前状态 / Hardware and current status

| 项目 / Component | 硬件 / Hardware | 当前状态 / Current status |
| :--- | :--- | :--- |
| 机型 / Model | ASUS Vivobook S16 S5650AA | 本仓库实机 / Machine tested here (`MacBookPro16,2`) |
| 操作系统 / OS | macOS Sequoia 15.6 (`24G84`) | 可静默直通启动（`ShowPicker=false`, `ScanPolicy=257`）/ Silent direct boot |
| 处理器 / CPU | Core Ultra 7 356H, Panther Lake, 16C/16T | 16 核在线；Comet Lake CPUID 伪装 + `ProcessorType=3841` / All 16 cores online |
| 显卡 / GPU | Intel Arc (PTL Xe2), PCI `8086:B0A0` | `XeGfx (0.0.47)` + `XeGfxAccel (0.9)` + `XeGfxAGDC (0.1.1)` + `XeGfxIntelFB (0.9)` 已加载；应用层 Metal 3 / Vulkan 离屏通过；**WindowServer 仍被 NVMTL allowlist 拒绝，桌面合成未走硬解** / Kexts loaded & Metal 3 reported; **WindowServer denied by NVMTL allowlist, desktop acceleration unresolved** |
| 屏幕与背光 / Display & Backlight | 16-inch OLED (`ATNA60HS01-0`) | `XeGfxIntelFramebuffer` 已接管，识别为 `2560×1600 @ 165.00 Hz`；`AppleBacklightDisplay` 与 `XeGfxBacklightHandler` 已挂载（`brightness` 0–1024），NVRAM 持久化已部署；Fn+亮度键（`SSDT-BKEY`）待实机确认 / Framebuffer active at 165 Hz with backlight handler; Fn brightness keys pending verification |
| 内存 / Memory | 32 GB LPDDR5X 7467 MT/s | 正常识别 / Working |
| 主硬盘 / Primary SSD | 1 TB NVMe | APFS 系统可启动 / Boots macOS Sequoia 15.6 |
| 副硬盘 / Secondary SSD | Samsung PM981 256 GB | `SSDT-Disable-PM981.aml` 已包含（默认禁用状态） / Disable SSDT included |
| 键盘 / Keyboard | Built-in PS/2 | VoodooPS2Keyboard 可用 / Working |
| 触摸板 / Touchpad | TZY4E41, I²C `TPD0` | **GPIO 中断模式已实机确认**（`VoodooI2C 2.9.1` + `VoodooI2CHID`）；唤醒后稳定性待测 / Confirmed GPIO interrupt mode; post-wake stability pending |
| 摄像头 / Camera | ASUS FHD webcam (`0x3277:0x0101`) | XHCI HS02（`WCAM`/`CIR` + `A2UP`）修复后已正常识别 / Detected after HS02 fix |
| USB / Type-C | Intel xHCI / Type-C (`0xe331`, `0xe37d`) | `UTBMap` 已适配 `MacBookPro16,2`，常规 USB 设备可用；Type-C 视频输出与全端口未全面验证 / USB works; Type-C display & full port coverage pending |
| 电池 / Battery | Internal battery | `AppleSmartBattery` 电量/充电/循环次数正常（`SSDT-BATT-FIX-UNIT0.aml`） / Working |
| 音频 / Audio | ALC235 + Intel SST `8086:E328` | `AppleALC (1.9.8)` 已识别 `Built-in Input` 与 `Built-in Output`；实际外放、耳机孔与录音待确认 / Detected; playback, jack switch & mic capture pending |
| Wi-Fi | RTL8852BE `10EC:B852` (`en0`) | 已联网（`AirPort_RTW89`），已注入真实 MAC ROM（`0c:cd:d0:e6:e1:8f`）与 `built-in` 属性以支持 Apple ID / Connected; real ROM & built-in injected for Apple ID |
| 蓝牙 / Bluetooth | Realtek USB `0BDA:B85B` | `RealtekBluetoothFirmware (1.0.2)` + `BlueToolFixup (2.7.2)` 已启用并可配对设备 / Working; long-term audio accessory tests pending |
| 睡眠 / 唤醒 / Sleep & Wake | `SSDT-LID` + `.Display_boot` 电源修复 | 已部署修复，**尚无实机睡眠唤醒循环记录**（`Sleep/Wakes: 0`） / Staged; full sleep/wake cycle unverified |

---

## 近期关键改动 / Key changes (2026-11-15 ~ 2026-11-16)

- **OpenCore 与引导 / Boot**：升级并同步至 Sequoia 15.6 EFI；配置 `ShowPicker=false`、`ScanPolicy=257`、移除 `-v` 与调试日志目标，启用静默直通启动。
- **CPU / ACPI**：保留 `APIC-legacy.aml`、`SSDT-PLUG-ALT.aml`、`SSDT-BATT-FIX-UNIT0.aml`、`SSDT-PTL-GPIO.aml`、`SSDT-TPD0.aml`；新增 `SSDT-PNLF.aml`、`SSDT-BKEY.aml`（Fn+亮度键）、`SSDT-LID.aml`（合盖睡眠）与 `SSDT-USB-FIX.aml`（HS02 摄像头 / TDM0）；设置 `ProcessorType=3841` 与短 `revcpuname` 配合 `RestrictEvents`。
- **核显与显示 / Graphics & Display**：
  - `XeGfx (0.0.47)`、`XeGfxAccel (0.9)`、`XeGfxAGDC (0.1.1)` 与 `XeGfxIntelFB (0.9)` 均已启用；
  - `XeGfxIntelFB` 新增高刷 VBL 定时器、eDP AUX / DPCD 16-bit HDR 背光控制、`AppleBacklightDisplay` 识别与 NVRAM 亮度持久化；
  - **当前卡点**：诊断日志显示 `WindowServer` 仍被 `NVMTLDriver` allowlist 拦截（`denied by list: no device for WindowServer`），`nvaccel_pipe_perform=0`、`nvaccel_scanout_copies=0`。
- **网络与 Apple ID / Network & Apple ID**：为 `en0`（Wi-Fi PCI 设备）注入真实硬件 MAC ROM（`0c:cd:d0:e6:e1:8f`）与 `built-in` 属性。

---

## 待办与已知问题 / Remaining issues & TODO

1. **解决 WindowServer NVMTL 放行与桌面呈像加速**：排查 `NVMTLDriver` 对 `WindowServer` 的 allowlist 限制，打通 `nvaccel_iop_ok_h4` / `nvaccel_pipe_perform` / `nvaccel_scanout_copies`。
2. **睡眠 / 合盖唤醒实机测试**：触发一次完整合盖/空闲睡眠与唤醒，验证核显恢复、背光、GPIO 触摸板及 Wi-Fi/蓝牙状态。
3. **外设与交互复测**：验证 Fn+亮度快捷键、内置扬声器/耳机孔/麦克风实际表现、Type-C 视频输出与各 USB 端口。

---

## 使用与回退 / Use and rollback

这是本机实测 EFI，不保证其他机器直接可用。替换前请务必备份当前 EFI 并保留可启动恢复介质；配置包含本机 SMBIOS 与 `ROM` 字段，其他使用者请自行生成新的 SMBIOS 标识。

This EFI is tuned for this specific machine. Always back up your EFI and keep bootable recovery media before making changes, and generate your own SMBIOS identifiers if reusing this configuration.

## 历史记录 / Historical records

- [桌面修复记录 / Desktop fix notes](GPU_UI_FIX.md)
- [触摸板 GPIO 记录 / Touchpad GPIO](TOUCHPAD_GPIO.md)
- [首轮测试（历史） / Initial test](HARDWARE_TEST_2026-11-13.zh-CN.md) · [English](HARDWARE_TEST_2026-11-13.md)
- [后续记录（历史） / Follow-up](HARDWARE_FOLLOWUP_2026-11-13.zh-CN.md) · [English](HARDWARE_FOLLOWUP_2026-11-13.md)

## 致谢 / Credits

[Acidanthera](https://github.com/acidanthera)、[Dortania](https://dortania.github.io/)、[FranciumOS](https://github.com/FranciumOS-org/Airport_RTW89)、[SimpleHDA](https://github.com/laobamac/SimpleHDA)、[RealtekBluetoothFirmware](https://github.com/thegwchr/RealtekBluetoothFirmware)、[Lem's Hardware Lab](https://github.com/lems-hardware/lhl-hackintosh-docs)、[WTLIntelGfx](https://github.com/InSnh-Gd/WTLIntelGfx)，以及老吴黑苹果工作室的初始参考环境。
