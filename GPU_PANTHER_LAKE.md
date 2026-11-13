# Panther Lake B0A0 核显适配 / GPU bring-up

2026-11-13 · ASUS S5650AA · Intel `8086:B0A0` · macOS 26.0 `25A354`

## 当前结论 / Current conclusion

### B0A0 显存访问阻断修订 / CPU-access containment revision

部署完成：新驱动完整构建、链接/KPI/签名/架构检查及原有 16 项测试、新增阻断分支测试全部通过。[构建记录](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43440462656)。已备份并替换硬盘 EFI 开机副本、签名诊断副本和探测脚本，读回一致，ocvalidate 通过，开机配置未变。新二进制 SHA-256：`3ad564ca02e5d91324f7392b897b709f4e0e75fab66218e4c05b24f868f5461b`。实机效果待重启验证。

Deployed after a successful complete build, link/KPI/signature/architecture checks, all 16 existing tests and the new compiled containment test. Boot copy, signed diagnostic copy and wrapper on the internal EFI were backed up and replaced, with matching readback and clean ocvalidate. Boot configuration is unchanged. Binary SHA-256 is shown above. Hardware behavior remains unverified until reboot.

下一次 macOS 启动后运行 `sudo zsh /Volumes/SYSTEM/EFI/Diagnostics/gpu-probe.command`。B0A0 预期 stage 1 通过、stage 2 返回不支持并留下元数据；脚本不应进入显存像素校验。阶段返回失败是本版的预期阻断结果，不应手动推进 stage 3 或后续阶段。

After the next macOS boot, run the wrapper. Expected B0A0 behavior is successful stage 1, unsupported/incomplete stage 2 with metadata preserved, and no CPU pixel checksum. The failed stage is intentional containment; do not manually advance to stage 3 or later.

新增 `patches/xe-ptl-metadata-only.patch`：保留 DSM/MMIO 和完整 GOP 页表遍历，发布候选物理范围、页数、DM 页数及 PTE 散列。在 B0A0 上释放页表临时数组后返回 `-EOPNOTSUPP`，不调用 `xg_vm_vmap_pa`，不执行像素读取，不建立 GOP baseline，stage 2 不得标为完成。此修订用于阻断已观察到的崩溃路径并采集元数据，不是 Metal 或显存访问修复。

The new patch retains DSM/MMIO and GOP page-table inspection, publishing the candidate physical range, page count, DM-page count and PTE hash. On B0A0 it frees the temporary page array and returns `-EOPNOTSUPP` before `xg_vm_vmap_pa` or pixel reads, without establishing a GOP baseline or completing stage 2. This contains the observed crash path and collects metadata; it is not a Metal or framebuffer-access fix.

脚本仅在实际加载的 XeGfxResident 发布 `XeGfxProbePolicy=ptl-metadata-only-v1` 时才允许触发，旧驱动不会因替换 EFI 文件而被误运行。新增测试编译并执行实际阻断分支，覆盖 DM、非 DM 页和其他设备对照；完整构建结果见后续部署记录。

The wrapper requires the loaded XeGfxResident to publish the exact metadata-only policy before triggering the probe, preventing an old resident binary from running after files on EFI change. A new compiled test executes the actual containment branch for DM/non-DM pages and an alternate-device control. Full build and deployment results are recorded below when available.

### 崩溃证据更新 / Crash evidence update (22:01 collection)

已采集到 macOS machine-check panic。MC10–MC15 报告地址分别落在 `0x7c800000`、`0x7c800040`、`0x7c8000c0`、`0x7c800100`、`0x7c800140`、`0x7c8001c0`；状态为 `0xbe0000000080113a` 或 `0xfe0000000080113a`。这些地址落在修订版由 DSMBASE 和首个 DM PTE 推导的 GOP 物理显存起始区域。`xg_xe_bootfb_checksum()` 每 64 字节直接读取映射像素，和报错地址间距吻合，因此 CPU 直接访问 stolen/GOP 显存是首要故障路径。报告没有指令回溯，尚不能区分地址解释、CPU 访问限制或缓存属性问题；不能据此诊断 CPU 硬件损坏。

The new collection contains a macOS machine-check panic. Banks MC10–MC15 report addresses within `0x7c800000–0x7c8001c0`, with status `0xbe0000000080113a` or `0xfe0000000080113a`. This is the GOP physical-memory start derived from DSMBASE and the first DM PTE in the revised probe. `xg_xe_bootfb_checksum()` directly samples mapped pixels every 64 bytes, matching the reported address spacing. Direct CPU access to stolen/GOP memory is therefore the leading fault path. The report contains no instruction backtrace, so address interpretation, CPU access restrictions and cache attributes remain unresolved; this does not establish defective CPU hardware.

本次启动 `debug.xegfx_stage=0`，未重跑 stage 2。开机驱动保留，采集脚本的阻断继续生效。本轮未替换驱动二进制。下一版需要先分离寄存器/GGTT 元数据采集与 CPU 像素访问；DM 页未确认访问规则前应拒绝映射/校验，并保留失败返回值，不能把跳过像素校验当成 GOP 保留或 stage 2 成功。暂不要求再次重启测试。原始 panic 和 NVRAM 留在本地，仅提交去标识后的结论。

