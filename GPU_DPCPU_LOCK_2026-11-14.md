# DPCPU 锁实验 / DPCPU lock experiment

## 问题与修改 / Problem and change

固定 fork `5ffc79fb9e53eb820899edd644b83681bea3aa39` 的 `shim/src/fbsd/xg_kern.c:xg_dpcpu_block` 在查表和发布新块时使用原始 CAS 自旋锁，但没有像同文件的线程表锁、`xg_sched.c` 的原始锁那样保存并关闭中断。禁止抢占区域中的调用者可能遇到已被抢占的持锁线程，造成无界空转。FreeBSD LinuxKPI 的 `linux_rcu.c` 在 `sched_pin()` 后访问 DPCPU，因此“调用者已经禁止抢占”是实际存在的用法；这里尚未取得本机卡死时的持锁者/等待者堆栈。

The pinned fork uses a raw CAS spinlock for DPCPU lookup/publication without disabling interrupts around ownership. A caller in a non-preemptible section can spin behind a preempted owner. LinuxKPI RCU accesses DPCPU after `sched_pin()`, so pinned callers are not hypothetical API usage. We do not have a holder/waiter stack proving this caused the observed hardware freeze.

V16 在两段原始锁前保存并关闭中断，释放锁后恢复原状态；分配、初始化及并发发布失败后的释放均放在锁外。保留原有分配和复制行为、查表顺序、以及 v15 的 PC start bypass。该实验只改变 DPCPU 锁保护，仍请求一次完整 stage 4，不拆成 stage 1–3 测试，不宣称正常 stage 4 或 Metal 已实现。

V16 saves/disables interrupts before both raw-lock sections and restores the prior state after release. Allocation, initialization and disposal of a losing allocation stay outside the raw lock. The v15 PC-start bypass remains, isolating the DPCPU change. The probe still requests stage 4 once; it is not split into earlier-stage tests or a claim of complete stage-4/Metal support.

## 验证 / Validation

`patches/test_dpcpu_irq.py` 从实际源码提取 DPCPU 函数及锁函数，编译并执行，检查新分配、缓存命中、原本关闭中断的命中、分配期间另一 CPU 抢先发布、不同模板。替身断言在 CAS 获取及释放时中断已关闭，并检查分配与释放不持有原始锁。基线必须在 IRQ 断言失败，修正版必须通过。

The test compiles the actual source functions with deterministic dependency substitutes. It covers allocation, cache hits, an already-disabled caller, competing publication during allocation and distinct templates. It verifies interrupt state at acquisition/release and checks that allocation/free do not hold the raw lock. The baseline must fail and the patched version must pass. These are source-level tests, not a reproduction or resolution of the machine freeze.

## 构建与部署 / Build and deployment

[CI 43508155230](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43508155230) 成功：旧版 DPCPU 触发预期断言，修正版执行通过；原有 16 项测试、GuC 错误传播、PC 等待与 bypass 选择器、x86_64 架构、签名、固定固件及许可证检查通过。构建代码提交 `07f01d9`，产物 `14076783216`。

CI succeeds: the baseline is rejected at the expected IRQ assertion; the patched actual function passes. All 16 existing tests, GuC error propagation, PC wait/selector tests, architecture/signature and firmware/licence checks pass. Build source: `07f01d9`; artifact: `14076783216`.

已备份现用文件并写入内部 SYSTEM EFI 的开机和诊断驱动，包装脚本要求 `ptl-dpcpu-irq-v16`。独立回读两份二进制、完整 SHA256 清单、包装脚本和开机 personality 一致。OpenCore 1.0.8 `ocvalidate` 无问题；EFI 盘符已移除。开机配置未修改。

The boot and diagnostic drivers on the internal SYSTEM EFI have been backed up and replaced. The wrapper requires policy `ptl-dpcpu-irq-v16`. Independent readback verifies both binaries, the complete manifest, wrapper and boot personality. OpenCore 1.0.8 validation passes; the temporary EFI drive letter is removed. Boot configuration is unchanged.

- Binary SHA256: `ed21eb7e021f40590b785650d3409b92c59c7cb7e3b341d8c0a0a4ea0b016aec`
- Local backup: `backups/before-xe-dpcpu-irq-20261114-051746`

尚未重启验证，不能报告卡死已解决。下一次进入 macOS 后运行原 `gpu-probe.command`，仍只请求一次 stage 4，NVRAM 追踪关闭，保留 PC start bypass。若仍卡死，需要继续区分此锁风险与实际故障，不能把源码测试通过当作硬件通过。

Hardware reboot testing is pending. Run the existing `gpu-probe.command` after booting macOS; it still requests stage 4 once, with NVRAM tracing off and the PC-start bypass retained. Source-level tests do not establish hardware success or prove the lock was the freeze cause.

## 实机结果：仍卡死 / Hardware outcome: still freezes

