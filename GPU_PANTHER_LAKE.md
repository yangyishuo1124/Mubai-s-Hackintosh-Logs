# Panther Lake B0A0 核显适配 / GPU bring-up

2026-11-13 · ASUS S5650AA · Intel `8086:B0A0` · macOS 26.0 `25A354`

## 当前结论 / Current conclusion

2026-11-14 上游 issue / 提交对照：[中文与英文调查记录](GPU_UPSTREAM_RESEARCH_2026-11-14.md)。本轮仅更新调查结论，EFI 未修改。

Upstream issues and commits reviewed: [bilingual research notes](GPU_UPSTREAM_RESEARCH_2026-11-14.md). Documentation only; EFI unchanged this round.

### 撤回重复阶段拆测 / Withdraw redundant stage splitting

用户指出已有 stage 1–3 成功及 stage 4 内部进展证据，分段重测前面阶段不能直接推进当前故障。刚提交的分段脚本尚未部署到硬盘 EFI，现从仓库撤回，恢复 v13 原探测脚本。后续调查聚焦 stage 4 内部，尤其已观测到的 GuC post-load/PC 启动相邻路径；早期文件采样不用于推翻之前实测。GPU 卡死仍未解决，本轮无需重启。

Prior stage-1–3 success and internal stage-4 progress remain valid. The proposed split-stage wrapper did not directly advance the current fault and had not been deployed to disk; it is withdrawn from the repository, restoring the v13 wrapper. Further investigation focuses within stage 4, especially the observed GuC post-load/PC-start neighborhood. Early file samples do not invalidate prior hardware evidence. The GPU hang remains unresolved; no reboot is needed this round.

### v13 仍卡死：保存本次进入 stage 4 前的状态 / V13 still stalls: preserve pre-stage4 state

新日志 20261114-115434 确认 v13 文件/策略通过，EFI hash 匹配；请求未返回，progress 只有启动采样 0。错误传播修正尚未带来可见返回或固件错误，不能声称修复整机卡死。之前 stage 1–3 已通过、部分尝试进入过 stage 4 的证据仍有效。

The new 20261114-115434 probe passes v13 file/policy checks and EFI hash matches. The request does not return; progress only samples startup 0. Error propagation has not yet yielded a visible return or firmware error; the hard freeze is unresolved. Prior stage-1–3 success and stage-4 progress remain valid evidence.

此前此处的分阶段脚本方案已撤回且未部署，以上方撤回说明为准。

The split-stage wrapper proposal formerly described here was withdrawn without deployment; see the withdrawal above.

### 修正 GuC/功耗控制错误传播 / Correct GuC and PC error propagation

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43495307922)。16 项原测试与新增真实上传函数错误路径测试通过，固件、架构及签名检查通过。已备份并部署 EFI 开机/诊断驱动和脚本，读回一致、ocvalidate 通过，开机配置不变。SHA-256：`64ed733117aa795e37fcb7098272764d633389be9286ce9de442a4fc67b634db`。下一次只运行一次探测；若正常返回，检查实际阶段错误和固件日志，不仅看命令退出码；若卡死仍等待约 90 秒再恢复。真实硬件错误是否被截获、整机卡死是否改善均待验证。

Full build, all 16 original tests, the new actual-upload-function failure-path test, firmware/architecture/signature validation pass. EFI boot/diagnostic bundles and wrapper are backed up and deployed, with matching readback, clean ocvalidate and unchanged boot configuration. One hardware attempt is needed; on return inspect signed stage results and firmware logs, not just shell exit status. Capturing real hardware errors and any hard-freeze improvement remain unverified.

审查固定源码发现：__xe_guc_upload 在 RSA/DMA 失败出口仍返回 0；guc_wait_ucode 为 void，失败后调用者仍可标记 RUNNING；PC 两次状态等待超时后 ret 仍可能为 0。0205 补丁令上传失败返回原错误，认证等待返回状态/超时错误且禁止误标 RUNNING，PC 等待结果存入 ret。它修正真实的假成功路径，但尚未证明就是整机冻结原因。错误退出可能改变后续清理路径，需实机确认。

