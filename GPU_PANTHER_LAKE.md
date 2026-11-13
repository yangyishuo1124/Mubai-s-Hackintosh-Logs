# Panther Lake B0A0 核显适配 / GPU bring-up

2026-11-13 · ASUS S5650AA · Intel `8086:B0A0` · macOS 26.0 `25A354`

## 当前结论 / Current conclusion

第二次实机尝试：EFI 和 macOS 本地副本的所有散列均通过，99:99 所有权错误不再出现。kmutil 改为报告 `org.watchthelight.XeGfx not approved to load`，要求通过系统设置批准。驱动仍未加载，debug.xegfx_stage/results/log 均未注册，未运行 stage 2。当前是加载策略阻塞，不是已证实的 GPU 探测失败。下一步先查看 macOS「系统设置 → 隐私与安全性」是否提供允许按钮；仅批准这次 XeGfx，若系统要求则重启，再运行脚本。如无批准入口，应记录界面情况继续调查，避免重复相同测试。未更改安全策略、驱动或开机配置。

Second hardware attempt: every hash on EFI and the local macOS copy passes; the 99:99 ownership error is gone. kmutil now reports `org.watchthelight.XeGfx not approved to load` and requests System Settings approval. The driver has not loaded, its debug.xegfx_stage/results/log controls are absent, and stage 2 has not run. This is a loading-policy blocker, not an established GPU-probe failure. Next inspect System Settings → Privacy & Security for an approval control, approve only this XeGfx attempt, restart if requested, then rerun the wrapper. If no approval control exists, record the UI state for further investigation rather than repeating the same test. No security-policy, driver or boot-configuration change was made.

