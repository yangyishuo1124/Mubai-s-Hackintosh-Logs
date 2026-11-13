# Panther Lake B0A0 核显适配 / GPU bring-up

2026-11-13 · ASUS S5650AA · Intel `8086:B0A0` · macOS 26.0 `25A354`

## 当前结论 / Current conclusion

### 追踪版实机：已进入 xe，最后日志在 stolen 分配器前 / Trace build reaches xe

用户截图中所有资源校验通过，但 stage 请求未返回。Windows 只读 NVRAM 得到 `s4 p11098`，按新编号规则是 pass 1、索引 49 的 GPU SYSINIT 入口。该键还保存了随后驱动日志：GOP GGTT 原范围为 `0xff000000 + 0xfa0000`（分配器交集 `0 + 0`）；两次读取并识别 `xe/ptl_guc_70.bin` 70.72.1；最后打印 `GOP DSM 0x7c800000: exclude prefix 0xfa0000 bytes`。

The trace build still hangs. The screenshot shows successful file checks, not a completed stage. Read-only Windows NVRAM recovery yields `s4 p11098`, the GPU SYSINIT entry (pass 1, index 49), followed by xe driver logs reporting the GOP range, reading/recognizing GuC 70.72.1 twice, and finally excluding the GOP prefix from DSM allocation.

这次已越过 linux_current 初始化；此前的 p1035 不能再作为当前故障位置，也不能据此声称线程初始化已修复——同步追踪可能改变了执行时序。GuC 文件读取/版本识别不代表固件已上传、运行或启用提交。GOP allocator 的 `0 + 0` 表示该高地址 GOP 与分配器可分配区间无交集，不等于原 GOP 范围为空。

This attempt passed linux_current initialization; the earlier p1035 is not the current failure location. Timing changes from synchronous tracing may explain the different progress, so no thread-init fix is claimed. Firmware recognition does not prove upload, running GuC or submission. The empty GGTT allocator intersection does not mean the original GOP footprint is empty.

紧接最后日志的候选路径为 `__xe_ttm_vram_mgr_init`（mutex、TTM resource manager、drm_buddy、managed cleanup 注册）以及之后 `devm_ioremap_wc` 的 stolen CPU 别名映射。仅凭最后日志不能确认卡在其中哪一步，也不能把它直接归为此前的像素读取 MCE；需在这些调用前后增加同步检查点。现有入口检查点说明 xe module callback 尚未返回。

Candidate paths after the final message include VRAM-manager lock/TTM/buddy initialization and managed cleanup, then the stolen CPU alias mapping. The trace does not identify which call hangs, nor establish the previous CPU pixel-read MCE as the cause. These calls need internal entry/return checkpoints. The GPU module callback has not returned.

原始追踪已本地保存；本轮保留开机驱动及配置，不替换二进制。脚本暂停重复初始化，仅采集；当前不要求再次重启收同一组数据。

Raw traces remain local. Boot driver/configuration and binary are retained. The wrapper collects only until the next targeted revision; no repeat reboot/collection is requested in this round.

### 重启后证据与同步追踪版 / Reboot evidence and synchronous trace revision

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43457167633)：编译、链接、KPI、架构、签名、固件嵌入及全部原有测试通过。检查点标签已确认在链接后二进制中存在。已备份并部署 EFI 开机/诊断驱动、资源与脚本，读回一致，ocvalidate 通过，配置不变。驱动 SHA-256：`7e063ed791d26206d9505441f4e536de35bb782fe63cc801dfbfc0d6f7e2094e`。新版的持久检查点实机效果尚待验证；可在下一次启动后运行一次 stage 4 探测，卡死后从 Windows 只读读取 NVRAM，不反复重跑。

Compilation/link/KPI/architecture/signature, embedded firmware and all existing tests pass; checkpoint labels are present in the linked binary. Boot/diagnostic bundles, resources and wrapper are backed up and deployed to EFI with matching readback and clean ocvalidate. Configuration is unchanged. Hardware checkpoint behavior remains unverified. The next boot can perform one stage-4 localization attempt; after a hang, read NVRAM from Windows without repeatedly retriggering.

重启后完整采集无新增 panic；当前 stage/progress/running 均为 0，没有重新执行 stage 4。仍以先前 Windows 从 NVRAM 读出的 `s4 p1035` 为定位依据。没有新 panic 不表示先前没有卡死，也不提供额外的故障指令证据。