Pinned-source review found __xe_guc_upload returns 0 on RSA/DMA failure, void guc_wait_ucode allows its caller to mark RUNNING after failure, and PC timeout can retain ret=0. Patch 0205 propagates original upload errors, authentication errors/timeouts and PC wait results, preventing false RUNNING. This corrects actual false-success paths, not an established cause of the hard freeze. Earlier failure can exercise different cleanup paths; hardware validation is needed.

新增测试编译修改后的真实上传函数，用桩模拟成功、RSA 失败、DMA 失败和认证等待超时，核对返回值、失败标记及后续调用短路；另检查 PC 等待结果存储。它不是固件实际运行或硬件通信验证。v13 保留请求入口监视、无 NVRAM 和 stage 5+ 阻断。完整构建通过并已部署，实机效果待确认。

The new test compiles the actual modified upload function with stubbed success/RSA/DMA/authentication outcomes, checking returns, status and short-circuiting. PC wait-result storage is checked separately. This is not real firmware/hardware validation. V13 retains request-entry monitoring, no NVRAM and the stage-5+ boundary. Full build and deployment passed; hardware behavior pending.

### 移除 panic 停留参数后仍无重启 / No reboot after removing panic-stop argument

用户再次报告没有自动重启。新报告 20261114-113054 确认 trace=0、env 无 NVRAM、watchdog=60；配置文件已无 debug=0x100（日志本身未输出实际运行 boot-args）。请求未返回，进度文件仅一条 progress=20，对应 stage 2 入口附近；它是较早采样，不是已确认的最终停止点。不能因此继续断言这次卡在 GuC，也不能以没有 reboot 就证明监视线程从未运行。下一步应分开请求各阶段、在每次前后落盘标记，避免连续阶段覆盖进度造成误判。本轮没有再改 EFI。

The user again reports no automatic reboot. New probe 20261114-113054 records trace=0, no NVRAM flag and watchdog=60. Config lacks debug=0x100, although this log does not report effective runtime boot-args. The request did not return; its sole progress=20 sample is near stage-2 entry, not a proven final stall. Neither a GuC failure nor watchdog nonexecution is established. Next localization should request each stage separately with durable before/after markers, rather than infer a final stop from an early sample. No further EFI change this round.

### 修正 panic 自动重启配置 / Correct panic reboot configuration

v12 最新 20261114-111730 报告未完成，progress 只有启动采样 22，EFI 驱动 hash 匹配 v12。发现启动参数一直含 debug=0x100，会阻止 panic 自动重启；此前由“不重启”推断 watchdog 未运行的依据不足，不能排除已经 panic 而画面未更新。

The latest v12 probe is incomplete, with only startup progress=22 and a matching EFI binary. Boot arguments still included debug=0x100, which prevents automatic panic reboot. Prior inference from no reboot to watchdog failure was insufficient; a panic without display update remains possible.

已备份并从实际 EFI/仓库配置移除 debug=0x100，并确保 NVRAM Delete 含 boot-args，使下次启动采用新值。其余启动参数、驱动二进制不变，读回一致、ocvalidate 通过。此改动恢复自动重启的前提，不保证所有死锁能 panic/重启，更不是 GPU 修复。参考：https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/nehalem.html 。

Backed up and removed debug=0x100 from active/repository config, ensuring boot-args is in NVRAM Delete so the new value applies at next boot. Other arguments and binary remain unchanged; matching readback and clean ocvalidate. This removes a panic-reboot blocker, not every possible deadlock or the GPU failure itself.

### 请求入口监视修订 / Request-entry watchdog revision

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43489172557)。已备份并部署 EFI 开机/诊断驱动、资源及脚本；链接后版本与 request-watchdog 字符串存在，读回一致，ocvalidate 通过，config.plist 不变。SHA-256：`c71676c1410153c7ed8b4d9ea55fa2c7cb26bcbd7f8c1ad05f1bf3666b36e493`。下一次重启运行一次探测，若卡住等待约 90 秒观察 panic/自动重启，再回 Windows 读报告。监视范围修正已部署，实机效果及 GPU 卡死修复未确认。

