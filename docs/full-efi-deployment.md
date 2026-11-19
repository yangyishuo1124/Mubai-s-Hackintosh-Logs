# 全功能 EFI 部署说明 / Full-feature EFI deployment

本分支 `feature/full-efi` 提供一套**包含全部已实现功能**的 EFI，并附带 FULL / SAFE 两套 profile
与完整的系统卷安装、校验、回退流程。

> **重要前提**：本套 EFI **未在真机上验证过**。组装者没有 macOS 环境，无法确认它能开机。
> 它的 EFI 层（config / ACPI / kext 注入）来自 2026-11-17 16:05 实机验证通过的 `5a2bbd1`；
> 但 Metal 栈（NVMTLDriver / Mesa）是本次从 CI 产物包重新组装的，**没有实机验证**。
> 请务必保留回退路径。

---

## 1. 这套 EFI 相对 `main` 改了什么

| 项目 | `main`（apps-only） | 本分支（全功能） |
| :--- | :--- | :--- |
| `Kernel/Add` `XeGfxAccel.kext` | 关闭 | **启用** |
| `Kernel/Add` `XeGfxAGDC.kext` | 关闭 | **启用** |
| `Kernel/Block` 实验性驱动 Exclude | 5 条（XeGfx / AGDC / Accel / IntelFB / NMIntelFB） | **全部解除**，只保留 IOSkywalkFamily |
| `XeGfxIntelFB` 的 `OSBundleRequired=Root` | 已移除（11-18 为躲 panic 去掉） | **保留** |
| `boot-args` | 含 `-v`、`-xeintelfboff` | `keepsyms=1 ... xegfx_bootstage=4 nvaccelfb=1 -nmintelfboff` |
| `Misc/Boot` `ShowPicker` / `Timeout` | True / 5（调试引导） | **False / 0**（静默直通启动） |
| `Misc/Security` `ScanPolicy` | 0 | **257** |
| `Misc/Debug` `Target` / `AppleDebug` | 67 / True | **0 / False** |
| `Diagnostics/GPU/metal/`、`GPU/vulkan/` | **不存在** | **已补齐**（NVMTLDriver + Mesa + libdrm + libvulkan） |
| `EFI/Tools/` | 不存在 | **新增**（RPATH 修复 / 系统卷安装 / 回退 / profile 切换 / 校验） |

### 为什么必须解除 Exclude

`Kernel/Block` 的 `Strategy=Exclude` 会把该 bundle identifier **完全排除出 AuxKC**——连装在
`/Library/Extensions` 上的系统卷 kext 也不会加载。`XeGfxIntelFB` 正是靠系统卷 + AuxKC 生效的，
一旦被 Exclude，**显示接管、背光、HiDPI、合盖恢复会全部失效**（这正是 `5f0de92` 的实际状态）。

### 为什么 `OSBundleRequired=Root` 必须保留

`2bd94d1`（11-18 05:16）为了躲早期 panic 移除了这个字段。代价是 `XeGfxIntelFB` 无法在早期引导
接管 framebuffer，显示接管推迟到系统卷可写之后。**「先能开机」与「完整功能」在此直接冲突**，
本分支选择完整功能，并把 panic 风险交给回退流程兜底。

---

## 2. 部署步骤

### 第 0 步（Windows）：把 EFI 装到 EFI 分区

用你惯用的方式把 `EFI/` 目录内容拷到 EFI 分区的 `EFI/` 下。**先备份现有 EFI 分区。**

校验（可选但推荐）：

```
python tools\validate_efi.py --efi Z:\EFI
```

> 此时应该出现 3 条 RPATH 警告——这是**预期的**，下一步会修复。

### 第 1 步（macOS）：修复 Metal 栈的 @rpath

```
sudo /bin/bash /Volumes/<ESP>/EFI/Tools/prepare-metal-stack.command
```

这一步必须做。`libvulkan_intel.dylib` 来自 CI 构建，**没有 LC_RPATH**，靠 `@rpath/libdrm.2.dylib`
引用依赖——2026-11-17 19:26 的桌面接入失败（WindowServer 连续 SIGABRT 至 watchdog）就是这个原因。
脚本用 `install_name_tool` 补 `@loader_path` RPATH、重新签名，然后**逐个验证依赖可解析**并做空环境
加载测试。**验证不通过就不要继续部署。**

### 第 2 步（macOS）：安装系统卷组件

```
sudo /bin/bash /Volumes/<ESP>/EFI/Tools/full-install.command
```

按 11-15 ~ 11-17 实机验证过的顺序执行：

1. 备份 `/Library/Extensions`、`/Library/GPUBundles`、`nvrm610.conf`、`nvmtl-allow.txt` 到
   `/Users/Shared/Mubai-FullEFI-backups/<时间戳>/`
2. 移除已弃用的 `NMIntelFB.kext`
3. 安装 `XeGfxIntelFB.kext`（含 `OSBundleRequired=Root`），校验 `OSBundleRequired` 后读回
4. `kmutil install --volume-root / --update-all` 重建 AuxKC（第一轮）
5. 安装 `XeGfxAccel.kext`、`XeGfxAGDC.kext`
6. 再次重建 AuxKC（第二轮）
7. 校验安装结果并打印验收要点

