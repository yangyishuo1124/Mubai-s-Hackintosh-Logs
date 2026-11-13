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