Full build/tests and validation pass. Boot/diagnostic bundles, resources and wrapper are backed up and deployed, with linked policy/request-watchdog markers, matching readback, clean ocvalidate and unchanged config.plist. One hardware attempt after reboot is needed; if stalled, allow about 90s for a panic/reboot before recovering in Windows. Coverage correction is deployed; hardware monitoring behavior and a GPU hang fix are unverified.

v12 将独立线程监视从 xg_run_stage(4) 前移到 stage sysctl 的初始化请求入口，在 stage lock 获取和阶段循环之前启动，并确认线程就绪。创建失败或就绪超时则不进入初始化；已有监视请求返回 EBUSY。线程用请求 active 状态覆盖整个阶段循环（包括阶段间 gRunning=0 的间隙），请求结束解除监视。超时报告正在运行阶段、已完成阶段、progress、IRQ/handler 及 spin 统计。保留无 NVRAM 环境和 stage 5+ 边界，未改 GPU 寄存器或原阶段调用。

V12 arms its dedicated thread at the stage-sysctl request entry, before stage-lock acquisition and the stage loop, with a readiness handshake. Creation/readiness failure prevents initialization; overlapping monitors return EBUSY. Request-active state covers all stages and gaps between them, then disarms on completion. Timeout reports running/completed stage, progress, IRQ/handler and spin statistics. NVRAM remains disabled and stages 5+ stay blocked; original GPU calls/register behavior are unchanged.

生成源码已检查启动先于锁和阶段循环、解除监视在解锁之后。策略为 `ptl-request-watch-v12`。完整构建通过，实机效果待确认；它仍依赖普通内核调度，不是独立 NMI/硬件 watchdog，卡死尚未修复。

Generated-source checks confirm arming before the lock/loop and disarming after unlock. Policy is `ptl-request-watch-v12`. Full build passed; hardware behavior is pending. This still relies on kernel scheduling, not an independent NMI/hardware watchdog; the hang remains unresolved.

### v11 无自动重启：监视启动范围的盲区 / V11 no reboot: watchdog coverage gap

用户报告无自动重启。最新 20261114-105228 报告通过策略及文件校验，EFI 哈希匹配 v11；进度文件仅一行 progress=0，无新完整报告。审查确认 stage sysctl 先顺序执行 1–3，再到 4；v11 专用线程仅在 xg_run_stage(4) 内创建。因此不能确认专用线程已经启动，也不能由此证明全局调度停止。此前以进入 stage 4 为前提的诊断范围不完整，需将监视前移到整次初始化请求前，再区分早期初始化停顿与后续 GPU 卡死。此轮没有修改 EFI 或驱动。

The user reports no automatic reboot. The latest 20261114-105228 probe passes policy/file checks; EFI matches v11, the progress file only has progress=0, and no completed report is new. The sysctl executes stages 1–3 before 4, while v11 creates its dedicated monitor only inside xg_run_stage(4). Monitor startup is therefore unproven; global scheduling failure cannot be inferred. Coverage must begin before the complete initialization request to distinguish earlier initialization from later GPU stalls. No EFI or binary change this round.

### 独立内核线程看门狗 / Dedicated kernel-thread watchdog

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43485047808)。已备份并部署开机/诊断驱动、资源和配套脚本，核对链接后版本及 watchdog 字符串，读回一致，ocvalidate 通过，config.plist 不变。二进制 SHA-256：`8d9986ee6473c32337f7612c84a4ad3d2543f7941c2187311627ec022bf41591`。下一次只运行一次 stage 4，若停住等待约 90 秒观察是否出现 panic/重启；实机监视效果与卡死修复均未确认。