### 第 3 步：正常重启并验证

重启后等约 3 分钟让开机脚本采集完成，然后回 Windows 读：

```
<EFI>/Diagnostics/reports/gpu-display-<时间戳>/
```

| 文件 | 期望内容 |
| :--- | :--- |
| `kextstat.txt` | `XeGfx`、`XeGfxIntelFramebuffer`、`NMXAccel` 都在列 |
| `status-first.txt` | `debug.xegfx_stage = 7` |
| `accel-30s.txt` | 呈现事务计数持续增长（不是 0） |
| `xeintelfb-ioreg.txt` | `XeGfxIntelFramebuffer` 节点存在 |
| `crashes/` | **应该为空**——有 panic 或 WindowServer 崩溃报告就说明这条路走不通 |

---

## 3. 回退

出现停在苹果标志、kernel panic 或桌面无显示时：

**Windows 侧**：

```
python tools\efi_profile.py --efi Z:\EFI --profile safe
```

**macOS 侧**（如果还能进系统）：

```
sudo /bin/bash /Volumes/<ESP>/EFI/Tools/full-rollback.command
```

SAFE profile 会：关闭 `XeGfxAccel`/`XeGfxAGDC` 注入、恢复 5 条实验性驱动 Exclude、去掉
`-xeintelfboff` 之外的激进项、换回只读的采集脚本。这是 `main` 分支当前的 apps-only 状态，
即 2026-11-18 10:25 之后磁盘上跑的那个配置。

---

## 4. 两套 profile 的对照

| | FULL | SAFE |
| :--- | :--- | :--- |
| 引导期注入 | XeGfx + XeGfxAGDC + XeGfxAccel | 仅 XeGfx |
| 实验性驱动 Exclude | 无 | 5 条全开 |
| 桌面合成 | 走 Metal（`nvaccelfb=1/3/4`） | 软件路径 |
| 开机脚本 | `Diagnostics/profiles/gpu-display-capture.full.command` | `...safe.command` |
| 启动引导 | 静默直通（ShowPicker=False） | 调试引导（ShowPicker=True, `-v`） |
| 已知风险 | 早期 boot panic 路径（11-18） | 桌面无 Metal 加速 |

切换：

```
python tools\efi_profile.py --efi <EFI 路径>            # 只看当前状态
python tools\efi_profile.py --efi <EFI 路径> --profile full
python tools\efi_profile.py --efi <EFI 路径> --profile safe
```

---

## 5. 这套 EFI 包含哪些已验证功能

| 功能 | 状态 | 依据 |
| :--- | :--- | :--- |
| 电池（`_BIF`/`_BIX` 1mV 修正） | ✅ | `a0ccba3`、`1be2ce3` |
| 音频 ALC235（AppleALC + SimpleHDA） | ✅ | `748c203` |
| Wi-Fi RTL8852BE（AirPort_RTW89 + Skywalk + AMFIPass） | ✅ | `83648b8` |
| 蓝牙（RealtekBluetoothFirmware + BlueToolFixup） | ✅ | 11-13 |
| 触摸板 GPIO 中断 | ✅ | `400daaa` |
| 摄像头 HS02 / USB UTBMap | ✅ | `d147a39` |
| 静默直通启动 | ✅ | `ec96645` |
| 防 S3 睡死（`pmset` 持久化） | ✅ | `4d9c885` |
| 显示接管（XeGfxIntelFB） | ✅ | `5a2bbd1` |
| 背光 NVRAM 记忆 | ✅ | `f72976a` |
| 合盖息屏 / 开盖亮度恢复 | ✅ | `22fb018`、`ce2213d` |
| HiDPI 1280×800 / 2560×1600 @165Hz | ✅ | `20404d4`、`5a2bbd1` |
| 桌面 Metal 合成（毛玻璃/圆角/头像菱形修复） | ✅ | `4ab0980` |
| IOSurface 共享内存 | ✅ 实装验证 | `520e4c6` |
| 低帧率与输入卡顿 | ❌ 未解决 | `ade4f6e` |

---

## 6. 尚未解决 / 未验证

1. **本 EFI 未经实机验证**——组装环境没有 macOS，无法确认能否开机。
2. **Metal 栈未实机验证**——NVMTLDriver 与 Mesa 是本次从 CI 产物包（run `44059572203` /
   `43615870360`）组装，`libvulkan_intel.dylib` 需在 macOS 上跑 `prepare-metal-stack.command`
   修复 RPATH 后才可用。
3. **`air-runtime/libLLVM.dylib` 缺失**——本机不存在该文件。若 macOS 系统卷的
   `/Library/GPUBundles/air-runtime/` 下也没有，NVMTLDriver 的 AIR 翻译可能不完整。
4. **共享内存实现未入库**——`patches/xg_xe_userptr.inc` 等文件不在仓库，userptr 内核二进制
   也没保留，本套 EFI 里的 `XeGfx.kext` 是 11-15 的 V35 基线，**不含** `xe_userptr` 功能。
5. **低帧率 / 输入卡顿**——已定位到 IOSurface 纹理创建与 ANV GEM 分配等待，未解决。
6. **Pipe Scaler**（>半屏缩放分辨率）——未实现。
