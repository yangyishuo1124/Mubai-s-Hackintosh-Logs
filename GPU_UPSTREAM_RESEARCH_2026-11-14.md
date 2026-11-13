# Stage 4 上游调查 / Upstream investigation

2026-11-14 · ASUS S5650AA · Panther Lake 8086:B0A0 · v13

## 结论 / Findings

已有 stage 1–3 成功，以及 stage 4 进入 GuC post-load / PC 启动相邻路径的记录继续有效。本轮查 issue、提交和本地源码，没有修改 EFI、重新编译驱动或要求重启。尚未找到此机器卡死的确定根因。

Prior stage-1–3 success and internal stage-4 GuC post-load / PC-start observations remain valid. This round reviewed issues, commits and local source; it did not change EFI, build a driver or require a reboot. The hard-freeze root cause is still unproven.

## 1. Panther Lake 上游状态 / Upstream Panther Lake status

[WTL issue #8](https://github.com/watchthelight-labs/WTLIntelGfx/issues/8) 跟踪 xe 移植；[issue #11](https://github.com/watchthelight-labs/WTLIntelGfx/issues/11) 是另一台 B082 Panther Lake 的测试讨论，维护者明确说明现有 i915 构建不能提供 Xe3 加速。该线程中 Linux 已加载 GuC 70.72.1；这支持固件选择有参考依据，不证明 B0A0 与移植后的接口已正常工作。

[Issue #8](https://github.com/watchthelight-labs/WTLIntelGfx/issues/8) tracks the xe port. In [#11](https://github.com/watchthelight-labs/WTLIntelGfx/issues/11), the maintainer states that the existing i915 build cannot accelerate Xe3. Another B082 machine loads GuC 70.72.1 under Linux. This supports the firmware choice as a reference, not correct operation of this B0A0 port.

## 2. GuC 回复被丢弃、非连续映射 / Dropped GuC replies and sparse mappings

[SR-IOV Xe3 项目](https://github.com/ericek111/vibe-nullmoth-xe3-qemu) 记录 runtime-PM 失败桩阻止 G2H，以及多段物理内存映射只映射首段的问题。当前固定源码已包含 `0130-runtime-pm-always-active.patch`；`shim/src/xnu/xg_vm.cpp` 已逐段建描述符，再用 `IOMultiMemoryDescriptor` 拼接。两者已有源码层修正，不能再当作本轮新发现的遗漏。仍需核对实际运行时回复处理、共享内存可见性和映射属性。

The [SR-IOV Xe3 project](https://github.com/ericek111/vibe-nullmoth-xe3-qemu) reports G2H being blocked by runtime-PM stubs and incomplete mappings of discontiguous physical buffers. Our pinned source already includes patch 0130 and per-range descriptors joined with IOMultiMemoryDescriptor. These are existing source fixes, not newly discovered omissions. Runtime delivery, shared-memory visibility and mapping attributes remain worth checking. Its VF path disables GuC PC; successful VM acceleration therefore does not validate our bare-metal PC-start path.

## 3. GuC PC 错误返回 / GuC PC error reporting

[Linux 3f2bdcc](https://github.com/torvalds/linux/commit/3f2bdccbccdcb53b0d316474eafff2e3462a51ad) 修复 PC 启动失败后 `ret=0` 的问题，与 v13 对超时结果赋值并返回的修正方向吻合。v13 硬件上依旧卡死，因此这证明错误传播值得修，不能证明根因已解决。

[Linux commit 3f2bdcc](https://github.com/torvalds/linux/commit/3f2bdccbccdcb53b0d316474eafff2e3462a51ad) fixes a zero return after PC-start failure, corroborating v13's error-propagation correction. V13 still freezes on hardware; correctness of that fix is separate from resolving this hang.

## 4. G2H 工作线程与唤醒 / G2H workers and wakeups

[Linux e515272](https://github.com/torvalds/linux/commit/e5152723380404acb8175e0777b1cea57f319a01) 对 G2H 回复超时补充工作线程刷新，关联 xe issues 1620、2902。我们的 6.14 `xe_guc_ct.c` 已有超时后的 `LNL_FLUSH_WORK`；不能把同一改动重复加入，也不能直接把 LNL 限定扩大到 PTL。值得借鉴的是分清“硬件未回复”与“回复未被工作线程处理”，继续检查中断到 G2H 队列、等待/唤醒、锁与 IRQ 状态。

[Linux e515272](https://github.com/torvalds/linux/commit/e5152723380404acb8175e0777b1cea57f319a01), linked to xe issues 1620 and 2902, flushes the G2H worker on response timeout. Our 6.14 CT source already has LNL_FLUSH_WORK. Do not duplicate it or broaden its platform gate without analysis. The useful distinction is missing firmware replies versus replies not processed by the worker. Audit IRQ-to-worker delivery, waits/wakeups and lock/IRQ state within stage 4.

## 5. 启动画面与 GuC 区域 / Boot framebuffer versus GuC space

[WTL #13](https://github.com/watchthelight-labs/WTLIntelGfx/issues/13) 和已于 11 月 12 日合并的 [PR #16](https://github.com/watchthelight-labs/WTLIntelGfx/pull/16) 处理 i915 下 GOP 从 `0xFE800000` 跨过 GuC 边界的问题。我们的已记录 GOP GGTT 范围是 `0xFF000000 + 0xFA0000`，不符合其“从边界下方跨过 `0xFEE00000`”的触发条件，不能直接套用迁移补丁。当前已有 xe GOP GGTT/stolen 保留。后续应核对 xe 自己的 GuC、PC BO 和分配范围，不能从 i915 的边界推断 xe 必然安全。

[WTL #13](https://github.com/watchthelight-labs/WTLIntelGfx/issues/13) and [merged PR #16](https://github.com/watchthelight-labs/WTLIntelGfx/pull/16) address an i915 boot framebuffer crossing 0xFEE00000 from below. Our recorded GOP range starts at 0xFF000000, so that trigger does not match. Existing xe GOP reservations remain relevant; compare xe's actual GuC/PC buffer and allocator ranges before adapting any relocation logic.

## 6. 其他参考的适用范围 / Other references and limits

[VedCloud 的等待实现](https://github.com/VedCloud/Meteor-Lake-Xe-LPG-Metal-Graphics/blob/main/NullMoth/gpu-port/xkpi/bsdcompat/src/nmx_sleep.c) 使用先登记等待、再释放调用者锁的顺序以防丢失唤醒。当前 `xg_lock.c` 的 CV/msleep 路径也采用这个顺序；尚未据此发现可直接提交的缺失修正。需结合 CT/工作队列具体调用检查。

[VedCloud's wait implementation](https://github.com/VedCloud/Meteor-Lake-Xe-LPG-Metal-Graphics/blob/main/NullMoth/gpu-port/xkpi/bsdcompat/src/nmx_sleep.c) registers waits before dropping the caller lock. Our CV/msleep paths already use that ordering. This is a comparison reference, not proof of a newly found bug.

[Linux b0ac4ef](https://github.com/torvalds/linux/commit/b0ac4ef074ace20714a3bf96d23ae2ba61cc4439) replaces PC polling with an elapsed-time based helper because exponential sleep accounting can overshoot. Our source still uses the older loop. This is a candidate for bounded-wait cleanup after checking the port's sleep and time functions; it does not explain a machine-wide freeze on its own, especially before evidence confirms entry to that loop.

## 后续方向 / Next direction

优先审查 stage 4 内 GuC/PC 共享 BO 的地址、CPU 映射与缓存属性，以及 CT 中断到工作线程的唤醒链路。保持“已到达路径”与“硬件功能成功”分开；不重复把测试截断到 stage 4 之前，不因早期采样覆盖已有通过记录。以上线索尚无一项被证明是本机根因。

Prioritize GuC/PC shared-BO addresses, CPU mappings/cache attributes and CT IRQ-to-worker wakeups inside stage 4. Reached code paths are not hardware-success proof. Do not repeat tests cut off before stage 4 or replace prior success with early samples. None of these references establishes this machine's root cause.