The post-reboot collection contains no new panic; stage/progress/running are zero and stage 4 was not retriggered. The prior Windows-recovered trace remains the primary evidence. Absence of a new panic neither disproves the hang nor identifies a faulting instruction.

新增 `patches/instrument_sysinit.py`：每个 SYSINIT 调用前后同步保存检查点，编号为进入 `10000 + pass*1000 + index*2`、返回为进入值+1。linux_current 内部编号 20001–20008，依次为入口、current zone 创建前/后、mm zone 创建前/后、线程析构事件注册前/后及 current 分配函数安装后。不跳过原初始化，也不修改分配器、锁或事件处理逻辑。

The new instrumentation synchronously persists SYSINIT entry/return checkpoints and eight internal linux_current steps. It preserves every initializer and does not alter allocator, lock or event-handler semantics. Entry codes are 10000 + pass*1000 + index*2; return codes are entry+1. Internal codes 20001–20008 cover entry, both zone creations, destructor registration and allocator installation.

新加载策略为 `ptl-stage4-trace-v5`，脚本只接受该版本。NVRAM 同步发生在释放日志 spin lock 之后；同步追踪本身会改变时间行为，若出现新卡点也需考虑追踪写入路径，不能把最后保存的标签直接当成精确故障指令。stage 5+ 边界和禁止像素访问保持，下一次依然是 stage 4 定位实验，尚未修复卡死。

The wrapper requires the new trace policy. NVRAM synchronization occurs after releasing the log spin lock. Synchronous tracing changes timing and can itself affect execution, so a final persisted label is not proof of the exact failing instruction. Stage 5+ remains blocked and CPU pixel access remains disabled. This is a stage-4 localization experiment, not a hang fix.

### stage 4 卡死：持久追踪 s4 p1035 / Stage-4 hang: persistent trace

用户实测运行即系统卡死。EFI 探测记录停在 stage 请求处，无完整新采集。Windows 只读读取 Apple NVRAM 的 `xegfx-step` 成功，最后保存 `s4 p1035`；另两个追踪键不存在。根据该构建 Mach-O 的 `__xg_set` 表及 SYSINIT 的 subsystem/order 排序，1035 对应 pass 0、索引 35 的 `_linux_current_sys_init`（`linux_current_init`）。其结构已按所用 FreeBSD 的 sysinit 布局核对；这是兼容层线程初始化，非 GPU driver pass 1。

The hardware attempt hung before completing collection. Read-only Windows firmware-variable access recovered `s4 p1035`. Matching this exact binary's linker set and subsystem/order sorting identifies pass 0 index 35 as the LinuxKPI current-thread SYSINIT. This is before the GPU-driver pass, not evidence of GuC execution.

追踪为周期持久化，因此 1035 只是最后保存位置；实际停止点可能是该入口或后续紧邻入口，尚不能定位具体语句。`linux_current_init` 包括 UMA zone 建立和 thread_dtor 事件注册，shim 的 UMA reserve/prealloc 本身为空实现，不能据此假定预分配耗尽。需要增加每个 SYSINIT 入口/返回的同步追踪及函数内部检查点，不能直接跳过线程初始化来推进。

The trace is periodic: the actual stop may be in this or a subsequent nearby initializer, and no exact statement is established. The function creates UMA zones and registers a thread destructor; reserve/prealloc are no-ops in this shim, so allocation exhaustion cannot be inferred from them. Further localization needs synchronous entry/exit checkpoints and internal checkpoints, not bypassing current-thread initialization.

保留开机驱动和配置，仅将探测脚本改为采集后退出，避免重跑已卡死的路径。采集脚本补齐真实键 `xegfx-step-prev`、`xegfx-accel` 和阶段状态。原始报告只保留在本地；本轮未替换驱动二进制。下一次 macOS 仅采集上次卡死/panic 证据。

Boot injection and configuration are retained; the wrapper now collects and exits without repeating stage 4. The collector adds the actual previous-trace key, acceleration trace and stage state. Raw reports stay local. No driver binary is replaced in this round; the next macOS action is collection only.

