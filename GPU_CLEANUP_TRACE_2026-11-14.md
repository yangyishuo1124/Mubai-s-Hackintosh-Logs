# V23 GuC 异步清理追踪 / Asynchronous cleanup tracing

V22 照片最后为 nop_q put returned，缺少随后 q put begin；这不能定位到主队列 put 内部。固定 Linux 版本的普通 GuC 队列 fini 投递 CLEANUP 消息后可返回，真正的销毁可在独立工作线程继续。故本次检查异步路径，而非跳过 GGTT 或清理。

V22 ends at nop_q put returned, before q put begin. This does not locate the stall within the main queue put. Normal GuC queue finalization can enqueue CLEANUP and return, with destruction continuing in a worker. This version investigates that asynchronous path without bypassing GGTT or cleanup.

新增 CLEAN 前缀日志覆盖 GuC fini 入口、cleanup 消息处理及异步销毁：runtime PM get、GuC ID 释放、取消延迟超时工作、调度实体/调度器结束、ge 释放、最终队列/LRC 释放和 PM put。每个操作有 begin/returned；所有原有操作及顺序保留，不改变引用计数、锁、超时、消息和工作队列。日志会影响时序，尚无修复成功或加速成功证据。原有日志函数在 console printf 前已释放 gLogLock，未发现可直接认定的日志锁重入根因。

CLEAN logs cover GuC fini entry, cleanup-message processing and asynchronous teardown: runtime PM acquisition, GuC ID release, delayed timeout-work cancellation, scheduler entity/scheduler finalization, ge release, final queue/LRC release and PM release. Original calls, ordering, references, locks, timeouts, messages and workqueues remain. Logging affects timing; neither a fix nor acceleration is proven. The existing logger releases gLogLock before console printf; a log-lock reentrancy root cause has not been established.

Source reference: [pinned xe_guc_submit.c](https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/xe_guc_submit.c).

## 部署 / Deployment

- Source `d3e2726e`; [build 43581048791](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43581048791), artifact `14107969189`; compile and existing regressions passed.
- SHA-256: `5280c34e3d71d3f254ab8a2f16cacbb0c574ad40e4dd2d818d326a6360988b96`.
- 内部 EFI 启动/诊断驱动与包装已更新并回读；启动配置不变，ocvalidate 通过。/ Internal EFI boot/diagnostic kext and probe wrapper updated and read back; config unchanged, ocvalidate passed.
- Backup: `backups/before-xe-cleanup-trace-20261114-174051` (local workspace).
- 保留 V21 延迟启动、V22 LRC/GGTT 日志及自动采集，无需重装。/ Deferred boot, LRC/GGTT logs and automatic capture remain; no installer rerun required.
- 真机重启结果待验证 / Hardware reboot result pending.