用户反馈 v16 仍卡死。已从内部 EFI 读取并在本地保留 `gpu-probe-20261114-220542.txt` 及对应 progress 文件：资源校验通过，包装脚本通过 v16 策略门禁，环境明确记录 display=0、skip_pc_start=1、trace=0、watchdog=60。stage 请求只留下 `debug.xegfx_stage: 0`，未完整返回；progress 文件仅有 `2026-11-14 22:05:42 progress=0`。EFI 开机二进制回读 SHA256 仍为上述 v16 值。临时 EFI 盘符已移除。

The user reports another freeze. The EFI probe dated 20261114-220542 passes resource checks and the v16 policy gate, with display=0, skip_pc_start=1, trace=0 and watchdog=60. The stage request does not complete; the progress file has only its initial sample. The EFI boot binary still matches the recorded v16 hash. Raw logs remain local and the temporary drive letter has been removed.

DPCPU 修改未消除本机故障，不能报告为已修复。初始进度不是故障定位，不能否定历史 stage 1–3 通过及 stage 4 内部记录；也不能证明 48000 PC 绕过点已执行，或排除全部 PC 相关路径。本轮没有新内部堆栈或寄存器证据，保持现有驱动，不要求重复运行同一实验。

The DPCPU change did not resolve the machine freeze. An initial progress sample is not a fault location and does not invalidate earlier stage-1–3 success or internal stage-4 observations. It does not prove checkpoint 48000 was reached or exclude all PC paths. No new internal stack/register evidence was captured. No replacement driver or repeat of the same experiment is requested this round.

## 前台日志 / Foreground diagnostics

原包装脚本在阻塞的 stage 4 请求返回后才读取驱动日志。现改成先显示现有日志，再后台发起一次 stage 4，前台每 100ms 读取新增日志和变化的 progress，直接输出到终端及原有报告；日志环形缓冲发生轮转时输出当前快照。取消原每秒 `sync` 的后台监视器，保持 NVRAM 追踪关闭。驱动仍为 v16，未新增驱动修复，也不把日志读取视为 GPU 成功。

Previously the wrapper read the driver log only after the blocking stage request returned. It now shows the existing log, submits stage 4 once in the background and reads new log content/progress every 100ms in the foreground. Terminal output continues to the existing report. A rotated log triggers a fresh snapshot. The old background monitor's per-second sync is removed; NVRAM tracing remains off and the driver stays at v16.

这是用户态实时读取，不是内核每条指令同步刷屏。瞬间冻结、日志锁阻塞或显示停止刷新都可能使最后几条未显示；关闭 NVRAM 追踪时的内部 checkpoint 仍主要由 progress 数值表示。照片中的最后一行只能缩小范围，不能单独证明下一条指令就是根因。

This is userspace live reading, not synchronous kernel-to-terminal output for every instruction. A sudden freeze, blocked log lock or stopped display may prevent the final messages from appearing. With NVRAM tracing off, internal checkpoints are primarily represented by progress numbers. The last visible line narrows the search but is not proof of the exact faulting instruction.

## 源码链接 / Source links

## 前台日志实测 / Live-log hardware observation

已读取并本地保存 `gpu-probe-20261114-222415{,-progress,-stage}.txt`。照片最后可见 progress=20，但 EFI 报告继续记录到 **45011**；progress 文件为 0、30、45011。两项 vmap 自测返回 0，日志记录 GOP GGTT 保护、物理 DMA 地址及两个 GuC 70.72.1 固件条目。不能把 `drmn0 state 10 driver -` 的中途枚举快照当作最终绑定结果。

The photograph ends at progress=20, but the persisted EFI report continues to **45011**, with progress samples 0, 30, 45011. Both vmap self-tests return zero; the log records GOP GGTT protection, physical DMA addresses and two GuC 70.72.1 firmware entries. The intermediate `drmn0 state 10 driver -` enumeration is not a final binding result.

45011 对应 `guc_wait_ucode returned`。v13 起该检查点之后检查 `ret`，失败则进入清理路径，因此只证明等待函数返回，不证明认证成功或 firmware RUNNING。采样仍可能错过后续检查点，不能据此精确定位下一条故障指令；没有证据证明 48000 PC 绕过已执行。该记录保留历史 stage 1–3 成功，不把故障倒退定位到 stage 2。原始报告不上传。

Checkpoint 45011 means `guc_wait_ucode returned`. Since v13 the next code checks `ret` and follows cleanup on error. It proves a return, not successful authentication or firmware RUNNING. Sampling may miss later checkpoints; it does not identify the next faulting instruction or prove checkpoint 48000 ran. Earlier stage-1–3 success remains valid. Raw reports stay local.

- [Pinned shim](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/shim/src/fbsd/xg_kern.c), [scheduler raw-lock convention](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/shim/src/fbsd/xg_sched.c).
- [Pinned FreeBSD LinuxKPI RCU](https://github.com/freebsd/freebsd-src/blob/9da2c05a748fd17757638e1a9e78215cdb8b80d0/sys/compat/linuxkpi/common/src/linux_rcu.c).