The full build and checks pass. Boot/diagnostic bundles, resources and wrapper are backed up and deployed, with linked policy/watchdog markers, matching readback, clean ocvalidate and unchanged config.plist. One stage-4 attempt after reboot is needed; if stalled, allow about 90s to observe a panic/reboot. Hardware monitor behavior and a hang fix remain unverified.

v11 不修改 GPU 寄存器或初始化调用，保留无 NVRAM 对照。新增独立 kernel_thread_start 监视线程，stage 4 启动前等待就绪（最多约 1 秒）；创建失败/未就绪则停止初始化。监视线程每 100ms 检查，60 秒未结束则 panic 报告内存 progress、中断/handler 计数和自旋统计。它不依赖 thread_call 工作池，也不在 watchdog 中获取日志锁或同步 NVRAM；仍依赖内核调度，不能保证从全局中断/硬件停顿中恢复。监视不是实际 GPU 修复，完整构建通过，实机效果待确认。

V11 preserves original GPU calls/register behavior and the no-NVRAM comparison. A dedicated kernel_thread_start monitor must signal readiness before stage 4 starts (approximately 1s bound); failure stops initialization. It checks every 100ms and panics after 60s with in-memory progress, IRQ/handler counts and spin statistics. It avoids the thread_call worker pool, log lock and NVRAM sync in its watchdog path. It still needs kernel scheduling and cannot guarantee recovery from global interrupt/hardware stalls. This is diagnostic infrastructure, not a GPU fix; build passed; hardware results pending.

### 无 NVRAM 对照实机结果 / No-NVRAM hardware comparison result

用户确认卡住后等待超过 90 秒仍无自动重启，最后手动重启。60 秒 watchdog 未产生可见恢复；源码表明 watchdog 和 irqoff checker 均依赖 thread_call，并非独立 NMI 看门狗。因此调度/中断阻塞是候选，尚非确证。暂不要求重复同一测试。

The user waited over 90 seconds without automatic reboot and manually restarted. The 60s watchdog produced no visible recovery. Both watchdog and irqoff checker use thread_call, not an independent NMI watchdog. Scheduling/interrupt blocking is a candidate, not proven. No repeat of this identical test is requested.

最新日志 `gpu-probe-20261114-094258.txt` 明确显示 trace=0、env 无 NVRAM 标志、watchdog=60。stage 请求未返回，没有新完整诊断包。配套 progress 文件只有一行 `09:42:58 progress=22`，是启动附近采样，不能当作卡死位置；背景采样没有提供后续步骤证据。

The latest probe explicitly records trace=0, no NVRAM environment flag and watchdog=60. The stage request did not return and no new completed diagnostic archive appeared. Its progress file contains only `09:42:58 progress=22`, a startup sample rather than an established failure site. Background sampling provides no later-step evidence.

关闭 NVRAM 仍未完成初始化，因此并发/同步 NVRAM 写入不能解释全部失败；现有数据仍不能区分内核全局阻塞、IRQ/调度或具体 GPU 操作。不得用旧 NVRAM 当作本轮卡点。待确认 watchdog 等待时间及重启方式，再选择独立于正常调度的诊断方式；本轮不盲改寄存器或继续加同步写入。

Disabling NVRAM did not complete initialization, so NVRAM concurrency/synchronous writes do not explain the entire failure. These records do not distinguish global kernel blocking, IRQ/scheduling issues or a particular GPU operation. Old NVRAM must not be attributed to this attempt. Watchdog wait duration and reboot method need confirmation before choosing diagnostics independent of normal scheduling; no speculative register change or extra synchronous persistence is introduced.

### 无 NVRAM 写入对照 / No-NVRAM comparison

[脚本校验通过 / Wrapper verification passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43474465119)。此任务包含 zsh 语法检查及旧基线产物的既有测试，不是重新构建或验证新的驱动二进制；本轮二进制未变。

This run checks wrapper syntax and existing tests against the older baseline artifact; it is not a rebuild or new-binary verification. No binary was changed this round.

