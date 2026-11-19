# ASUS Vivobook S16 S5650AA · Panther Lake Hackintosh

> **`feature/full-efi` 分支**：提供一套包含全部已实现功能的 EFI（恢复 2026-11-17 16:05 实机验证过的
> 全功能状态，并补齐 Metal 栈与部署/回退工具）。**该套 EFI 未经真机验证**，部署前请先读
> [`docs/full-efi-deployment.md`](docs/full-efi-deployment.md)。`main` 分支保持 apps-only 状态。

**简体中文 / English** · 更新 / Updated: **2026-11-18**

这是我的 ASUS Vivobook S16 S5650AA 黑苹果适配记录与 OpenCore EFI。当前实机运行 **macOS Sequoia 15.6 (24G84)**（OpenCore `REL-108-2026-09-27`，SMBIOS `MacBookPro16,2`），已实现静默直通启动、`XeGfxIntelFramebuffer` 接管显示与背光（`1280×800` HiDPI 与 `2560×1600` 1x @ 165 Hz / Metal 3）、**开机亮度 NVRAM 记忆**、**合盖息屏与开盖亮度恢复**、**防 S3 睡死（`pmset` 持久化）**、触摸板 GPIO 中断、Wi-Fi/蓝牙/摄像头与 `en0` Apple ID 注入；**WindowServer 桌面低帧率与输入卡顿**（视觉类渲染异常已于 11-17 修复）与**大于半屏的缩放分辨率（Pipe Scaler）**仍待进一步适配。

> **2026-11-18 现状**：EFI 已切换为**仅应用加速（apps-only）**策略——开机脚本写入 `-WindowServer` / `*` 进程拒绝名单，等待 WindowServer 就绪后再把 `XeGfxAccel` 从磁盘延后加载，桌面合成仍走软件路径。恢复过程曾停在苹果标志，**实机验证尚未通过**。各阶段的实测状态见下方「验证链条 / Verified chain」，恢复细节见 [`docs/boot-recovery-2026-11-18.md`](docs/boot-recovery-2026-11-18.md) 与 [`docs/system-layer-boot-audit-2026-11-18.md`](docs/system-layer-boot-audit-2026-11-18.md)。

My OpenCore EFI and adaptation logs for the ASUS Vivobook S16 S5650AA. The machine currently runs **macOS Sequoia 15.6 (24G84)** (OpenCore `REL-108-2026-09-27`, SMBIOS `MacBookPro16,2`) with silent direct boot, `XeGfxIntelFramebuffer` display & backlight control (`1280×800` HiDPI & `2560×1600` 1x @ 165 Hz / Metal 3), **boot brightness NVRAM persistence**, **lid-close backlight-off & lid-open brightness restore**, **anti-S3-sleep-death (`pmset` persisted at boot)**, GPIO-mode touchpad, Wi-Fi/Bluetooth/Webcam, and `en0` built-in/ROM injection for Apple ID. **WindowServer frame drops and typing lag** (visual glitches were fixed on 2026-11-17) and **>half-panel scaled resolutions (Pipe Scaler)** remain open.

> **Status 2026-11-18**: the EFI now runs an **apps-only** GPU policy — the boot helper installs a `-WindowServer` / `*` process deny list and loads `XeGfxAccel` late from disk, so desktop composition still uses the software path. The recovery attempt stopped at the Apple logo and **has not passed real-machine verification yet**.

---

## 硬件与当前状态 / Hardware and current status