Apple reference / 苹果说明：[User-approved kernel extension loading](https://support.apple.com/en-gb/guide/deployment/depa5fb8376f/web).

首次实机尝试：驱动全部文件散列通过，但 kmutil 在加载前拒绝 EFI FAT 上的 99:99 所有权（要求 0:0）。未注册 debug.xegfx_stage，没有执行硬件探测；不能据此判定 B0A0 不兼容。已修正脚本：先复制到 /private/var/tmp 下的独立本地目录，设置 root:wheel 和受限写权限，再次验证散列后从本地加载。未安装至 /Library/Extensions，未更改开机配置；本地临时副本保留用于诊断。新版加载效果尚待实机验证。

First hardware attempt: every bundle hash passed, but kmutil rejected the EFI FAT ownership (99:99 instead of 0:0) before loading. No debug.xegfx_stage was registered and no hardware probe ran; this does not establish B0A0 incompatibility. The wrapper now copies to a unique /private/var/tmp directory, sets root:wheel and restricted write permissions, rechecks hashes, then loads the local copy. No /Library/Extensions installation or boot configuration change; the temporary local copy is retained for diagnosis. Loading this revised wrapper remains hardware-unverified.

本机仍使用 GOP 基础显示，无已验证 Metal 加速。调查发现 InSnh-Gd 的 WTLIntelGfx 分支已超出最初的移植计划：包含 xe 构建选择、Panther Lake 补丁、B0A0 PCI 匹配和分阶段硬件探测代码。不能据此宣称已支持本机；最新集成记录只验证 C 对象，尚未完成新版 C++ 链接或 PTL 实机测试。

This machine still uses GOP with no verified Metal acceleration. The InSnh-Gd WTLIntelGfx fork now contains more than its original port plan: xe build selection, Panther Lake patches, a B0A0 PCI entry and staged hardware probing. This is not proof of support: its latest integration record covers C objects, not a new complete C++ link or PTL hardware validation.

## 固定源码 / Pinned sources

| Source | Revision |
| --- | --- |
| [WTLIntelGfx fork](https://github.com/InSnh-Gd/WTLIntelGfx) | `5ffc79fb9e53eb820899edd644b83681bea3aa39` |
| [Xe3 SR-IOV experiment](https://github.com/ericek111/vibe-nullmoth-xe3-qemu) | `7246d386e94a2f5e8fe4f8a17099d11514b0ae40` |
| WTLKcAbi | `99808a2dcd645b971eaa19a65ca9e94682892ddb` |
| Linux | `38fec10eb60d687e30c8c6b5420d86e8149f7557` (v6.14) |
| drm-kmod | `c16de0f9fa` |
| FreeBSD | `9da2c05a748fd17757638e1a9e78215cdb8b80d0` |

入口 / Read first: [xe-build.md](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/docs/xe-build.md), [PTL patches](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/docs/xe-ptl-patches.md).

## 可验证的下一步 / Testable next steps

1. 完整构建 xe kext，检查架构、链接、公开 KPI、同名符号和签名；当前复现流程见 `.github/workflows/xe-build.yml`。
   Build the complete xe kext; verify architecture, link, public KPIs, symbol shadowing and signature using the workflow.
2. 首次实机仅运行 stage 2，记录真实 graphics/media GMD_ID、BAR、GOP 布局；不从 B390 的 B080/B082 推断 B0A0 的全部参数。上游称其为只读寄存器探测，但它会映射硬件并读取帧缓冲，仍未在本机验证。
   First hardware trial should stop at stage 2 to capture actual graphics/media GMD_ID, BARs and GOP layout. Do not infer every B0A0 parameter from B080/B082. Upstream describes a read-only probe, but it maps hardware and reads the framebuffer and is unverified here.
3. 只有探测结果和原显示布局通过后，才准备 GuC 固件和后续 GT 初始化、执行测试。当前构建流程**不带 GuC 固件**，不能用于宣称 stage 4+ 可用。
   Only after validating probe output and the original scanout should GuC firmware and later GT/engine trials be prepared. The current workflow **does not bundle GuC firmware** and does not establish stage 4+ readiness.
4. Metal 还需要 accelerator、ANV、libdrm 和用户态插件配套。仅链接内核驱动不代表 WindowServer 加速或内屏输出完成。
   Metal additionally needs the accelerator, ANV, libdrm and userspace plugin. A linked kernel driver alone does not establish accelerated WindowServer or panel output.

## 与已有演示的区别 / Scope of existing demonstrations

[XPS Iris Xe](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) 使用 Apple Tiger Lake 驱动适配 Raptor Lake，不能直接套到 Xe3。[Xe3 演示](https://github.com/ericek111/vibe-nullmoth-xe3-qemu) 使用 Linux 管理的 SR-IOV VF 和虚拟显示输出；裸机 PF 初始化、GuC 与内屏显示责任不同。

The XPS project adapts Apple's Tiger Lake driver to Raptor Lake and is not a direct Xe3 solution. The Xe3 demonstration uses a Linux-managed SR-IOV VF and virtual display; bare-metal PF initialization, GuC and physical-panel ownership are different tasks.

## 已生成手动探测包 / Manual probe package built

完整构建已生成 3,253,520 字节 x86_64 kext，链接、442 个未定义符号的 KPI 校验、同名符号检查通过。首次完整任务在最后的宿主测试因 bzero 宏重定义失败；修正测试宏兼容后，对同一二进制重新检查架构、签名及 KPI，16/16 宿主测试通过。0159 补丁仅重新生成完整上下文，未更改语义。构建使用 Sequoia Intel 环境；本机 Tahoe 26.0 的实际加载和 ABI 仍待验证。

The complete build produced a 3,253,520-byte x86_64 kext with link, 442-symbol KPI and shadow checks passing. The initial complete job failed in the final host tests due to a bzero macro redefinition. After fixing that test compatibility issue, the same binary passed architecture, signature and KPI verification and all 16 host regressions. Patch 0159 only receives complete unified context, with unchanged semantics. Build verification used an Intel Sequoia environment; actual loading and ABI behavior on this machine's Tahoe 26.0 remain unverified.

- [Build / 构建](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43428309279)
- [Successful verification / 成功复核](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43429886489)
- Binary SHA-256: `9ce455258ebd569b5db8cbe1593da83f923909ee5298bf0c767eeddbcf6b222f`

探测文件位于 `EFI/Diagnostics/GPU`，未加入 OpenCore Kernel/Add，未安装至系统卷或辅助内核集合。脚本手动加载，仅运行 stage 2，自动采集报告。此阶段没有 GuC 固件、引擎执行或 Metal 初始化；重启后不会自动加载。仅已完成构建与脚本验证，尚未证明本机硬件探测成功。

Files live in `EFI/Diagnostics/GPU`, outside OpenCore Kernel/Add, with no system-volume or AuxiliaryKC installation. The wrapper manually loads the kext, stops at stage 2 and collects a report. There is no GuC firmware, engine execution or Metal initialization in this trial; it is not configured to load at next boot. Build/script verification does not establish a successful hardware probe.

挂载 SYSTEM EFI 后运行 / After mounting the SYSTEM EFI:

```sh
sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/gpu-probe.command
sudo diskutil unmount /Volumes/SYSTEM
```

若加载失败，脚本停止并采集，不自动修改系统安全设置。 / On load failure the wrapper stops and collects diagnostics; it does not automatically change security settings.