v10 最新只读记录为 `s4 p46001 checkpoint 46001 PC forcewake returned`，EFI 二进制哈希与 v10 一致。这证明到了该检查点，尚不证明同步保存调用已经返回，也不能确认下一步共享内存清零是原因。

The latest v10 trace is `s4 p46001 checkpoint 46001 PC forcewake returned`, with matching EFI binary hash. This establishes reaching the checkpoint, not returning from synchronous persistence; it does not establish shared-memory clearing as the cause.

本轮不改驱动二进制或开机配置。脚本先关闭 `debug.xegfx_trace`，env 不再设置 `xegfx.nvram_trace=1`。内存 progress 更新保留，后台独立进程每秒读一次 progress 写入同次报告的 `-progress.txt` 并 sync；60 秒 watchdog 保留。监控最多 90 次采样，脚本退出时停止。若内核/存储整体卡住，后台采样或 sync 也可能停止；日志缺失不等于某步骤没执行。目标是排除初始化线程中的同步 NVRAM 保存干扰，不是已修复 GPU。

Driver binary and boot configuration remain unchanged. The wrapper disables `debug.xegfx_trace` and omits the NVRAM-trace environment flag. In-memory progress remains; an independent process samples once a second into the matching `-progress.txt`, flushing the filesystem. The 60s watchdog remains; monitoring is bounded to 90 samples and stopped on wrapper exit. A kernel/storage-wide stall can stop sampling/flushing too, so missing samples do not prove a step was not reached. This comparison removes synchronous NVRAM persistence from initialization; it is not an established GPU fix.

脚本语法/现有验证通过，已备份并部署 EFI 脚本、读回一致；驱动二进制与开机配置逐字节保持不变。实机对照待运行。下次结果优先读取进度文件/完整报告/panic；旧 NVRAM 标签可能原样保留，不能当作本次结果。

Wrapper syntax/existing verification passed; the EFI wrapper is backed up, deployed and read back identically. Driver binary and boot configuration remain byte-for-byte unchanged. Hardware comparison pending. Read the new progress file, completed report or panic first. Old NVRAM can remain unchanged and must not be treated as a new trace.

### 追踪并发修正 / Trace concurrency correction

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43471982931)。已备份并部署 EFI 开机/诊断驱动及脚本，读回一致、ocvalidate 通过，config.plist 不变。SHA-256：`3be08e66332814a9cf77ad7eeffab280f240aa26852588807454533a4b621853`。本地生成源码检查了原子门、两个释放出口及 timer 抑制；实际硬件并发行为和卡死改善待验证。

Full build/tests and validation passed. Boot/diagnostic bundles and wrapper are backed up and deployed with matching readback, clean ocvalidate and unchanged config.plist. Local generated-source checks cover the atomic gate, both release exits and timer suppression. Hardware concurrency behavior and any hang improvement remain unverified.

v9 实机最后记录变为 `s4 p44009 checkpoint 44009 xe_guc_post_load_init returned`，未留下 PC 入口或内部标记。EFI 哈希与 v9 一致，最新记录 20261114-091555。位置后退意味着目前不能把 PC 启动当作已确认的唯一故障点。

The v9 attempt leaves `s4 p44009 checkpoint 44009 xe_guc_post_load_init returned`, without PC entry/internal markers. EFI matches v9; latest probe is 20261114-091555. The earlier checkpoint means PC startup is not an established unique failure location.

源码审查发现定时器与初始化线程均可调用 `xg_trace_write`，且快照后的 NVRAM 写入/同步没有串行化，可能交错或用旧快照覆盖新快照。v10 用非阻塞原子门保证同一时间只有一个 writer，并停止 stage 4 定时器持久化（同步检查点继续）；正文 progress 从同一加锁快照读取。并发 writer 忙时跳过写入，避免在初始化线程等待追踪锁。修正的是追踪设计缺陷，尚不能证明它就是整机卡死原因。NVRAM 同步本身仍可能卡住，最后标签仍不是精确故障指令。

