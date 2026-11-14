# V21 等待显卡枚举后初始化 / Deferred boot initialization

V20 自动采集确认 stage 2 在 progress=20 返回 -19：xg_probe 尚未找到 GPU。并未进入 GGTT 或 stage 4。V21 将初始化移出同步 IOService::start，服务发布后调度延迟 250 ms 的线程调用，再最多轮询 60 秒等待 Intel GPU 对象。等待期间不运行 stage 1，不占 stage 锁，不持 watchdog 请求。

V20 capture shows stage 2 returning -19 at progress 20 because xg_probe cannot find the GPU, before stage 4/GGTT. V21 moves initialization out of synchronous IOService::start. After service publication it schedules a delayed thread call (250 ms), then polls for the Intel GPU for up to 60 seconds. No stages, stage lock or request watchdog are active while waiting.

找到 GPU 后释放查询引用，再启动原有 watchdog 并持锁执行 stages 1–4。超时打印 GPU discovery timed out 并退出；没有分配到任务也只记录错误。保留 display=0、PC-start bypass、NVRAM trace=0、V19 的批次排空及 V18 检查点，不调用 stages 5+。异步任务一旦创建即拒绝卸载，避免回调运行时 kext 被卸载。

After discovery the query reference is released; the original watchdog and locked stage 1–4 loop run. Discovery timeout or task-allocation failure is logged without stage execution. Display=0, PC-start bypass, NVRAM trace=0, V19 batching and V18 checkpoints remain. Stages 5+ are not invoked. Unloading is refused once the asynchronous task exists, avoiding callback lifetime hazards.

自动采集读取 EFI 中的最新脚本，无需重装 LaunchDaemon。采集窗口延长到 120 秒，覆盖枚举等待。下一次重启进入 macOS 后等约三分钟，再回 Windows 读取 EFI；不需盲操作。

The installed LaunchDaemon uses the current script on EFI and needs no reinstall. Capture is extended to 120 seconds to cover discovery wait. Reboot macOS, wait about three minutes and return to Windows for EFI readout; no blind interaction is needed.

宿主测试验证真实生成 helper 的 GPU 缺失超时、延迟出现、参数拒绝、watchdog/阶段失败和 1–4 顺序，并检查服务入口仅调度、不内联初始化。测试不能证明真实启动时序或图形加速成功。即使本次通过 stage 2，也不等于此前 GGTT/PC 问题已解决。

Host tests exercise the generated helper for missing/delayed GPU, arguments, watchdog/stage failures and ordering, plus structural checks that service start schedules rather than directly runs initialization. These do not prove actual boot timing, acceleration or resolution of earlier GGTT/PC hangs.

## 部署与验证 / Deployment and verification

- Source commit: `ff1c5917`; build [43576813605](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43576813605), artifact `14107071089`, passed.
- XeGfx SHA-256: `580c3ec128a7e35587a9da589352e59ef21f51bf255d2fe7e04cc65cf44473ef`.
- 已写入内部 EFI 的启动与诊断驱动、探测包装和自动采集脚本，逐项回读一致，config.plist 未改动，ocvalidate 通过。/ Internal EFI boot/diagnostic driver and capture/probe scripts copied and read back; config unchanged and ocvalidate passed.
- Backup: `backups/before-xe-deferred-boot-20261114-164507` (local workspace).
- 尚未进行 V21 真机重启验证。/ V21 hardware reboot validation is pending.

## V21 真机照片反馈 / Hardware photo result

本次照片显示已进入 stage 4。`43011 migration init returned`、GuC 固件上传和 `45012 GuC RUNNING status committed`、`44085 xe_guc_enable_communication returned` 均可见；随后进入 `44036 xe_gt_record_default_lrcs begin`。后面多个 GGTT MMIO 屏障及主/媒体 GT TLB 失效有返回。照片最末行为 `42130 GGTT barrier MMIO read begin`，没有可见的对应返回。重复编号代表函数多次调用，并非固定线性阶段。

The photo reaches stage 4: migration initialization returns, GuC upload reaches RUNNING, communication enabling returns, then default LRC recording begins (44036). Several later GGTT barriers and primary/media GT invalidations return. The final visible line is 42130, GGTT barrier MMIO read begin, without a visible matching return. Repeated checkpoint numbers represent repeated function calls, not a linear stage counter.

该检查点在 xe_ggtt_invalidate 的 VF_CAP_REG 读取前；缓存源码定义偏移为 0x1901f8。同一读取先前已返回，不能仅凭照片认定寄存器错误或确定硬件根因。下一步应给默认 LRC 建立中的引擎、队列创建、GGTT 节点插入/移除与作业提交关联编号，核对 MMIO 访问和内存映射生命周期，而非继续对整个 stage 4 二分截断。

This checkpoint precedes the VF_CAP_REG read in xe_ggtt_invalidate (offset 0x1901f8 in the cached source). Earlier reads returned, so the photo alone does not establish an invalid register or hardware root cause. Next instrumentation should correlate engine, queue creation, GGTT node insertion/removal and job submission during default LRC recording, alongside MMIO/mapping lifetime review.

补充边界：虽然没有运行单独的 stage 5 执行测试，stage 4 内部的默认 LRC 记录本身包含 WA/NOP 作业提交；此前“无执行测试”的描述不能解释为 stage 4 完全不提交 GPU 命令。尚无图形加速成功证据。

Scope clarification: no separate stage-5 execution test runs, but default LRC recording inside stage 4 itself submits WA/NOP jobs. Earlier wording about no execution test must not imply that stage 4 submits no GPU commands. Acceleration remains unproven.

本次 Windows 读取 EFI 未发现比 V20 更新的 gpu-display 自动采集目录。照片是本次定位依据；不能从缺失目录判断全系统卡死或仅显示停止。

Windows EFI inspection found no newer gpu-display capture directory than V20. This diagnosis uses the photo; missing captures do not distinguish a system-wide hang from a frozen display.
