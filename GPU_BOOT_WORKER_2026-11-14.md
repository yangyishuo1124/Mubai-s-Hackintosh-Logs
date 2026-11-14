# V24 独立初始化线程 / Dedicated initialization worker

## 问题与边界 / Problem and limits

V23 两张最新照片显示 GuC 异步清理完整返回，后面仍有 launchd/APFS/FIPS 启动输出，用户报告持续停屏。没有 stage 4 返回或 panic 栈，不能确定整机死锁，不能宣布 GPU 加速成功。没有证据表明继续拆分清理日志能定位根因。

V23 photographs show an asynchronous GuC finalizer fully returning, followed by launchd/APFS/FIPS activity, while the user reports a stationary display. Neither stage-4 completion nor a panic backtrace is visible. A global deadlock or acceleration success is not established. More cleanup checkpoints alone are not justified by this evidence.

## 改动 / Change

原本 thread_call 回调直接运行所有初始化和等待。V24 保留 IOService 注册后的 250ms 延迟，但回调只创建独立 kernel_thread 并释放调用方的线程句柄引用；初始化、GPU 发现及 stages 1–4 在新线程执行，返回后线程自行结束。创建失败明确报错且不执行阶段。保留原来的卸载阻止条件。

Previously the thread_call callback ran all initialization and waits. V24 retains the 250ms deferred dispatch after service registration, but the callback only creates a kernel thread and releases the caller's handle reference. GPU discovery and stages 1–4 run on that worker, which terminates after returning. Creation failure logs an error and runs no stages. Existing unload prevention remains.

Apple XNU 的默认 thread_call_allocate 使用 HIGH 组；HIGH 组没有 TCG_PARALLEL 标志。这支持将长初始化与共享回调执行环境分开，但不能据此断言原本一定死锁或此次一定修复。

Apple XNU's default thread_call_allocate selects the HIGH group, which lacks TCG_PARALLEL. This motivates isolating long initialization from shared callback execution, but does not establish that the previous code deadlocked or that this change fixes the hardware symptom.

References: [Apple thread_call.c](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/thread_call.c), functions thread_call_allocate / thread_call_allocate_with_options and thread_call_groups. Reviewed 2026-11-14; these references describe scheduling, not a reproduced hardware fault.

独立监控每 5 秒打印 HEARTBEAT：elapsed_ms、running、completed、progress、irqs、handled、最长自旋与长自旋计数；不获取阶段锁、不读取 GOP 像素。原来超过 60 秒的 watchdog panic 保留，debug=0x100 保留。console 输出仍依赖系统可运行并能刷新画面，因此没有心跳照片不能单独证明内核未运行。

The independent monitor prints HEARTBEAT every five seconds with elapsed time, stage/progress, IRQ counters and spin statistics. It takes no stage lock and reads no GOP pixels. The existing >60s panic and debug=0x100 remain. Console output still depends on system execution and visible display updates; an absent photographed heartbeat alone cannot prove the kernel stopped.

不跳过 LRC、清理、GGTT 或中断，不增加 stage 5，不改变 PC bypass/display=0。硬件效果待真机验证。

No LRC, cleanup, GGTT or IRQ operation is bypassed; stage 5 is not added; PC bypass/display=0 remain. Hardware behavior awaits validation.

## 验证 / Validation

CI 编译并执行真实提取的启动 helper、worker/callback 和 watchdog 测试：创建失败、回调只分发、句柄释放、一次初始化与线程结束、5s 心跳、正常返回与 >60s 超时；继续执行原有构建与回归检查。部署信息待构建完成补充。

CI compiles and executes tests extracted from the actual helper, worker/callback and watchdog: creation failure, dispatch-only callback, handle release, single initialization and termination, 5s heartbeat, normal completion and >60s timeout; existing build/regression checks remain. Deployment details will follow the completed build.

## 部署记录 / Deployment record

- Source: `eea81130`; [build 43584717747](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43584717747), artifact `14109574579`.
- 编译、原有回归、新增实际 worker/callback 与 watchdog 行为测试全部通过。/ Compilation, existing regressions and actual worker/callback/watchdog behavior tests passed.
- Driver SHA-256: `8a94e7c94f1d60961b5395d659fad81329082e3f435fb660a9c873b777005ce9`.
- 启动与诊断 kext 已复制到内部 EFI 并逐字节回读；config.plist 与启动 kext Info.plist 保留，ocvalidate 1.0.8 通过。/ Boot and diagnostic kexts copied to internal EFI and read back; config and boot kext Info.plist preserved; ocvalidate 1.0.8 passed.
- Local backup: `backups/before-xe-worker-heartbeat-20261114-182423`.
- 自动采集与 debug=0x100 保留。未执行真机启动，不能宣布停屏修复。/ Automatic capture and debug=0x100 retained. Hardware boot is not yet tested; no stall-fix claim.
- 独立验证工作流改为下载本次构建 43584717747；之前固定的旧构建不能用作 V24 二进制验证。/ The separate verification workflow now downloads this exact build; its previously fixed older artifact cannot validate the V24 binary.

- [Exact-build verification 43585189019](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43585189019) passed: artifact 43584717747 downloaded; architecture, signature, KPI imports and host regressions passed. / 本次构建的架构、签名、内核接口引用和主机回归检查通过。