| 项目 / Component | 硬件 / Hardware | 当前状态 / Current status |
| :--- | :--- | :--- |
| 机型 / Model | ASUS Vivobook S16 S5650AA | 本仓库实机 / Machine tested here (`MacBookPro16,2`) |
| 操作系统 / OS | macOS Sequoia 15.6 (`24G84`) | 可静默直通启动（`ShowPicker=false`, `ScanPolicy=257`）/ Silent direct boot |
| 处理器 / CPU | Core Ultra 7 356H, Panther Lake, 16C/16T | 16 核在线；Comet Lake CPUID 伪装 + `ProcessorType=3841` / All 16 cores online |
| 显卡 / GPU | Intel Arc (PTL Xe2), PCI `8086:B0A0` | **视觉类渲染异常已修复**：`nvmtl_self_snap` 补丁（`patches/patch_nvmtl.py`，默认关闭自采样替身纹理）解决了 CABackdropLayer 毛玻璃变黑、圆角合成破坏与锁屏头像菱形，11-17 18:11 重启后确认「显示正常」。**低帧率与输入卡顿仍未修复**（WindowServer 采样热点在 IOSurface 纹理创建与 ANV GEM 分配等待）。**IOSurface 共享内存（`xe_userptr`）已实装并在硬件上验证通过**（原生 4 MiB IOSurface GPU 填充零错误、16 模式往返全过、无 staging buffer；⚠️ **仅隔离测试进程验证，桌面从未启用，实现也未入库**），但尚未接入桌面。当前 EFI 已回退为 apps-only：启用 `XeGfx` 核心注入（`xegfx_bootstage=4`），禁用 AGDC 与新 framebuffer 接管，`XeGfxAccel` 在启动缓存中以 `Exclude` 拦截，改由开机脚本在 WindowServer 就绪后从磁盘延后加载，桌面合成回到软件路径 / Visual glitches (black blur, broken corners, diamond avatar) were fixed by the `nvmtl_self_snap` patch and confirmed on 2026-11-17; **low frame rate and typing lag remain unfixed**. The current EFI is apps-only: core `XeGfx` on (`xegfx_bootstage=4`), AGDC and the new framebuffer off, `XeGfxAccel` `Exclude`d from the boot cache and loaded late from disk, so desktop composition is back on the software path |
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

## 验证链条 / Verified chain

按时间顺序列出各阶段的实测状态。**断点在「共享内存之后、桌面接入」这一步**——共享内存本身已在硬件上验证可用。

| 阶段 | 状态 | 依据 |
| :--- | :--- | :--- |
| 基础 EFI：电池、音频、网卡、摄像头、静默启动 | ✅ 实机可用 | 11-12 ~ 11-16 |
| 触摸板 GPIO 中断模式 | ✅ 实机确认 | `400daaa` |
| PTL B0A0 stage 1–3 初始化、GOP 显存快照 | ✅ 实机通过 | `2f51246`、`4b4e734` |
| stage 4 SYSINIT 卡死定位（v11 ~ v17） | ❌ 根因未定位 | `GPU_PANTHER_LAKE.md` |
| Metal 计算 1024/1024、像素回读、Vulkan 离屏、NMXAccel 匹配 | ✅ 验证通过 | `GPU_UI_FIX.md` |
| 显示接管、背光 NVRAM 记忆、合盖息屏与开盖恢复 | ✅ 实机验证 | `5a2bbd1` |
| HiDPI `1280×800` / `2560×1600` 1x @165 Hz | ✅ 实机验证 | `5a2bbd1` |
| WindowServer Metal 合成：毛玻璃变黑、缺圆角、锁屏头像菱形 | ✅ 11-17 17:51 `nvmtl_self_snap` 修复后确认「显示正常」 | `4ab0980`、`532caff` |
| **IOSurface 共享内存（`xe_userptr`）** | ✅ **已实装并在硬件上验证通过**：补丁实装进内核源码，构建出新 UUID `81DDE75D-CD72-326D-8A7F-8D6F5A697A12` 的内核并装入 EFI（旧内核保留为 `XeGfx-pre-userptr.kext`），19:11 重启后确认新内核加载、Stage 7 成功；GPU 填充原生 4 MiB IOSurface 0/1,048,576 错误字、16 种 CPU/GPU 往返模式全过、20 次独立导入/提交/释放全过、全程无 staging buffer。⚠️ 但开关为 opt-in，仅对隔离测试进程开启并随即恢复关闭，**桌面从未启用**；实现源码在 `experimental/xe-iosurface-userptr` 分支（已合入 `feature/full-efi`），但 **userptr 内核二进制从未入库**——仓库 EFI 的 `XeGfx.kext` 仍是 11-15 的 V35 基线，11-18 回退也把磁盘 EFI 换回了该基线 | `520e4c6`、`docs/xe-iosurface-shared-memory.md` |
| 桌面接入：WindowServer 实际使用共享内存与加速桥 | ❌ 19:26 连续 SIGABRT（Mesa 产物缺 LC_RPATH）；修正后仍存在 completion timeout | `048d6e2`、`60564d9` |
| apps-only 回退后的实机启动 | ❌ 停在苹果标志，未通过验证；且**该修复只进了仓库、未部署到磁盘**——磁盘 EFI 仍是 `048d6e2` 基线（`Kernel/Add` 里 `XeGfxAccel`/`XeGfxAGDC` 仍为启用，即 11-18 早期 boot panic 的根因；`gpu-windowserver-policy.command` 也不在磁盘上）。**已于 2026-11-20 03:06 部署 `feature/full-efi` 分支的全功能 EFI 到磁盘**（备份见 `backups/disk-efi-backup-20261120-030623`），macOS 侧仍需执行 `prepare-metal-stack.command` 与 `full-install.command` | `5f0de92`、`docs/boot-recovery-2026-11-18.md` |
| 低帧率与快速输入卡顿 | ❌ 未解决（采样热点在 IOSurface 纹理创建与 ANV GEM 分配等待） | `ade4f6e` |