### stage 3 已通过，推进 GuC/GT stage 4 / Stage 3 passed; advancing to GuC/GT

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43452344154)：阶段边界/快照/阻断及原有 16 项测试通过；编译、链接、KPI、签名、架构、固件资源和内嵌数据检查通过。已备份并部署硬盘 EFI 开机/诊断副本、资源和脚本，读回与固件散列核验通过，ocvalidate 正常，配置不变。驱动 SHA-256：`a45501203b28d657b10f18cf205636739f016bb2eff10a1561444d71892db9fe`。GuC/GT 实机运行状态尚未验证。

All boundary/snapshot/containment and 16 existing tests pass, with compile/link/KPI/signature/architecture and resource/embedded firmware checks passing. Boot/diagnostic bundles, resources and wrapper are backed up and deployed to the internal EFI; readback, firmware hashes and ocvalidate pass. Configuration is unchanged. Driver SHA-256 is shown above. Hardware GuC/GT operation remains unverified.

重启后运行现有探测脚本，目标为 stage 4，失败时不继续手动推阶段。若黑屏重启，回到 Windows 读取阶段追踪，再收集 macOS panic；不把资源校验或 stage 3 成功当成 GuC/GT 成功。

After reboot the wrapper targets stage 4. Do not manually advance after failure. A black-screen reboot requires examination of stage traces and subsequent panic collection. Resource validation or a stage-3 pass is not a GuC/GT success.

最新实机采集：stage 1/2/3 均返回 1，完成阶段为 3。`XeGfxPost.result=1`、`metadata-unchanged=1`、`frmcount-delta=17`、`pixel-verified=0`，页表散列仍为 `0x765b28479d6be205`。newbus 已绑定 vgapci，drmn 节点尚未绑定驱动，符合 SYSINIT 未运行的阶段。shim 报告无 IOMMU，DMA 地址为物理地址。`older than gen11` 是 shim 旧设备列表未识别 B0A0 的诊断文本，不是硬件世代判断；xe 的 DSM 保留使用已修订的 MMIO 路径。

The latest hardware run completes stages 1–3 with successful post-bus GOP metadata validation and frame delta 17; pixels remain unverified. vgapci is attached, while drmn remains unbound before GPU SYSINIT. The shim reports no IOMMU and physical DMA addresses. Its old device-list message incorrectly labels the unrecognized B0A0 as older than gen11; this is not a hardware-generation finding. The xe reservation path uses the corrected MMIO DSM discovery.

本轮加入固定 linux-firmware `bda6eccc3a8f` 的原样 PTL GuC，附原许可，散列 `ac42861c62b69f19923d9a69d971fb849921585a01924e14c0e8ac679d7cde81`。构建要求资源文件、内嵌固件及许可均存在且散列吻合。新策略 `ptl-stage4-guc-v4` 允许 stage 4 SYSINIT/GuC/GT 初始化并执行 GOP 元数据和 GT 状态检查；stage 5 及以后在执行测试之前阻断，不发布 Metal 加速设备。

This revision adds the unmodified pinned PTL GuC with its original licence. Build checks require matching resource and embedded firmware plus the licence. The new policy permits stage-4 SYSINIT/GuC/GT initialization with GOP metadata and GT checks, but blocks stages 5+ before execution tests and does not publish a Metal accelerator.

脚本明确设置 `compat.linuxkpi.xe_probe_display=0 xegfx.nvram_trace=1`，保持固件显示路径并保存阶段追踪。stage 4 会实际操作 GT，关闭显示探测不保证硬件不会黑屏或重启；实机结果必须由返回值、GT 状态、GOP 检查和崩溃报告共同确认。

The wrapper disables display probing and enables persistent stage tracing. Stage 4 operates the GT; disabling display takeover does not guarantee freedom from black screens or reboots. Hardware status must be established from stage results, GT state, GOP checks and crash evidence.

### 推进至 PCI/DMA stage 3 / Advance to PCI/DMA stage 3

[完整构建通过 / Successful full build](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43448978188)：阶段边界、显示快照、原有阻断测试和全部 16 项测试通过，编译/链接/KPI/签名/架构检查通过。新版已备份并部署至硬盘 EFI 开机/签名诊断副本和脚本，读回一致，ocvalidate 通过，开机配置不变。二进制 SHA-256：`8d48440b3d47e3f3787e5c790a709d2a2bd5fc279e25e072dcf2506248522768`。stage 3 实机效果尚待验证。