The current boot reports `debug.xegfx_stage=0`; stage 2 was not retriggered. Boot injection remains enabled and the collection-only gate remains in place. No driver binary was replaced in this round. The next revision must separate register/GGTT metadata inspection from CPU pixel access. Until DM-page access rules are established, mapping/checksum access must fail closed; skipping pixel validation cannot count as GOP preservation or successful stage 2. No further reboot test is requested yet. Raw panic/NVRAM data stays local; only this sanitized finding is published.

Earlier entries below describe preceding experiments and their evidence at the time. / 以下为此前各轮记录，不代表当前验证状态。

MMIO 修订版实测失败：用户报告运行探测即黑屏重启，最新日志仅保留文件散列检查，未完成 stage 2 或保存返回值。无法据此判断 panic、机器检查异常或具体故障指令。GOP 页表遍历、保留显存物理地址换算、映射和像素校验均仍在调查范围，不能宣称 MMIO 修订已解决 -22。已将 gpu-probe.command 临时改为采集后退出，保留 EFI 开机驱动及配置，不恢复手动加载；collect.command 新增最新内核 panic 文件、有限 NVRAM 崩溃键和近 30 分钟内核 XeGfx/panic 日志。原始崩溃报告只在本地，不上传标识信息。下一步仅运行采集，先取得上一次崩溃证据，不重复 stage 2。

The MMIO revision failed on hardware: the user reports an immediate black-screen reboot on probing. The latest log ends after bundle hash checks, without a completed stage 2 or return value. It does not establish a panic type, machine-check cause or faulting instruction. GOP page traversal, stolen-memory address translation, mapping and pixel checksum reads remain under investigation; the -22 repair is not established. gpu-probe.command now collects and exits without invoking stage 2. EFI boot injection and the driver are retained. The collector adds recent kernel panic files, selected panic NVRAM keys and 30 minutes of filtered kernel XeGfx/panic logs. Raw reports and identifiers remain local. The next boot is for collecting previous-crash evidence only, without rerunning stage 2.


DSMBASE MMIO 修订版已完成完整编译、链接、KPI、同名符号、签名、架构及 16/16 测试检查，已备份并替换 EFI 开机副本及签名诊断副本，散列清单同步更新，读回与仓库一致、ocvalidate 通过。开机注入配置保持不变。新版实际 GOP 探测仍待验证；不将编译通过视为 -22 已解决。

The DSMBASE MMIO revision passes the complete build/link, KPI, shadow, signature, architecture and all 16 host tests. Boot and signed diagnostic copies are backed up and replaced, with manifests refreshed, matching readback and ocvalidate passing. Boot-injection configuration is unchanged. Hardware GOP probing remains pending; build success does not establish that -22 is fixed.

[Build / 构建](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43435179850) · Binary SHA-256: `3fa08422711ccc2075702ba6237fdd54d36fb2e3afa82e1b93334e594f4fac7d` · Source adjustment / 源码修订: `patches/xe-ptl-dsm-mmio.patch`


开机加载实测成功：XeGfxResident 为 active 且 IOMatchedAtBoot = Yes，stage 1 自检通过。stage 2 读取到 B0A0、graphics GMD_ID 0x07804000、media GMD_ID 0x07800004、16 MiB BAR0、256 MiB BAR2 和 2560×1600 GOP，随后返回 -22；debug.xegfx_stage 保持 1，不能将表示已尝试的 XeGfxStage=2 视为通过。当前探测代码在 GOP 页遍历阶段仍使用 PCI 0xc0/c4 获取 DSM 基址，新补丁改为 MMIO DSMBASE 0x1080c0/c4，并增加失败页号/PTE 诊断。MMIO 来源依据 Linux v6.14 xe_regs.h 和 stolen manager 的定义；修复效果待实测。后续 stage 4 的 stolen 保留补丁仍需单独检查，当前不进入 stage 4。

Boot injection is confirmed: XeGfxResident is active with IOMatchedAtBoot=Yes and stage 1 passes. Stage 2 reads B0A0, graphics GMD_ID 0x07804000, media 0x07800004, 16 MiB BAR0, 256 MiB BAR2 and 2560×1600 GOP, then returns -22. Completed-stage sysctl remains 1; the attempted-stage registry property 2 is not a pass. The GOP page walk still reads DSM from PCI 0xc0/c4. A new patch uses MMIO DSMBASE 0x1080c0/c4 and reports failing page/PTE, based on Linux v6.14 register definitions and stolen-manager behavior. Hardware validation is pending. Stage-4 stolen reservation still requires separate review; stage 4 is not attempted.


按用户要求，现已启用 EFI Kernel/Add 的 XeGfx.kext（x86_64 Darwin 25），IOResourceMatch 改为 IOKit。二进制不变，开机副本移除失效签名，原签名副本及配置已备份。读回一致、ocvalidate 通过；加载尚待重启验证。stage 2 仍由脚本触发，不自动初始化 GuC/Metal。脚本仅使用开机驱动，不再手动加载或重试审批。

At the user's request, XeGfx is enabled in EFI Kernel/Add for x86_64 Darwin 25, matching the IOKit resource. Binary unchanged; stale signature omitted from the boot copy, with original signed bundle and configuration backed up. Readback and ocvalidate pass; boot loading is unverified. Stage 2 remains script-triggered; no automatic GuC/Metal initialization. The wrapper now requires the boot-resident driver rather than retrying manual approval.


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