---

## 近期关键改动 / Key changes (2026-11-15 ~ 2026-11-18)

- **仅应用加速策略 / Apps-only GPU Policy**：新增 `EFI/Diagnostics/gpu-windowserver-policy.command`，向 `/Library/GPUBundles/nvmtl-allow.txt` 与 `/Library/Extensions/nvmtl-allow.txt` 写入并读回 `-WindowServer` / `*` 拒绝名单；`gpu-display-capture.command` 改为先等待 WindowServer 就绪、确认未继承 `NVMTL_ENABLE` 绕过、确认 Metal 插件支持拒绝名单后，再推进 `debug.xegfx_stage=7` 并从 `EFI/OC/Kexts/XeGfxAccel.kext` 延后加载加速桥，不再写 `nvaccelfb`、不再启用 AGDC、不重启 WindowServer。
- **启动缓存拦截改为 Exclude / Cache Blocker Switched to Exclude**：`Kernel/Add` 中实验性 GPU 驱动的 `Disable` 拦截对已进入系统辅助驱动缓存的驱动返回 `Unsupported`，改为 `Exclude`；`xegfx_bootstage` 由 0 恢复为 4，保留 XeGfx 核心注入以避开早期 framebuffer 崩溃。**⚠️ 后补更正（依据 11-18 10:12 的 OpenCore 日志 `opencore-2026-11-18-101243.txt`）：`Exclude` 只作用于 Apple 自带的 prelinked kext，对 `org.watchthelight.*` 这类第三方 kext 全部返回 `Unsupported`，根本拦不住走 AuxKC 的驱动——唯一有效的开关是 `Kernel/Add` 里启不启用。**
- **系统层恢复审计 / System-layer Recovery Audit**：新增 `docs/system-layer-boot-audit-2026-11-18.md`，明确「回退 GitHub EFI ≠ 恢复当时的系统运行环境」——旧 EFI 仍会加载系统盘中的新版加速驱动，开机服务仍会执行显示接管设置，因此需要先读取系统侧状态再针对性恢复。
- **驱动启动日志 / Driver Boot Trace**：新增 `docs/xegfx-boot-trace-2026-11-15.log`（V33 stage 5/6 引擎执行与 GGTT 写回读回验证记录）。
- **Sequoia 安装与回退工具 / Sequoia Installer & Rollback**：新增 `tools/sequoia-install.command` 与 `tools/sequoia-uninstall.command`（按 UUID 挂载 EFI 分区、备份并逐文件校验 OC/Diagnostics/Boot 三段，失败自动回滚；**需配套 `EFI/` 与 `SHA256SUMS.txt`，目前尚未打包完成**），以及 Windows 侧 `tools/restore_github_efi.py`（按提交号回退 EFI，含 ocvalidate 校验与逐文件 SHA-256 读回验证）。
- **OpenCore 与引导 / Boot**：升级并同步至 Sequoia 15.6 EFI；配置 `ShowPicker=false`、`ScanPolicy=257`、移除 `-v` 与调试日志，启用 `DisableRtcChecksum`；清理 EFI 根目录冗余日志与临时脚本。
- **防睡死与电源 / Anti-sleep-death**：在 `EFI/Diagnostics/gpu-display-capture.command` 开机脚本中持久化 `pmset` 禁用睡眠参数，规避 Panther Lake 固件无 S3 导致的 `Sleep Wake failure in EFI 0x00000000 0x0000001f` 睡死问题。
- **亮度记忆与合盖开盖修复 / Boot & Lid Backlight Fix**：更新 `patches/patch_xegfxintelfb.py`：1）修复 `BlHandler::doUpdate` 提前清除 `fHasSavedBl` 标志导致开机早期 `brightness=255` 覆盖 NVRAM 记忆值的问题；2）监听 `IOPMrootDomain` `AppleClamshellState`（外加 500ms 轮询兜底），合盖时锁存 `fPreLidBlLevel` 并写 `0` 息屏，开盖时拦截 macOS 下发的 `0`/`255` 覆盖并立即恢复盒盖前亮度。
- **HiDPI 分辨率启用 / HiDPI 1280×800 Enabled**：在 `patches/patch_xegfxintelfb.py` 中恢复 `kDisplayModeValidForHiResFlag` 与面板物理尺寸上报，系统设置已可切换 `1280×800` HiDPI（2x `2560×1600 @ 165Hz`）与 `2560×1600` 1x。
- **桌面 Metal 诊断 / Desktop Metal Diagnostics**：在 `nvrm610.conf` 加入 `NVMTL_FBFETCH_WS=1` 并验证 `WindowServer` 已开启 `framebuffer fetch ON`，定位到剩余 `bytesPerRow` 非 32B 对齐拷贝不同步、`clear-only pass` 及 PTL Xe2 渲染异常问题。
- **NVMTL 自采样替身纹理修复 / NVMTL Self-Snapshot Fix（11-17 傍晚，视觉异常已修复）**：`patches/patch_nvmtl.py` 默认关闭 `nvmtl_self_snap`——自采样目标被 pre-pass `_snap` 替换会使 CABackdropLayer 毛玻璃变黑并破坏圆角合成。构建产物已部署并重新签名 `NVMTLDriver.bundle`，18:11 重启 WindowServer 后确认「显示正常，仍然卡顿」，**桌面毛玻璃变黑、缺圆角与锁屏头像菱形随之修复；低帧率仍未修复**。见 [`docs/progress-2026-11-17-nvmtl-self-snap.md`](docs/progress-2026-11-17-nvmtl-self-snap.md)。
- **IOSurface 共享内存（硬件验证通过 / Hardware-Verified Shared Memory）**：`patches/xg_xe_userptr.inc` 以 opt-in 有线页替换上游对 `xe_hmm_userptr_populate_range` 的拒绝，配 DMA 散列表映射与 fence 序拆除；Mesa 侧 `patches/apply_mesa_userptr.py` 在 `ANV_XE_USERPTR=1` 时才暴露 `VK_EXT_external_memory_host`。19:11 重启后确认新内核 UUID `81DDE75D-CD72-326D-8A7F-8D6F5A697A12` 加载、Stage 7 成功，**GPU 填充原生 4 MiB IOSurface 0/1,048,576 错误字，16 种 CPU→GPU→原 IOSurface 往返模式全过，全程无 staging buffer**——**共享内存本身是实装并在硬件上跑通的**。**但开关仅对隔离测试进程开启、测试后即恢复关闭，桌面从未真正启用；实现源文件（`patches/xg_xe_userptr.inc`、`patches/apply_mesa_userptr.py`）、验证脚本与 userptr 内核二进制均未入库——仓库 EFI 是 11-15 的 XeGfx V35 基线，11-18 回退已把磁盘 EFI 换回该基线。** 见 [`docs/xe-iosurface-shared-memory.md`](docs/xe-iosurface-shared-memory.md)。
- **桌面接入失败与基线恢复 / Desktop Integration Failure & Baseline Recovery**：19:26 接入后 WindowServer 连续 SIGABRT 至 watchdog 超时，根因是新 Mesa 产物缺 `LC_RPATH` 导致 `@rpath/libdrm.2.dylib` 无法解析、Vulkan 初始化失败后 CoreDisplay 断言退出——独立测试用 `DYLD_LIBRARY_PATH` 掩盖了打包问题。已回滚旧 Mesa / 旧插件并核对 SHA-256；补 `@loader_path` 并重签名后，无 `DYLD_LIBRARY_PATH` 的硬件复测通过（2560×1600 Metal IOSurface 双向访问零错误，20 次导入/提交/释放全过）。
- **Intel completion bridge 硬件试验 / Completion Bridge Trial**：加速器 UUID `582FA4EC-C798-3643-BD08-781E26D2B30C` 加载后，WindowServer 首次选中 Metal 未自动重启，但 display-pipe presents 停在 0 直到受控重启；修正能力查询（`NVAccel` → `NMXAccel`）后 10 秒动画试验测得 25.51 / 29.67 次呈现事件，测量窗口内无额外 timeout；30 秒保留检查多出 1 次 timeout，故关闭 kernel waiting 且未持久化实验插件。