Stage-boundary, snapshot, containment and all 16 existing tests pass, along with compilation/link/KPI/signature/architecture checks. Boot and signed diagnostic copies plus the wrapper are backed up and deployed to the internal EFI with matching readback and clean ocvalidate. Boot configuration is unchanged. The binary SHA-256 is shown above; stage-3 hardware behavior remains unverified.

重启后运行现有 `gpu-probe.command`：预期完成阶段为 3，`XeGfxPost.result=1`、`metadata-unchanged=1`、`pixel-verified=0`；若阶段 2 或 3 失败，不应手动请求更高阶段。脚本必须检测到新加载策略才会运行。日志采集完成后卸载 SYSTEM 再重启。

After reboot, run the existing wrapper. Expected evidence is completed stage 3 and a successful post-bus GOP check, with metadata unchanged and pixels explicitly unverified. If stage 2 or 3 fails, do not request higher stages. The wrapper requires the new resident policy. Unmount SYSTEM after collection before rebooting.

新增 `xe-ptl-stage3-metadata.patch`，使用明确的 `ptl-stage3-metadata-v3` 加载策略。B0A0 的非像素检查明确返回 1 后保存独立的 GOP 元数据基线、GGTT/物理保留范围；像素 baseline 始终为 false，不建立 CPU 显存映射。stage 2 此时可通过“元数据探测”条件，但不表示像素已验证。失败或非明确成功的返回值均停止推进。

The new policy accepts a B0A0 metadata baseline only after an explicit successful comparison. It records separate GOP metadata and reservation ranges while leaving the pixel baseline false and never mapping framebuffer pixels. Stage 2 can then pass as a metadata probe, not as pixel verification. Negative or ambiguous results stop progression.

stage 3 按上游执行 PCI/DMA shim 初始化及 newbus/IOPCIDevice 总线绑定，再调用 GOP 显示检查：布局、DSM、全量 PTE 必须和原基线一致，当前 100 ms 采样期间帧计数也必须前进。结果写入 `XeGfxPost`，明确区分 `metadata-unchanged` 和 `pixel-verified=0`。任一条件失败则 stage 3 不标为完成。

Stage 3 initializes PCI/DMA shim layers and newbus/IOPCIDevice attachment, then validates GOP state against the original metadata baseline. Layout, DSM and all PTEs must match; the current 100 ms frame sample must also advance. `XeGfxPost` distinguishes consistent metadata from unverified pixels. Any failure prevents stage-3 completion.

在运行 stage 4 的 SYSINIT 之前硬性返回不支持，因此手动请求 stage 4–7 也不能绕过限制。当前不加载 GuC，不初始化 GPU 引擎或接管显示；GuC 固件、GT 初始化及后续未实现功能仍待处理。这是比上一版更进一步的总线初始化实验，不是 Metal 支持。

A hard boundary rejects stage 4 before GPU SYSINIT, including requests for later stages. No GuC, GPU-engine initialization or display takeover occurs. GuC firmware, GT bring-up and missing later implementations remain outstanding. This is a bus-initialization experiment beyond the prior metadata-only probe, not Metal support.

### 实机通过：非像素 GOP 检查 / Hardware pass: pixel-free GOP checks

最新完整采集显示 `XeGfxGOPMetadataResult=1`，两次采样间显示布局和全量 PTE 散列一致；帧计数前进 18。`XeGfxGOPMetadataPTEHash` 与初次页表遍历散列均为 `0x765b28479d6be205`。仍为 4000 个 DM 页、候选起点 `0x7c800000`、长度 `0xfa0000`。`XeGfxGOPCPUAccessBlocked=Yes`、`XeGfxGOPPixelVerified=No`。采集完成，panic 目录仅有先前已分析的报告，无新增文件。

The latest complete hardware collection reports `XeGfxGOPMetadataResult=1`: the display layout and full PTE hash match between samples, and the frame counter advances by 18. The comparison hash matches the initial page-walk hash, `0x765b28479d6be205`. The region remains 4000 DM pages at candidate start `0x7c800000`, length `0xfa0000`. CPU framebuffer access stays blocked and pixel verification remains false. Collection completes; only the previously analyzed panic report is present.

