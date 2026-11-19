# ASUS Vivobook S16 S5650AA · Panther Lake Hackintosh

**简体中文 / English** · 更新 / Updated: **2026-11-18**

这是我的 ASUS Vivobook S16 S5650AA 黑苹果适配记录与 OpenCore EFI。当前实机运行 **macOS Sequoia 15.6 (24G84)**（OpenCore `REL-108-2026-09-27`，SMBIOS `MacBookPro16,2`），已实现静默直通启动、`XeGfxIntelFramebuffer` 接管显示与背光（`1280×800` HiDPI 与 `2560×1600` 1x @ 165 Hz / Metal 3）、**开机亮度 NVRAM 记忆**、**合盖息屏与开盖亮度恢复**、**防 S3 睡死（`pmset` 持久化）**、触摸板 GPIO 中断、Wi-Fi/蓝牙/摄像头与 `en0` Apple ID 注入；**WindowServer 桌面 Metal 渲染异常**与**大于半屏的缩放分辨率（Pipe Scaler）**仍待进一步适配。

> **2026-11-18 现状**：EFI 已切换为**仅应用加速（apps-only）**策略——开机脚本写入 `-WindowServer` / `*` 进程拒绝名单，等待 WindowServer 就绪后再把 `XeGfxAccel` 从磁盘延后加载，桌面合成仍走软件路径。恢复过程曾停在苹果标志，**实机验证尚未通过**，详见 [`docs/boot-recovery-2026-11-18.md`](docs/boot-recovery-2026-11-18.md) 与 [`docs/system-layer-boot-audit-2026-11-18.md`](docs/system-layer-boot-audit-2026-11-18.md)。

My OpenCore EFI and adaptation logs for the ASUS Vivobook S16 S5650AA. The machine currently runs **macOS Sequoia 15.6 (24G84)** (OpenCore `REL-108-2026-09-27`, SMBIOS `MacBookPro16,2`) with silent direct boot, `XeGfxIntelFramebuffer` display & backlight control (`1280×800` HiDPI & `2560×1600` 1x @ 165 Hz / Metal 3), **boot brightness NVRAM persistence**, **lid-close backlight-off & lid-open brightness restore**, **anti-S3-sleep-death (`pmset` persisted at boot)**, GPIO-mode touchpad, Wi-Fi/Bluetooth/Webcam, and `en0` built-in/ROM injection for Apple ID. **WindowServer Metal composition glitches** and **>half-panel scaled resolutions (Pipe Scaler)** remain open.

> **Status 2026-11-18**: the EFI now runs an **apps-only** GPU policy — the boot helper installs a `-WindowServer` / `*` process deny list and loads `XeGfxAccel` late from disk, so desktop composition still uses the software path. The recovery attempt stopped at the Apple logo and **has not passed real-machine verification yet**.

---

## 硬件与当前状态 / Hardware and current status

