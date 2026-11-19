# 2026-11-20：开机跑码 / 启动项选择器、`--stage accel` 失败根因、背光修复载体核对

本文记录三件事的证据链：① 引导展示改为调试引导；② `full-install.command --stage accel` 在
`prepare-metal-stack.command` 成功之后**仍然必然失败**的根因；③ 「背光修复没上」这一疑问的
二进制级核对结论。

---

## 1. 引导展示：恢复 08ab2ba 那组调试组合

把 2026-11-18 04:45 的 `08ab2ba`（"restore ShowPicker=true, ScanPolicy=0, Timeout=5, Target=67
and -v boot-args"）那组参数套到全功能 EFI 上，**只改引导展示，不动 GPU 部分**：

| 键 | 值 | 说明 |
| :--- | :--- | :--- |
| `Misc/Boot/ShowPicker` | `true` | 关掉静默直通，每次开机出选择器 |
| `Misc/Boot/HideAuxiliary` | `false` | 辅助条目（OpenShell）可见 |
| `Misc/Boot/Timeout` | `5` | 选择器停留 5 秒 |
| `Misc/Boot/PickerMode` | `Builtin` | OpenCore 自带图形选择器 |
| `Misc/Security/ScanPolicy` | `0` | 放开扫描限制，恢复镜像/未签名安装器可选 |
| `Misc/Debug/AppleDebug` | `true` | 内核调试日志 |
| `Misc/Debug/Target` | `67` | 日志上屏 + syslog + 变量 |
| `Misc/Debug/DisplayLevel` | `2147483650` | 全部消息 |
| `Misc/Debug/LogModules` | `*` | 所有模块 |
| `NVRAM boot-args` | 前置 `-v` | 开机跑码 |

> `ScanPolicy` 在 `Misc/Security` 下，**不是** `Misc/Boot`。

与 `08ab2ba` 的 config 逐项比对：11 项**完全一致**（`Boot.ShowPicker` / `HideAuxiliary` /
`Timeout` / `PickerMode` / `PickerAttributes` / `Security.ScanPolicy` / `Debug.AppleDebug` /
`Debug.Target` / `Debug.DisplayLevel` / `Debug.LogModules` / `boot-args`）。

GPU 部分未受影响（实测）：`XeGfx` / `XeGfxAGDC` / `XeGfxAccel` 三者仍启用，
`Kernel/Block` 仍只有 `com.apple.iokit.IOSkywalkFamily` 一条 Exclude，
`XeGfxIntelFB.kext` 的 `OSBundleRequired=Root` 保留。

**连带修掉的回退隐患**：`EFI/Tools/efi_profile.py` 里固化的 FULL 基准原本还是旧的静默启动值，
切一次 profile 就会把 `-v` 和选择器改回去。现已同步为新值，并实测 FULL→SAFE→FULL 往返与
磁盘配置逐项一致（幂等）。

---

## 2. `--stage accel` 必然失败 —— 检查用错了工具

### 现象

`prepare-metal-stack.command` 跑完之后，`full-install.command --stage accel`（以及
`--stage all`）仍在**第 0 步前置检查**直接退出，错误信息是
「libvulkan_intel.dylib 仍未修复 RPATH —— 请先运行 prepare-metal-stack.command」。
错误信息本身是误导——prepare 已经跑过了。

### 根因

原检查（第 71–73 行）：

```bash
if ! otool -L "$GPU/vulkan/libvulkan_intel.dylib" 2>/dev/null | grep -q '@loader_path'; then
    die 'libvulkan_intel.dylib 仍未修复 RPATH —— 请先运行 prepare-metal-stack.command'
fi
```

- `otool -L` 只输出**依赖**（`LC_LOAD_DYLIB`）；
- `prepare-metal-stack.command` 用的是 `install_name_tool -add_rpath @loader_path`，加的是
  **`LC_RPATH`**，它只出现在 `otool -l` 的输出里，**不会出现在 `otool -L` 里**。

Mach-O 实测（`libvulkan_intel.dylib`）：

```
LC_LOAD_DYLIB:
  /usr/lib/libSystem.B.dylib
  @rpath/libdrm.2.dylib
  /usr/lib/libz.1.dylib
  /usr/lib/libexpat.1.dylib
  /usr/lib/libc++.1.dylib
LC_RPATH: (空)
```

依赖里没有 `@loader_path` → `grep -q` 必然失败 → **无论 prepare 有没有跑过，脚本都必然 die**。

### 修法

改查 `LC_RPATH`，并覆盖 prepare 会改的全部四个 dylib：