阶段结果仍为 stage 1=1、stage 2=-102，完成阶段保持 1，符合本版阻断设计。系统显示信息仍为基础 GOP（2560×1600、15 MB），不代表 Metal 加速或可继续初始化。此次仅验证非像素检查在初始化前有效；尚未验证它作为初始化前后对比的完整性检查。下一步需接入明确区分“元数据一致”和“像素未验证”的检查策略、验证 GOP 保留与 GuC/GT 前提，当前不重复测试也不撤掉阶段阻断。

Stage 1 returns 1, stage 2 remains -102 and completed stage stays at 1, as intended. Display reporting is still basic GOP (2560×1600, 15 MB), not Metal acceleration or permission to advance initialization. This validates the check before initialization; it does not yet validate preservation across initialization. Further work must integrate a policy distinguishing consistent metadata from unverified pixels, validate GOP reservation and establish GuC/GT prerequisites. No repeat test or removal of the stage guard is requested in this round.

### GOP 非像素检查 / Pixel-free GOP checks

[完整构建通过 / Successful full build](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43446074325)：新增快照测试、既有阻断测试和全部 16 项测试通过，驱动编译、链接、KPI、签名及架构检查通过。已备份并替换硬盘 EFI 的开机/签名诊断副本，散列读回一致，ocvalidate 无问题，配置不变。二进制 SHA-256：`a3412d5d5cda6b2c136bb3891a6ac8f9b4f26665725806c84c60e678ab5f42cb`。尚待本机重启采集确认 `XeGfxGOPMetadataResult` 和帧计数差值。

Snapshot, containment and all 16 existing tests pass, together with driver compilation/link/KPI/signature/architecture checks. Boot and signed diagnostic copies on the internal EFI are backed up and replaced, with matching readback and clean ocvalidate; configuration is unchanged. Binary SHA-256 is shown above. Hardware snapshot result and frame delta remain unverified until the next boot collection.

新增 `xe-ptl-gop-snapshot.patch`：只通过现有 BAR0 映射读取寄存器和完整 GOP 页表，两次采样间隔 100 ms，对比平面控制、stride、尺寸、offset、surface、pipe-enable、DSM、覆盖长度及全部 PTE 的 64 位散列，并要求帧计数前进（接受 32 位回绕）。不映射或解引用像素内存。发布 `XeGfxGOPMetadataResult`，成功为 1；同时始终发布 `XeGfxGOPPixelVerified=No`。失败包括寄存器/页表变化、停帧、缺页、无活动 pipe 或 DSM 以及越界。

The new patch samples registers and the full GOP page table through the existing BAR0 mapping twice, 100 ms apart. It compares plane control, stride, size, offset, surface, pipe enable, DSM, footprint and a full 64-bit PTE hash, requiring frame-counter progress with unsigned wrap handling. It never maps or dereferences pixel memory. `XeGfxGOPMetadataResult=1` denotes a successful metadata check; `XeGfxGOPPixelVerified` remains false. Register/PTE changes, stalled frames, missing pages, inactive pipe/DSM and bounds failures are rejected.

此结果不是像素完整性或显示加速的证明；只检查两次采样之间的显示元数据。当前不将它接入后续阶段的通过条件：B0A0 stage 2 仍返回 -102，防止在其他初始化前提未满足时推进。完整构建同时纳入上轮已验证的 MMIO GOP 显存保留修订。

This checks display metadata between samples, not pixel integrity or acceleration. It does not yet replace later-stage pass conditions: B0A0 stage 2 still returns -102 to prevent progression before remaining initialization prerequisites are established. The complete build also incorporates the previously tested MMIO GOP reservation correction.

### 后续分配器修订与实际缺口 / Reservation fix and remaining implementation gaps

新增 `patches/xe-0200-gop-mmio-reservation.patch`，替换原 0200 补丁在 graphics >= 1270 的 PCI DSM 读取，使用 `xe_mmio_read64_2x32(xe_root_tile_mmio(xe), DSMBASE) & BDSM_MASK`。本机 PCI DSM=0；原逻辑可能不排除正在扫描输出的显存。保留算法仍对候选物理范围执行保守前缀排除，同时推进 GPU stolen_base 和 CPU io_base。此修订仅提交源码和验证，不替换当前 EFI 驱动，也未进入 stage 4。