| 项目 / Component | 硬件 / Hardware | 当前状态 / Current status |
| :--- | :--- | :--- |
| 机型 / Model | ASUS Vivobook S16 S5650AA | 本仓库实机 / Machine tested here (`MacBookPro16,2`) |
| 操作系统 / OS | macOS Sequoia 15.6 (`24G84`) | 可静默直通启动（`ShowPicker=false`, `ScanPolicy=257`）/ Silent direct boot |
| 处理器 / CPU | Core Ultra 7 356H, Panther Lake, 16C/16T | 16 核在线；Comet Lake CPUID 伪装 + `ProcessorType=3841` / All 16 cores online |
| 显卡 / GPU | Intel Arc (PTL Xe2), PCI `8086:B0A0` | 当前 EFI 启用 `XeGfx` 核心注入（`xegfx_bootstage=4`），**禁用** AGDC 与新 framebuffer 接管；加速桥 `XeGfxAccel` 在启动缓存中以 `Exclude` 方式拦截，改由开机脚本在 WindowServer 就绪后从磁盘延后加载，以保留应用 Metal 而拒绝桌面合成。桌面 Metal 渲染异常（掉帧、缺圆角、半透明变黑、锁屏头像菱形）仍未解决 / Core `XeGfx` injection is on (`xegfx_bootstage=4`); AGDC and the new framebuffer takeover are off. `XeGfxAccel` is `Exclude`d from the boot cache and loaded late from disk by the boot helper, keeping app Metal while denying WindowServer. Desktop Metal composition glitches remain unresolved |
| 屏幕与背光 / Display & Backlight | 16-inch OLED (`ATNA60HS01-0`) | `XeGfxIntelFramebuffer` 已接管显示与背光（`@165.00 Hz`）；**开机 NVRAM 亮度记忆已修复**、**合盖息屏与开盖亮度恢复已修复**（监听 `IOPMrootDomain` `AppleClamshellState` 并拦截开盖 `0`/`255` 覆盖）；已提供 **`1280×800` HiDPI** 与 **`2560×1600` 1x** 两种模式，大于半屏的缩放分辨率（如 `1680×1050` / `1920×1200` HiDPI）待补全 Pipe Scaler / **Boot NVRAM persistence & lid-close/open backlight restore verified**; **`1280×800` HiDPI & `2560×1600` 1x @ 165 Hz** available (>half-panel scaled modes need pipe scaler) |
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

## 近期关键改动 / Key changes (2026-11-15 ~ 2026-11-18)

- **仅应用加速策略 / Apps-only GPU Policy**：新增 `EFI/Diagnostics/gpu-windowserver-policy.command`，向 `/Library/GPUBundles/nvmtl-allow.txt` 与 `/Library/Extensions/nvmtl-allow.txt` 写入并读回 `-WindowServer` / `*` 拒绝名单；`gpu-display-capture.command` 改为先等待 WindowServer 就绪、确认未继承 `NVMTL_ENABLE` 绕过、确认 Metal 插件支持拒绝名单后，再推进 `debug.xegfx_stage=7` 并从 `EFI/OC/Kexts/XeGfxAccel.kext` 延后加载加速桥，不再写 `nvaccelfb`、不再启用 AGDC、不重启 WindowServer。
- **启动缓存拦截改为 Exclude / Cache Blocker Switched to Exclude**：`Kernel/Add` 中实验性 GPU 驱动的 `Disable` 拦截对已进入系统辅助驱动缓存的驱动返回 `Unsupported`，改为 `Exclude`；`xegfx_bootstage` 由 0 恢复为 4，保留 XeGfx 核心注入以避开早期 framebuffer 崩溃。
- **系统层恢复审计 / System-layer Recovery Audit**：新增 `docs/system-layer-boot-audit-2026-11-18.md`，明确「回退 GitHub EFI ≠ 恢复当时的系统运行环境」——旧 EFI 仍会加载系统盘中的新版加速驱动，开机服务仍会执行显示接管设置，因此需要先读取系统侧状态再针对性恢复。
- **驱动启动日志 / Driver Boot Trace**：新增 `docs/xegfx-boot-trace-2026-11-15.log`（V33 stage 5/6 引擎执行与 GGTT 写回读回验证记录）。
- **Sequoia 安装与回退工具 / Sequoia Installer & Rollback**：新增 `tools/sequoia-install.command` 与 `tools/sequoia-uninstall.command`（按 UUID 挂载 EFI 分区、备份并逐文件校验 OC/Diagnostics/Boot 三段，失败自动回滚；**需配套 `EFI/` 与 `SHA256SUMS.txt`，目前尚未打包完成**），以及 Windows 侧 `tools/restore_github_efi.py`（按提交号回退 EFI，含 ocvalidate 校验与逐文件 SHA-256 读回验证）。
- **OpenCore 与引导 / Boot**：升级并同步至 Sequoia 15.6 EFI；配置 `ShowPicker=false`、`ScanPolicy=257`、移除 `-v` 与调试日志，启用 `DisableRtcChecksum`；清理 EFI 根目录冗余日志与临时脚本。
- **防睡死与电源 / Anti-sleep-death**：在 `EFI/Diagnostics/gpu-display-capture.command` 开机脚本中持久化 `pmset` 禁用睡眠参数，规避 Panther Lake 固件无 S3 导致的 `Sleep Wake failure in EFI 0x00000000 0x0000001f` 睡死问题。
- **亮度记忆与合盖开盖修复 / Boot & Lid Backlight Fix**：更新 `patches/patch_xegfxintelfb.py`：1）修复 `BlHandler::doUpdate` 提前清除 `fHasSavedBl` 标志导致开机早期 `brightness=255` 覆盖 NVRAM 记忆值的问题；2）监听 `IOPMrootDomain` `AppleClamshellState`（外加 500ms 轮询兜底），合盖时锁存 `fPreLidBlLevel` 并写 `0` 息屏，开盖时拦截 macOS 下发的 `0`/`255` 覆盖并立即恢复盒盖前亮度。
- **HiDPI 分辨率启用 / HiDPI 1280×800 Enabled**：在 `patches/patch_xegfxintelfb.py` 中恢复 `kDisplayModeValidForHiResFlag` 与面板物理尺寸上报，系统设置已可切换 `1280×800` HiDPI（2x `2560×1600 @ 165Hz`）与 `2560×1600` 1x。
- **桌面 Metal 诊断 / Desktop Metal Diagnostics**：在 `nvrm610.conf` 加入 `NVMTL_FBFETCH_WS=1` 并验证 `WindowServer` 已开启 `framebuffer fetch ON`，定位到剩余 `bytesPerRow` 非 32B 对齐拷贝不同步、`clear-only pass` 及 PTL Xe2 渲染异常问题。