```bash
rpath_text="$(otool -l "$f" 2>/dev/null | grep -A3 'LC_RPATH' || true)"
if [[ "$rpath_text" != *@loader_path* ]]; then
    die "$(basename "$f") 缺少 @loader_path RPATH —— 请先运行 prepare-metal-stack.command"
fi
```

> 用 `grep -A3`（不带 `-q`）+ 命令替换，而不是 `grep -q` 管道：`grep -q` 提前退出会给上游
> 管道制造 SIGPIPE，在 `set -o pipefail` 下可能把成功判成 141。

同时把 `prepare-metal-stack.command` 的加 RPATH 逻辑改成**幂等**（已有 `@loader_path` 就跳过），
避免重复运行时堆叠多条 `LC_RPATH`。

另外补了一条 `--stage accel` 的前置提示：若 `/Library/Extensions/XeGfxIntelFB.kext` 不存在，
明确提醒加速桥依赖显示接管提供 framebuffer，应先跑一次 `--stage display`。

---

## 3. 「背光修复没上」的核对结论 —— **修复在二进制里**

### 提交链

| 提交 | 时间 | 改了什么 |
| :--- | :--- | :--- |
| `4aa92c0` | 11-16 19:31 | 入库 XeGfxIntelFB 二进制（73 440 B） |
| `f72976a` | 11-16 21:02 | **只改补丁脚本** `patches/patch_xegfxintelfb.py`（保持 `fHasSavedBl`），未重建二进制 |
| `22fb018` / `ce2213d` | 11-17 12:23 / 12:40 | 合盖息屏 + 开盖亮度恢复（源码改动） |
| `20404d4` | 11-17 15:52 | 恢复 `kDisplayModeValidForHiResFlag` 与面板物理尺寸（HiDPI） |
| `5a2bbd1` | 11-17 16:05 | **重建并入库二进制 99 248 B**，同时记录「合盖/开盖背光恢复 + HiDPI 1280×800 实机验证」 |

`f72976a` / `22fb018` / `ce2213d` / `20404d4` 经 `git merge-base --is-ancestor` 确认**全部是
`5a2bbd1` 的祖先**。当前二进制由 `5a2bbd1` 引入，晚于全部亮度相关源码改动。

### 二进制级验证（不依赖 README、不依赖提交信息）

在部署到磁盘上的 `XeGfxIntelFB` 二进制里直接搜 `f72976a` 引入的那段代码的特征字符串：

| 特征字符串 | 命中 |
| :--- | :--- |
| `ignoring early boot 255 brightness override` | ✅ |
| `ignoring early boot brightness` | ✅ |
| `ignoring early boot linear-brightness` | ✅ |
| `ignoring lid %u brightness override` | ✅ |
| `ignoring lid %u linear-brightness override` | ✅ |
| `clamshell closed (%s, saved preLid=` | ✅ |
| `clamshell opened (%s) -> restoring preLid=` | ✅ |
| `restored saved NVRAM brightness` | ✅ |
| `xeintelfb-bl` | ✅ |

前三条正是 `f72976a` 的 `fHasSavedBl` 早启保护——**修复确实编译进了当前二进制**。

### 磁盘原状未被回滚（部署前后逐字节核对）

2026-11-20 03:17 部署前做的备份 `backups/disk-efi-backup-20261120-031748` 保存了**磁盘原状**，
与仓库逐文件核对：

| 范围 | 差异 |
| :--- | :--- |
| `OC/`（118 文件） | 仅 `config.plist`（本次的引导展示改动） |
| `Diagnostics/`（27 文件） | 完全一致 |
| `Tools/`（4 文件） | 仅 `efi_profile.py`、`prepare-metal-stack.command`（本次改动） |

`XeGfxIntelFB` 二进制 SHA-256 两侧一致：`eb73a55739fcfe5096c2eabb027517ecfd425fdd8cb191013051f4bcd14da0ad`。

### 那为什么会「看起来没上」—— `SHA256.txt` 陈旧

`EFI/Diagnostics/GPU/SHA256.txt` 最后更新于 **11-16 19:31**（`4aa92c0`），当时只有 2 行，
列的是 `XeGfx.kext` 和一个早已不存在的 `xe-uapi-probe`。**里面根本没有 `XeGfxIntelFB.kext` 的条目**，
也没有 metal/vulkan 载荷的条目。对照这份清单看，自然会得出「亮度修复对应的 kext 不在清单里 →
像是没上」的结论。