Review found timer and initializer both invoke `xg_trace_write`, with unprotected NVRAM commits after snapshot capture. Interleaving can overwrite a newer snapshot with an older one. V10 adds a nonblocking atomic single-writer gate, suppresses stage-4 timer persistence (synchronous checkpoints remain), and formats progress from the same locked snapshot. A busy writer causes a skipped write rather than blocking initialization. This fixes a trace-design defect; it does not establish the cause of the system hang. NVRAM sync can still stall, so the last label is not an exact faulting instruction.

策略 `ptl-stage4-trace-v10`，保留 PC 内部检查点和原 GPU 初始化，stage 5+ 阻断。完整构建通过并已部署，实机效果待确认。

Policy is `ptl-stage4-trace-v10`; PC checkpoints, original GPU initialization and the stage-5+ boundary remain. Full build and deployment passed; hardware effects pending.

### 新实机定位：GuC 功耗控制 / New hardware localization: GuC power control

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43469610820)。已备份并部署 EFI 开机/诊断驱动、资源和脚本，读回一致、ocvalidate 通过，config.plist 不变。SHA-256：`baa1f09b3b9ccb95ed333f76ef1139a6dc448123a78dd3683ddf0b1c67ae408e`。下一次重启后只需一次 stage 4 复现，卡死后回 Windows 读取检查点，不反复运行。

Full build/tests and validation passed. Boot/diagnostic drivers, resources and wrapper are backed up and deployed to the internal EFI with matching readback and clean ocvalidate; config.plist is unchanged. One stage-4 attempt after reboot is needed; recover NVRAM in Windows after a hang rather than repeating it. Hardware success remains unverified.

最新只读 NVRAM：`s4 p44010 checkpoint 44010 xe_guc_pc_start begin`，EFI 驱动 SHA 与 v8 一致，探测记录为 20261114-090414。这次已越过 uC 内 HuC/GuC 上传、通信、默认 LRC 和 post-load 初始化调用，但函数返回不等于所有硬件状态已证实。候选范围为 GuC PC 启动或入口检查点同步保存，不直接判定固件不兼容。

Read-only NVRAM gives `s4 p44010 checkpoint 44010 xe_guc_pc_start begin`; EFI matches v8 and the new probe is 20261114-090414. HuC/GuC upload, communication, default-LRC and post-load calls returned this run; returns alone do not prove every hardware state. Candidates are GuC PC startup or synchronous persistence at its entry, not established firmware incompatibility.

0204 补丁保留原流程，46000–46013 成对标记 forcewake、共享内存清零/头部、PC reset、频率初始化/上限及固件控制；46020/46021 标记普通/延长状态等待入口；47000/47001 标记 reset CT 发送前/后。策略 `ptl-stage4-pc-v9`，stage 5+ 仍阻断。完整构建通过，已部署；卡死尚未修复。

Patch 0204 preserves control flow and brackets forcewake, shared-memory clearing/header, PC reset, frequency setup/cap and firmware control (46000–46013). Codes 46020/46021 enter normal/extended state waits; 47000/47001 bracket reset CT send. Policy is `ptl-stage4-pc-v9`; stages 5+ stay blocked. Full build and deployment passed; hang unresolved.

### 新实机定位：uC 硬件初始化 / New hardware localization: uC hardware initialization

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43467363285)。已备份并替换硬盘 EFI 的开机和诊断驱动及脚本，读回一致、ocvalidate 通过，开机配置不变。新版 SHA-256：`4d4827f7774f5718149951767eb7e504773c68168c50e6a0a8d9800d16829f33`。待重启后实机定位，不代表卡死已修复。

Full build/tests and validation passed. Boot and diagnostic drivers plus wrapper are backed up and deployed to the internal EFI, with matching readback and clean ocvalidate. Boot configuration is unchanged. Hardware localization after reboot remains pending; the hang is not fixed.

Windows 只读恢复最新 NVRAM：`s4 p43012 checkpoint 43012 uC hardware init begin`；新 EFI 记录仍停在 stage 请求。已越过此前的 stolen、GT forcewake、GGTT、引擎和迁移初始化；当前范围缩至 `xe_uc_init_hw` 或该入口检查点的同步保存。尚不能判断卡在 HuC 上传、GuC 上传、通信、默认 LRC、功耗初始化还是持久化本身，亦不能由此证明 GuC 正常运行。