---

## 待办与已知问题 / Remaining issues & TODO

1. **把仓库的 apps-only EFI 部署到磁盘 EFI 分区**：11-18 10:25 的回退用 `git archive 048d6e2` 覆盖了磁盘的 `EFI/OC`、`EFI/Diagnostics`、`EFI/BOOT`，因此**磁盘当前跑的是 11-17 19:27 的配置**——`Kernel/Add` 里 `XeGfxAccel.kext` 与 `XeGfxAGDC.kext` 仍为启用（正是 11-18 早期 boot panic 的根因），`gpu-windowserver-policy.command` 也不在磁盘上。仓库 HEAD（`5f0de92`）的 apps-only 修复**只提交未部署**，需重新挂载 EFI 分区并部署后再做实机验证。/ Deploy the repo's apps-only EFI to the disk EFI partition before further verification.
2. **完成 apps-only 策略的实机验证**：从恢复环境读取 `/Library/LaunchDaemons/org.mubai.gpu-capture.plist`、实验性 kext 的 `Info.plist`/UUID、AuxKC、Metal/Mesa 动态库哈希与 panic/WindowServer 报告，定位恢复时停在苹果标志的原因（早期 kext 挂死或 WindowServer 无法显示），再确认延后加载的 `XeGfxAccel` 生效且应用 Metal 可用。若 apps-only 路线不可行，**11-17 17:51 之后的状态（`debug.nvaccelfb=3` + `nvmtl_self_snap` 修复）是最后一个已确认「显示正常」的桌面配置**，可作为回滚基线。/ Complete real-machine verification of the apps-only policy and identify the cause of the Apple-logo stall.
3. **重建 userptr 内核并入库**：共享内存实现源码已合入本分支（`patches/xg_xe_userptr.inc`、`apply_xe_userptr.py`、`apply_mesa_userptr.py`、`apply_plugin_userptr.py`、`patches/intel-completion.patch`、`diagnostics/vk-iosurface-host.c`），CI 流水线也已接上（`xe-build.yml` 跑 ASan/UBSan 测试并打补丁，`xe-userland.yml` 构建 completion bridge 与 userptr 版 Mesa）。但**构建产物从未入库**——仓库 EFI 的 `XeGfx.kext` 仍是 11-15 的 V35 基线（3 个分支的二进制哈希一致），本机 `backups/` 下 36 个历史内核二进制也无一保留 userptr 构建。需在 CI 跑一次 userptr 构建并把产物提交回来，否则这条已验证的成果无法复现。/ Rebuild and commit the userptr kernel binary.
4. **修复 WindowServer 桌面低帧率与输入卡顿**：视觉类异常（毛玻璃变黑、缺圆角、锁屏头像菱形）已由 `nvmtl_self_snap` 补丁修复；剩余问题是掉帧与快速输入卡顿——WindowServer 采样热点集中在 IOSurface 私有纹理创建路径与 ANV GEM 分配等待（一次 8 秒采样中 `waitUntilCompleted` 约 29%、IOSurface 纹理创建约 17%），需优化 Vulkan/Mesa 与 XeGfx 的共享内存或呈现路径，并以受控负载验证。/ Fix the remaining frame drops and typing lag.
5. **大于半屏的缩放分辨率（Pipe Scaler）**：在 `XeGfxIntelFB` 中研究 `IOFBScalerInfo` / Intel pipe scaler 支持，使系统设置提供 `1440×900`、`1680×1050`、`1920×1200` HiDPI 等缩放选项。
6. **外设与交互复测**：验证 Fn+亮度快捷键、内置扬声器/耳机孔/麦克风实际表现、Type-C 视频输出及 PM981 真实 ACPI 禁用路径。
7. **打包 Sequoia 安装包**：为 `tools/sequoia-install.command` 补齐 `EFI/` 目录与 `SHA256SUMS.txt`，并解决脚本内 `安装.command` / `回退.command` 中文文件名缺失的问题。

---

## 使用与回退 / Use and rollback

这是本机实测 EFI，不保证其他机器直接可用。替换前请务必备份当前 EFI 并保留可启动恢复介质；配置包含本机 SMBIOS 与 `ROM` 字段，其他使用者请自行生成新的 SMBIOS 标识。

This EFI is tuned for this specific machine. Always back up your EFI and keep bootable recovery media before making changes, and generate your own SMBIOS identifiers if reusing this configuration.