现已重建为覆盖全部 21 个载荷的清单，并注明 `prepare-metal-stack.command` 会改动 metal/vulkan
下 dylib 的哈希（修复后的哈希记录在 `.rpath-fixed` 标记里）。

---

## 4. macOS 版本基线

- 本 EFI 的**实机验证基线是 15.6（24G84）**，整套调试链（NVMTL、completion bridge、`pmset`
  持久化、背光、合盖息屏）都在 15.6 上跑通。
- 15.8 = 24H23，Darwin 24.8，落在 `Kernel/Add` 的 `MinKernel=24.0.0` / `MaxKernel=25.99.99`
  区间内，**配置层面不需要为 15.8 改任何东西**。
- 但 `XeGfx` 是自研 kext，**15.8 的实际表现没有实机证据**。这一点不因为配置能过就改变。
---

## 5. 实机日志新发现：AGDC / Accel 的 AuxKC 注入返回 Invalid Parameter

2026-11-20 磁盘上新增了 10 份 OpenCore 日志（此前只有 11-18 的 15 份），说明当天实机开过多次机。
逐份对比 11-18 与 11-20 的日志：

### 11-18（5 条实验性驱动 Exclude 生效时）

```
OC: Prelinked blocker (Exclude) result 1 for org.watchthelight.XeGfxAccel  - Unsupported
OC: Prelinked blocker (Exclude) result 3 for org.watchthelight.XeGfxAGDC   - Unsupported
OC: Prelinked blocker (Exclude) result 4 for org.watchthelight.XeGfxIntelFB - Unsupported
OC: Prelinked blocker (Exclude) result 5 for com.nullmoth.NMIntelFB        - Unsupported
```

### 11-20（解除 Exclude 后，10 份日志里 9 份稳定复现）

```
OC: Prelinked injection XeGfxAGDC.kext  (Intel Xe2 AGDC display pipe bridge) - Invalid Parameter
OC: Prelinked injection XeGfxAccel.kext (Intel Xe2 IOAcceleratorFamily2 Metal bridge) - Invalid Parameter
```

`XeGfx.kext` 与 `XeGfxIntelFB.kext` **完全没有出现在日志里**——它们既不报错也不被提及。

### 判别规律

| kext | `OSBundleRequired` | `OSBundleLibraries` 是否引用**系统自带 prelinked kext** | 注入结果 |
| :--- | :--- | :--- | :--- |
| `XeGfx.kext` | 无 | 否（只有 kpi 族 + AppleACPIPlatform + IOPCIFamily） | 无错误 |
| `XeGfxIntelFB.kext` | `Root` | 否（kpi 族 + IOGraphicsFamily + IONDRVSupport + IOPCIFamily） | 无错误 |
| `XeGfxAGDC.kext` | `Root` | **是**：`com.apple.AppleGraphicsDeviceControl` | **Invalid Parameter** |
| `XeGfxAccel.kext` | `Root` | **是**：`com.apple.iokit.IOAcceleratorFamily2` | **Invalid Parameter** |

规律完全吻合：**带 `OSBundleRequired=Root` 且依赖系统自带 prelinked kext 的第三方 kext，
无法通过 OpenCore 的 prelinked injection 路径注入 AuxKC**，返回 `EFI_INVALID_PARAMETER`。
原因是把它们合并进 AuxKC 的 prelinked 集合时，解析依赖需要改动系统自带 kext 的集合结构，
注入器拒绝这样做。

这与 `2bd94d1`（11-18 05:16）移除三个实验性 kext 的 `OSBundleRequired=Root` 是同一件事的两面：

