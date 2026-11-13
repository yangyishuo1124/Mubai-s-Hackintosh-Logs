# DPCPU 锁实验 / DPCPU lock experiment

## 问题与修改 / Problem and change

固定 fork `5ffc79fb9e53eb820899edd644b83681bea3aa39` 的 `shim/src/fbsd/xg_kern.c:xg_dpcpu_block` 在查表和发布新块时使用原始 CAS 自旋锁，但没有像同文件的线程表锁、`xg_sched.c` 的原始锁那样保存并关闭中断。禁止抢占区域中的调用者可能遇到已被抢占的持锁线程，造成无界空转。FreeBSD LinuxKPI 的 `linux_rcu.c` 在 `sched_pin()` 后访问 DPCPU，因此“调用者已经禁止抢占”是实际存在的用法；这里尚未取得本机卡死时的持锁者/等待者堆栈。

The pinned fork uses a raw CAS spinlock for DPCPU lookup/publication without disabling interrupts around ownership. A caller in a non-preemptible section can spin behind a preempted owner. LinuxKPI RCU accesses DPCPU after `sched_pin()`, so pinned callers are not hypothetical API usage. We do not have a holder/waiter stack proving this caused the observed hardware freeze.

V16 在两段原始锁前保存并关闭中断，释放锁后恢复原状态；分配、初始化及并发发布失败后的释放均放在锁外。保留原有分配和复制行为、查表顺序、以及 v15 的 PC start bypass。该实验只改变 DPCPU 锁保护，仍请求一次完整 stage 4，不拆成 stage 1–3 测试，不宣称正常 stage 4 或 Metal 已实现。

V16 saves/disables interrupts before both raw-lock sections and restores the prior state after release. Allocation, initialization and disposal of a losing allocation stay outside the raw lock. The v15 PC-start bypass remains, isolating the DPCPU change. The probe still requests stage 4 once; it is not split into earlier-stage tests or a claim of complete stage-4/Metal support.

## 验证 / Validation

`patches/test_dpcpu_irq.py` 从实际源码提取 DPCPU 函数及锁函数，编译并执行，检查新分配、缓存命中、原本关闭中断的命中、分配期间另一 CPU 抢先发布、不同模板。替身断言在 CAS 获取及释放时中断已关闭，并检查分配与释放不持有原始锁。基线必须在 IRQ 断言失败，修正版必须通过。

The test compiles the actual source functions with deterministic dependency substitutes. It covers allocation, cache hits, an already-disabled caller, competing publication during allocation and distinct templates. It verifies interrupt state at acquisition/release and checks that allocation/free do not hold the raw lock. The baseline must fail and the patched version must pass. These are source-level tests, not a reproduction or resolution of the machine freeze.

构建、安装与实机结果将在验证后补充；本文件最初提交不表示 EFI 已替换。

Build, installation and hardware outcomes will be recorded after verification. The initial document commit does not mean the EFI has been replaced.

## 来源 / Sources

- [Pinned shim](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/shim/src/fbsd/xg_kern.c), [scheduler raw-lock convention](https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/shim/src/fbsd/xg_sched.c).
- [Pinned FreeBSD LinuxKPI RCU](https://github.com/freebsd/freebsd-src/blob/9da2c05a748fd17757638e1a9e78215cdb8b80d0/sys/compat/linuxkpi/common/src/linux_rcu.c).