---

## 待办与已知问题 / Remaining issues & TODO

1. **完成 apps-only 策略的实机验证**：从恢复环境读取 `/Library/LaunchDaemons/org.mubai.gpu-capture.plist`、实验性 kext 的 `Info.plist`/UUID、AuxKC、Metal/Mesa 动态库哈希与 panic/WindowServer 报告，定位恢复时停在苹果标志的原因（早期 kext 挂死或 WindowServer 无法显示），再确认延后加载的 `XeGfxAccel` 生效且应用 Metal 可用。/ Complete real-machine verification of the apps-only policy and identify the cause of the Apple-logo stall.
2. **修复 WindowServer 桌面 Metal 渲染异常**：修复 `NVMTLObjects.m` 中 `bytesPerRow` 非 32B 对齐的替身纹理重同步、`clear-only pass` 及 Panther Lake (`8086:B0A0`) `WindowServer` 合成异常（掉帧、缺圆角、毛玻璃变黑、锁屏头像菱形），以在不依赖“降低透明度”的前提下正常使用桌面硬件加速。
3. **大于半屏的缩放分辨率（Pipe Scaler）**：在 `XeGfxIntelFB` 中研究 `IOFBScalerInfo` / Intel pipe scaler 支持，使系统设置提供 `1440×900`、`1680×1050`、`1920×1200` HiDPI 等缩放选项。
4. **外设与交互复测**：验证 Fn+亮度快捷键、内置扬声器/耳机孔/麦克风实际表现、Type-C 视频输出及 PM981 真实 ACPI 禁用路径。
5. **打包 Sequoia 安装包**：为 `tools/sequoia-install.command` 补齐 `EFI/` 目录与 `SHA256SUMS.txt`，并解决脚本内 `安装.command` / `回退.command` 中文文件名缺失的问题。

---

## 使用与回退 / Use and rollback

这是本机实测 EFI，不保证其他机器直接可用。替换前请务必备份当前 EFI 并保留可启动恢复介质；配置包含本机 SMBIOS 与 `ROM` 字段，其他使用者请自行生成新的 SMBIOS 标识。

This EFI is tuned for this specific machine. Always back up your EFI and keep bootable recovery media before making changes, and generate your own SMBIOS identifiers if reusing this configuration.