Read-only Windows recovery gives `s4 p43012 checkpoint 43012 uC hardware init begin`. The new EFI log again ends at the stage request. This run passed stolen initialization, GT forcewake, GGTT, engines and migration setup. The current candidate is `xe_uc_init_hw` or synchronous persistence at its entry checkpoint. HuC/GuC upload, communication, default LRC setup, power control and persistence remain to be distinguished; running GuC is not established.

新增 0203 补丁：44000–44015 逐项标记 uC 硬件初始化，45000–45011 标记 GuC 提频、参数、传输准备、RSA、固件 DMA 上传和认证等待。每对偶数开始、奇数返回，不改变原调用或错误处理。策略为 `ptl-stage4-uc-v8`；stage 5+ 继续阻断。完整构建通过并已部署，卡死尚未修复。

Patch 0203 brackets uC hardware initialization (44000–44015) and GuC frequency/parameters/transfer preparation/RSA/firmware DMA/authentication wait (45000–45011). Even codes enter, odd codes return. Calls and error handling remain unchanged. Policy is `ptl-stage4-uc-v8`; stages 5+ remain blocked. Full build and deployment passed; the hang is unresolved.

### 分配器末尾检查点已到达；继续定位 GT / Allocator tail reached; tracing GT

[新版完整构建通过 / New full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43464244177)：16 项原测试、分配器路径测试、GOP 元数据/阶段边界检查及固件/签名/架构检查通过。已备份并部署开机与诊断驱动、资源和脚本，读回一致，ocvalidate 无问题，config.plist 保持不变。链接后二进制包含新策略及 GT/GGTT 标签。SHA-256：`10e0151c184b88f7fb1bcb078f7445ed6c0f2dde20ae8d78325adec342a355f4`。下一次重启后可运行一次 stage 4 定位；若卡死，回 Windows 读取 NVRAM，不反复执行。部署完成不代表硬件初始化成功。

The new full build passes all 16 existing host tests, allocator control-flow tests, GOP metadata/stage-policy checks and firmware/signature/architecture validation. Boot/diagnostic bundles, resources and wrapper are backed up and deployed to the internal EFI with matching readback and clean ocvalidate; config.plist is unchanged. The linked binary contains the new policy and GT/GGTT labels. After reboot, run one stage-4 attempt and recover NVRAM in Windows if it hangs. Deployment is verified; hardware initialization is not yet verified.

本次卡死后，Windows 只读恢复 NVRAM：`s4 p30005 checkpoint 30005 stolen init returned`。该检查点在 stolen manager 初始化末尾，位于 VRAM manager、清理注册和可选 WC 映射之后。本次证据不支持此前怀疑的分配器内部卡住；不过标签在同步 NVRAM 写入完成前形成，所以尚不能证明该检查点调用已经返回。最新 EFI 探测仍停在 stage 请求，没有新的完整诊断包。

Read-only NVRAM recovery after this hang gives `s4 p30005 checkpoint 30005 stolen init returned`. This is the tail of stolen-manager initialization, after the VRAM manager, cleanup registration and optional WC mapping. An allocator-internal stall is not supported by this attempt. The label is formed before synchronous persistence finishes, so the checkpoint call itself is not proven to have returned. The latest EFI probe stops at the stage request, with no new completed diagnostic archive.

新增 `xe-0202-gt-checkpoints.patch`：40000–40013 跟踪 device probe 中 stolen 返回、display-noaccel、GT、HECI、OA 和 DRM 注册；41000–41017 跟踪 GT 主初始化；42000–42013 跟踪 GT forcewake、GGTT、IRQ、MCR 和 early-engine/sysfs；43000–43013 跟踪全域 forcewake、寄存器恢复、时钟、引擎、uC、迁移和硬件初始化。每对偶数为进入、奇数为返回；多 GT 会复用编号。保留原调用和错误路径，不跳过任何初始化。检查点写入也可能影响时序，不能把最后标签直接当作故障指令。