The replacement 0200 patch changes DSM discovery for graphics >= 1270 from PCI reads to MMIO DSMBASE. With this machine's zero PCI DSM, the prior logic could miss exclusion of the active scanout allocation. The existing conservative prefix reservation still advances both GPU and CPU allocator bases. This round publishes source and tests only; it does not replace the current EFI binary or enter stage 4.

[隔离验证 / Isolated validation](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43444890227)通过：修订补丁实际应用于 Linux 源文件后，编译执行分配器真实代码片段；原有全部 16 项测试通过。更新测试中的 MMIO 模型，并增加本机 GOP 起点/长度用例：在假设 32 MiB stolen 池下排除 0xfa0000 字节前缀，剩余 0x1060000 字节。32 MiB 是测试容量，不是本机实测 stolen 总容量。此验证不等于新版完整 kext 已编译或实机分配器已运行。

Isolated verification applies the corrected patch to the Linux source and compiles/executes its actual reservation block. All 16 tests pass. The MMIO mock and a captured B0A0 GOP-range case verify a 0xfa0000-byte exclusion and 0x1060000-byte remainder in a hypothetical 32 MiB pool. That pool size is a test input, not a measured hardware capacity. This is not a complete new kext build or a hardware allocator test.

目前仍需实现并验证：不读取像素的 GOP 布局/PTE/帧计数基线及对比、显存保留规则与实际容量、GuC 固件及 GT 初始化。现有 `xg_store_check()` 在 xe 路径返回“不支持”，`xg_accel_claim()` 明确不发布 Metal 加速设备；这两项属于缺失实现，不能通过修改阶段返回值或 EFI 参数解决。当前 stage 2 阻断保持，不要求重复重启。

Outstanding work includes a non-pixel GOP layout/PTE/frame-counter baseline and comparison, reservation/capacity validation, GuC firmware and GT initialization. The xe path in `xg_store_check()` returns unsupported, and `xg_accel_claim()` explicitly does not publish an accelerated device. These are missing implementations, not EFI settings or stage-return-value fixes. The stage-2 guard remains; no repeat reboot is requested.

### 实机验证：元数据阻断生效 / Hardware validation: metadata guard works

22:31 探测、22:34 完整采集结束。实际加载策略为 `ptl-metadata-only-v1`，`XeGfxGOPCPUAccessBlocked=Yes`。阶段结果为 stage 1 = 1、stage 2 = -102 (`EOPNOTSUPP`)，完成阶段保持 1；IORegistry 的 XeGfxStage=2 仅代表尝试过。完整采集成功，panic 目录仅包含此前 22:01 的文件。

The 22:31 probe completed collection at 22:34 with the loaded metadata-only policy and CPU-access guard confirmed. Stage 1 returns 1; stage 2 returns -102 (`EOPNOTSUPP`), leaving the completed stage at 1. The registry stage 2 property records an attempt. The panic directory contains only the earlier 22:01 report.

元数据：4000 页、全部为 DM 页；候选物理起点 `0x7c800000`，跨度 `0xfa0000`（16,384,000 字节）；PCI DSM 为 0，MMIO DSM 为 `0x7c800000`，首个 PTE 为 `0x800003`。候选范围包含上次 MCE 报错地址。由此支持 CPU 显存访问为首要故障路径，但并未证明候选地址可供 CPU 使用，也未解决访问限制/缓存属性；不应通过改为 BAR2 读取或写 pcode 寄存器盲试。

Metadata contains 4000 pages, all DM, with candidate start `0x7c800000` and span `0xfa0000` (16,384,000 bytes). PCI DSM is zero; MMIO DSM is `0x7c800000`; the first PTE is `0x800003`. This candidate region includes the previous machine-check addresses, strengthening the CPU-access fault-path hypothesis. It does not prove CPU accessibility or resolve access/cache rules. Blind BAR2 reads or pcode writes are not justified by these results.

当前不需要重复同一测试。后续应研究保留固件 GOP 页表及 stolen 分配范围、无需 CPU 像素读取的完整性校验，再单独处理 stage 4 DSM 保留补丁；现有阻断不应移除以绕过阶段失败。

No repeat of this test is needed. Further work should establish firmware GOP/GGTT and stolen-allocation preservation, integrity checks without CPU pixel reads, and a separate review of stage-4 DSM reservation. Removing this guard simply to bypass the failed stage is not a valid fix.

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
