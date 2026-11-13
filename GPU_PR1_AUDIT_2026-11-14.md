# PR 1 对照 / PR 1 audit

2026-11-14 · B0A0 · v15 still freezes

## 来源 / Sources

- [PR 1](https://github.com/InSnh-Gd/WTLIntelGfx/pull/1): a merged port plan, not a ready hardware-validated driver.
- Current pinned fork: `5ffc79fb9e53eb820899edd644b83681bea3aa39`.
- [Linux GMD masks](https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/regs/xe_gt_regs.h), [GMD parsing](https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/xe_pci.c), [stepping decoding](https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/xe_step.c).

## 已有内容 / Existing implementation

当前源码和构建工作流已经使用该 fork。计划要求的驱动名/设备 ID、仅 GuC 固件、runtime-PM G2H、非连续映射、indirect ring state 规避、硬件规避补丁及 G2H READ_ONCE/WRITE_ONCE 均已有对应代码。补丁存在及编译通过不等于本机运行时条件命中；仍需区分。

The build already uses this fork. The planned naming/PCI IDs, GuC-only firmware, runtime-PM G2H handling, sparse mappings, indirect-ring-state mitigation, hardware workaround patches and fence accesses have corresponding source changes. Presence and compilation do not prove runtime applicability.

| 计划条目 / Plan item | 当前源码 / Current source |
|---|---|
| Probe / firmware / PM | 0100–0130 |
| 14025515070 mitigation | 0140: PTL indirect ring state disabled |
| 16023105232 / 14023061436 / 16028005424 | 0150 / 0151 / 0152 |
| 13012615864 / 13011645652 / 16026007364 | 0153 / 0154 / 0155 |
| 14025883347 / 14022293748 | 0156 / 0157 |
| LRC workarounds / fence | 0158 / regenerated 0159 |
| GOP | Local 0200 reservation replacement; CPU pixel access blocked |

## 具体硬件差异 / Hardware-specific difference

此前实机寄存器记录为 graphics `0x07804000`、media `0x07800004`。按上述固定 Linux 源码：arch 位 31:22，release 位 21:14，revision 位 5:0；解析结果为 graphics **30.01 / revision 0**，media **30.00 / revision 4**。`xe_step_gmdid_get` 按 A0 + revision 解释，因此驱动层的 stepping 分别是 **A0 与 B0**。这并不单独证明 CPU 是工程样品，也不是新的实测运行时 dump。

Previously captured GMD values decode to graphics **30.01, revision 0** and media **30.00, revision 4**. The pinned driver maps these to **graphics A0 / media B0**. This is a decoding of prior measurements, not a new runtime dump or evidence that the CPU is an engineering sample.

PR 参考机器是 B082，不能把其 graphics 30.00/B0 直接套到 B0A0。后续应按 3001/3000 及各自 revision 复核规则命中。另已检查 `xe_rtp.c`：VERSION_RANGE 包含上界，STEP 范围不包含上界；不能把 `(3000,3001)` 误认为不覆盖 3001。现有 0154 已覆盖 3000–3001，不应重复扩展。尚未发现可据此直接部署的缺失修正。

The reference B082 assumptions must not replace B0A0's captured IP/revision values. Audit rule applicability against each GT. In the pinned RTP evaluator, VERSION_RANGE includes its upper bound, while STEP excludes it. Existing 0154 already covers 3000–3001. No missing fix suitable for immediate deployment is established by this comparison.

## v15 实测 / Hardware outcome

已读取 `gpu-probe-20261114-124459.txt`：v15 策略门禁和资源校验通过；环境记录显式开启 PC start bypass，但阶段请求没有完整返回。不能证明已执行到 48000 绕过点，也不能据此排除所有 PC 路径。保留历史 stage 1–3 成功及 stage 4 内部观察。本轮只更新调查记录，不替换 EFI，不要求重复重启。

The new probe passes the v15 policy/resource gates and records the bypass option, but the stage request never completes. It does not prove checkpoint 48000 was reached or exclude every PC-related path. Earlier stage-1–3 success and internal stage-4 observations remain valid. Documentation only this round; no EFI replacement or repeated reboot requested.

## 新版 Linux 规则复核 / Newer Linux rule audit

本轮参考固定的 Linux 提交 [`2800868f63227c8237d70c41e70d441c919620d6`](https://github.com/torvalds/linux/tree/2800868f63227c8237d70c41e70d441c919620d6/drivers/gpu/drm/xe)，与 v6.14 基线及实际构建使用的 fork 补丁比较。范围为 `xe_wa.c`、GT/device OOB 规则和对应 GuC ADS 条目；不是对全部 Linux 改动或 macOS 兼容层的完整审计。

This pass compares a pinned newer Linux revision with the v6.14 baseline and the fork patches used by our build. Scope: the central WA table, GT/device OOB rules and corresponding GuC ADS entries. It is not an exhaustive audit of all Linux changes or the macOS compatibility layer.

| 候选 / Candidate | 核查结果 / Finding | 本轮处理 / Action |
|---|---|---|
| 16026508708 / KLV 0x900b | 新规则覆盖 graphics 3001 和 media 3000，但原作者明确限定其用途为 SR-IOV。The rule matches these IPs, but the author explicitly limits its relevance to SR-IOV. | 未发现本机走 VF 切换路径的证据，不作为裸机卡死修复添加。Not added as a bare-metal freeze fix without evidence of a VF-switch path. |
| 22019794406 | fork 未扩展该规则，但 ADS 通过 `14022293748 OR 22019794406` 启用同一 KLV 0x9009；0157 已让 14022293748 命中 graphics 3001。The rule itself is not extended, but 0157 already enables the same shared KLV through the other operand. | 仅补规则不会增加已启用的 GuC 行为。No additional GuC behavior from extending this rule alone. |
| 14021402888 | v6.14 已有 graphics 3000–3001 条目，写入 `CLEAR_OPTIMIZATION_DISABLE`。Already present in the baseline. | 不重复移植。No duplicate backport. |
| 16021867713 / 16021865536 | media 3000 的视频解码引擎时钟门控规则在基线中已存在。The applicable media-engine clock-gating entries already exist. | 不重复移植。No duplicate backport. |
| 14021871409 / 18034896535 / 16024792527 / 14021490052 | 新旧表中这些条目要求 graphics **3000** 的 A0–B0 范围；本机先前记录为 **3001**。These specific rules require graphics 3000, not the captured 3001. | 不因都叫 Xe3/A0 就扩展到本机。Do not broaden their IP conditions merely because both are Xe3/A0. |
| 14021486841 | 要求 media 3000 且 STEP(A0,B0)，不含 B0；本机先前记录解码为 B0。The upper step bound excludes the captured media B0. | 不强制启用。Not forced on. |

关键来源 / Key sources:

- [Newer WA table](https://github.com/torvalds/linux/blob/2800868f63227c8237d70c41e70d441c919620d6/drivers/gpu/drm/xe/xe_wa.c), [OOB rules](https://github.com/torvalds/linux/blob/2800868f63227c8237d70c41e70d441c919620d6/drivers/gpu/drm/xe/xe_wa_oob.rules), [GuC ADS](https://github.com/torvalds/linux/blob/2800868f63227c8237d70c41e70d441c919620d6/drivers/gpu/drm/xe/xe_guc_ads.c).
- [16026508708 author explanation and patch](https://lore-kernel.gnuweeb.org/intel-xe/hz4aphth73wrlqdamgcdzdudkgmubhxsdg2twkglgcl7s6ge7c@22eolqhdswyf/T/).
- [Baseline WA table](https://github.com/torvalds/linux/blob/38fec10eb60d687e30c8c6b5420d86e8149f7557/drivers/gpu/drm/xe/xe_wa.c); fork `xkpi/xe/patches/0157-wa-14022293748.patch` explicitly documents why the shared KLV is already enabled.

结论：这些候选中没有找到值得替换 EFI 的新增裸机修正。保持 v15，未构建或部署新的驱动，也未新增一次硬件测试。此结论不能排除其他遗漏；下一步应对照 stage 4 中 GuC/PC 初始化的调用与 macOS 内存映射、锁/中断实现，寻找能在源码上复现的差异，而不是把“不适用”规则全部打开。当前仍未证明最新一次卡死的具体指令或根因。

Outcome: none of these candidates establishes an additional bare-metal fix worth replacing the EFI for. V15 remains installed; no new binary or hardware test was produced. This does not exclude other omissions. Further work should compare the stage-4 GuC/PC call paths against the macOS mapping and lock/interrupt implementations and seek a reproducible source-level discrepancy. The exact instruction and root cause of the latest freeze remain unproven.