The new patch brackets device-probe calls (40000–40013), GT initialization (41000–41017), GT-domain forcewake/GGTT/IRQ/MCR/early-engine setup (42000–42013), and all-domain forcewake/register/clock/engine/uC/migration initialization (43000–43013). Even codes enter a call; the following odd code records its return. Multiple GTs reuse codes. All original calls/error paths remain. Persistence can change timing or itself stall; the final label is not an exact faulting instruction.

策略更新为 `ptl-stage4-gt-v7`。CPU 像素访问禁止及 stage 5+ 阻断仍保留，尚未修复卡死、尚无 Metal。补丁已在固定 Linux 源码上实际应用，并核对移除新增检查点后原代码 token 一致；完整构建通过，实机效果待确认。

Policy is `ptl-stage4-gt-v7`. CPU pixel access and stages 5+ remain blocked; the hang and Metal support remain unresolved. Local patch application against the pinned Linux source passes, and stripping the added checkpoints leaves original code tokens unchanged. [Full build 43464244177 passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43464244177); hardware results are pending.

### 显存分配器内部定位版 / Allocator localization revision

[完整构建通过 / Full build passed](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43461250290)：原有全部检查及新分配器路径测试通过，固件嵌入/签名/架构验证通过。已备份并替换硬盘 EFI 开机/诊断驱动和脚本，链接后检查点标签与版本标记存在，读回一致，ocvalidate 通过，开机配置不变。二进制 SHA-256：`14b7d142bd0cba6b9df4461aa71a38aff9212c893f29952f0cbc3a8ff9608bb3`。下一次只做一次 stage 4 复现；若卡死，回 Windows 读 NVRAM，不反复重跑。此版实机定位效果尚未验证。

Full build, existing checks and the new allocator control-flow test pass, including embedded firmware/signature/architecture validation. Boot/diagnostic bundles and wrapper are backed up and replaced on the internal EFI, with linked checkpoint/policy markers, matching readback and clean ocvalidate. Configuration is unchanged. One stage-4 reproduction is needed; after a hang, recover NVRAM in Windows rather than repeating the probe. Hardware localization remains unverified.

新增 `xe-0201-allocator-checkpoints.patch`，保留全部原始初始化/错误返回。30001/30002 为 stolen manager 创建前/后，30003/30004 为 stolen WC 映射前/后，30005 为 stolen 初始化返回。31001 为 VRAM manager 入口；31002/31003 为 mutex 初始化前/后；31004/31005 为 TTM resource manager 初始化前/后；31006/31007 为 buddy 初始化前/后；31008/31009 为 driver manager 注册前/后；31010/31011 为 managed cleanup 注册前/后。

The new patch retains initializer semantics and error returns. Codes 30001–30005 bracket stolen-manager initialization and WC mapping. Codes 31001–31011 identify VRAM-manager entry and before/after checkpoints for mutex, TTM resource-manager, buddy, driver-manager installation and managed cleanup.

新策略 `ptl-stage4-alloc-v6` 防止误跑旧版。同步 SYSINIT 和线程初始化追踪继续保留，不禁止 stolen 分配或改变缓存属性来盲试；stage 5+ 仍阻断。新增测试会编译实际修改后的 manager 函数，在模拟成功、buddy 失败和 cleanup 失败时检查执行顺序及原返回值；它不是硬件锁或映射正确性的证明。此版尚是定位实验，卡死没有修复。

The wrapper requires the allocator-checkpoint policy. Existing SYSINIT/current-thread tracing remains; no speculative disabling of stolen memory or cache-attribute change is introduced. Stages 5+ remain blocked. A new compiled test executes the actual modified function with stubbed dependencies, checking order and return values for success, buddy failure and cleanup failure. This does not establish hardware lock/mapping correctness. The hang remains unresolved.

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
