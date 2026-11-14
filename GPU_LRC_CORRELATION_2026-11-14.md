# V22 LRC 与 GGTT 关联日志 / Correlated LRC and GGTT tracing

V21 照片显示 GuC RUNNING、通信启用返回、进入默认 LRC 记录，最后可见 GGTT barrier MMIO read begin。此前相同读取成功多次，尚不能认定寄存器本身错误。

V21 reaches GuC RUNNING, communication enabled and default LRC recording. The last visible checkpoint precedes the GGTT MMIO read, which returned several times earlier. This does not establish an invalid register or root cause.

V22 在同一轮启动中打印引擎名称/类别/实例、主与 NOP 队列创建、WA/NOP 作业调用及返回码、上下文快照和队列释放，并为 GGTT 失效各调用点标出编译后源码行号；映射 BO 时记录指针、GGTT 起点、大小和 flags。这些日志用于关联最后一次读取的上下文，不再截断 stage 4。调用点行号对应已打补丁的 xe_ggtt.c，而非上游原始行号。

V22 logs engine name/class/instance, main and NOP queue creation, WA/NOP job calls and results, context snapshots and queue release. Each GGTT invalidation call site logs its compiled source line; BO mapping logs its address, GGTT start, size and flags. Line numbers refer to the patched xe_ggtt.c, not upstream source. These correlate the final read without cutting stage 4 short.

保持原来的 MMIO 读取、TLB 失效、PTE 写入、锁和错误处理，不跳过队列或作业。新增日志会改变时序，不能视为修复。保留 V21 延迟初始化、display=0、PC-start bypass 和自动采集。Stage 4 内部仍有默认 LRC 所需的 WA/NOP 提交，尚无硬件加速成功证据。

Original MMIO reads, TLB invalidations, PTE writes, locks and error handling remain; no queues or jobs are skipped. Logging changes timing and is not a proven fix. V21 deferred initialization, display=0, PC-start bypass and automatic capture remain. Stage 4 internally submits default-LRC WA/NOP jobs; acceleration is unproven.

## 部署 / Deployment

- Source: `10f0ef19`; [build 43578780788](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43578780788), artifact `14106669014`, compile and existing regression checks passed.
- Binary SHA-256: `df09b08a360c13552e081a3b2d3a1a01acf544c43c0aeba182b159695726f47d`.
- Internal EFI boot/diagnostic kext and probe wrapper updated and read back. Configuration unchanged; ocvalidate passed.
- 内部 EFI 已写入并回读一致，启动配置未改动，已通过检查。备份 / Backup: `backups/before-xe-lrc-correlation-20261114-171142` (local workspace).
- 真机验证待进行 / Hardware reboot validation pending.

## V22 照片结果 / Photo result

照片 1794647893857.jpg 显示 vcs0 (class=1, instance=0) 的 q/nop_q 创建返回；对应 GGTT map、MMIO barrier、主/媒体 GT TLB invalidate 均返回。emit_wa_job(gt,q)、emit_nop_job(gt,nop_q)、emit_nop_job(gt,q) 返回 rc=0，snapshot 返回；最后可见 `LRC nop_q put returned`。

Photo 1794647893857.jpg shows vcs0 (class 1, instance 0) queue creation and associated GGTT mapping/barriers/primary and media invalidation returning. WA and both NOP helper calls return zero, the snapshot returns, and the final visible message is `LRC nop_q put returned`.

下一条代码应先打印 `LRC q put begin`，再调用 xe_exec_queue_put(q)。照片缺少此前置日志，因此不能确定是 q 释放函数内部卡死，也不能再将本次最后可见状态称为 VF_CAP_REG 读取卡死。日志增加可能改变了时序。下一调查重点为队列清理触发的并发工作及日志路径，而不是跳过已返回的 MMIO 读取。

The next statement logs `LRC q put begin` before calling xe_exec_queue_put(q). That message is absent, so this photo cannot locate the stall inside the main queue release or establish a VF_CAP_REG read hang. Added logging may have changed timing. Investigation should cover cleanup-triggered concurrent work and logging rather than bypassing MMIO reads that returned.

对照固定版本 Linux xe_exec_queue.c：destroy 会调用 q->ops->fini(q)，最终 fini 包含 LRC 引用释放及队列内存释放。是否在移植层异步触发及对应锁行为仍需检查，尚无根因结论。源码参考 / Pinned source: https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/xe_exec_queue.c

Pinned Linux queue destruction invokes q->ops->fini(q); finalization releases LRC references and queue memory. Port-specific scheduling and lock behavior remain to be audited; no root cause is established. Zero helper return codes do not prove working acceleration. 本次 EFI 未发现新增自动采集目录，驱动未改动。No new EFI capture directory was found; the driver is unchanged this turn.


后续 / Follow-up: [V23 asynchronous cleanup tracing](GPU_CLEANUP_TRACE_2026-11-14.md).