- 去掉 `OSBundleRequired=Root` → 注入可能通过，但**失去早期 framebuffer 接管**（XeGfxIntelFB 的核心价值）
- 保留 `OSBundleRequired=Root` → 注入报 `Invalid Parameter`，但这类 kext 本来就该走
  **系统卷 `/Library/Extensions` + `kmutil` 构建 BootKernelExtensions.kc`** 的路径

也就是说：`full-install.command` 把 AGDC / Accel / IntelFB 装到 `/Library/Extensions` 再跑
`kmutil install --volume-root / --update-all`，走的正是**不依赖 OpenCore 注入**的那条路，
与上面这条日志错误并不冲突。桌面加速桥能否生效，取决于系统卷那条路，不是 EFI 的 `Kernel/Add`。

> **未验证**：本次没有 macOS 环境，无法确认 `kmutil` 那条路在 15.8 上是否真的把三个 kext
> 收进了 BootKernelExtensions.kc。需要在实机用 `kextstat` / `kmutil showloaded` 核对。

### 附带确认：11-20 的引导改动已在实机生效

最新一份日志（`opencore-2026-11-20-124648.txt`）里：

```
AAPL: #[EB|MBA:OUT] <"-v keepsyms=1 msgbuf=1048576 -no_compat_check ...">
AAPL: #[EB|LOG:VERBOSE] 2026-11-20T12:46:50
```

`boot-args` 以 `-v` 开头，且内核进入 **VERBOSE** 模式——开机跑码在实机上确实生效了。


---

## 6. Metal 栈的 RPATH 修复：改到 Windows 侧完成

上一节确认了磁盘上的 Metal 栈**完全没有修复**（四个 dylib 都没有 `LC_RPATH`，
`.rpath-fixed` 标记也不存在），说明 `prepare-metal-stack.command` 那次没跑成功。

原本的修复路径是「在 macOS 上跑 `prepare-metal-stack.command`」，但该脚本依赖
`install_name_tool` 与 `codesign`，只能在 macOS 上执行。本次改为**把结构修复搬到 Windows 侧**：

### 新增 `tools/patch_macho_rpath.py`

纯 Python 的 Mach-O 改写器，做两件事：

1. 在 load command 区末尾与首个 section 之间的**空闲区**插入一条
   `LC_RPATH @loader_path`（32 字节），并更新 header 的 `ncmds` / `sizeofcmds`；
2. 改写 `LC_ID_DYLIB`（`libvulkan.1.dylib` → `@rpath/libvulkan.dylib`，
   `libdrm.2.dylib` → `@rpath/libdrm.2.dylib`）。

关键约束是**不改变文件大小**：

| 文件 | 插入位置 | 头部余量 | 文件大小 | 段布局 | `LC_CODE_SIGNATURE` 偏移 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `libvulkan_intel.dylib` | 2264 | 6312 B | 不变 | 不变 | 不变 |
| `libvulkan.1.dylib` | 1576 | 3112 B | 不变 | 不变 | 不变 |
| `libdrm.2.dylib` | 1504 | 3072 B | 不变 | 不变 | 不变 |
| `libnvmtl_translate.dylib` | 2032 | 160 B | 不变 | 不变 | 不变 |

插入点全部落在首个 4096 字节页内，因此 `__LINKEDIT` 不移动、段偏移不变、
签名 blob 的 `codeLimit` 不变。逐字节比对确认：**每个文件的改动字节全部 < 4K**
（libvulkan_intel 18 B / libvulkan.1 25 B / libdrm 72 B / libnvmtl_translate 18 B）。

改写后由工具自身**重新解析并逐项校验**（文件大小、段布局、签名偏移、依赖列表、
load command 是否越界、LC_RPATH 是否存在、install name 是否符合预期），
任何一项不符就拒绝写盘。

> 开发过程中这个校验层抓到一个真 bug：改写 `LC_ID_DYLIB` 时切片终点算错，
> 导致字节数组被截短、后续内容整体位移。**是校验层先发现的，没有写坏文件。**
> 修好后补丁里又加了两处长度断言。

### 签名怎么办

`libvulkan_intel.dylib` 与 `libnvmtl_translate.dylib` 原本带 `LC_CODE_SIGNATURE`，
改头页后签名失效（这两个会被加载进 WindowServer，库校验要求签名有效）。
另两个原本就没签名。

因此 **macOS 侧仍必须跑一次 `prepare-metal-stack.command`**——但它的职责从
「修结构」变成「重签名 + 实载验证」。脚本现在会：

1. 幂等跳过已有的 `@loader_path`（不再重复添加）；
2. 幂等跳过已正确的 install name；
3. `codesign -f -s -` 重签名；
4. 逐个验证 `@rpath` 依赖在同目录可解析；
5. 做一次**空环境 `ctypes.CDLL` 加载测试**（不使用 `DYLD_LIBRARY_PATH`）；
6. 全部通过后写 `Diagnostics/GPU/.rpath-fixed` 标记。

第 4、5 步是**真正的 dyld 实载验证**——Windows 侧只能验证结构，验证不了实际加载。

### 校验器同步修正

`tools/validate_efi.py` 原来按 EFI 里的源目录判断 `@rpath` 能否解析，
对 `libvulkan.1.dylib`（部署时改名为 `libvulkan.dylib`）会误报
「同目录没有 libvulkan.dylib」。已改为按**部署后的真实布局**判断：
所有 dylib 平铺到 `/Library/GPUBundles/nvmtl/`，并套用改名映射。

结果：**0 错误 0 警告**（改前是 0 错误 3 警告）。
