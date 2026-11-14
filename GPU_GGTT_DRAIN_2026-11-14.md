# V19 GGTT 批次排空实验 / GGTT batch-drain experiment

V18 已记录 GGTT 清理开始、地址推进至 0x51000000，未观察到清理返回。V19 不再仅增加检查点，改为验证连续 posted MMIO 写入的批次排空是否影响挂死。

V18 records GGTT clear entry and advancing offsets through 0x51000000 without an observed return. V19 changes write batching rather than only adding checkpoints, testing whether posted-MMIO write draining affects the hang.

仅 PCI device 0xb0a0 的 xe_ggtt_clear 启用：每 64 次原有 PTE 写入后，用现有 VF_CAP_REG MMIO 读取排空写入；末尾不足 64 项也执行一次。保留所有 PTE、写入顺序、scratch 数据、锁范围和原有最终 TLB 失效。不强制开启其他步进的硬件 workaround，不改 GOP 像素访问。其他 device 的原路径不增加读取。

Only PCI device 0xb0a0 enables this experiment in xe_ggtt_clear. Every 64 existing PTE writes are followed by the existing VF_CAP_REG MMIO read barrier, with a final read for a partial batch. All PTEs, their order, scratch contents, lock scope and final TLB invalidation remain. No other stepping's workaround is forced and no GOP pixel access is added. Other device IDs receive no extra reads.

## 源码核对与依据 / Source review and rationale

- 原始 xe_gt.c 的 gt_fw_domain_init 已在调用 xe_ggtt_init 前持有 XE_FW_GT。重复添加同一 forcewake 引用不是当前已证实的修复。
- 0x51000000 是 GGTT 虚拟地址，对应 GSM 页表偏移约 0x288000，加上 8 MiB 起点仍在预期 8–16 MiB GGTT MMIO 区间内。尚未发现此地址本身越界；完整映射是否可靠仍需实际验证。
- 原始规则将 Wa_22019338487 限于特定 IP/步进；PTL media B0 不在其 A0–B0 排他上界内。未将它直接改为始终开启。

The source already holds primary-GT forcewake before GGTT init. The last observed virtual address maps to a GSM offset around 0x288000, within the expected GGTT MMIO region after its 8 MiB base; this is not proof of actual mapping reliability. The stepping-specific WA is not forcibly enabled for PTL media B0.

[Linux Xe upstream GGTT implementation](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/xe/xe_ggtt.c) already uses the VF_CAP_REG read before final invalidation. V19 reuses that operation more frequently as a local experiment; it is not an accepted upstream fix or proof that the hardware requires 64-entry batches.

[GGTT hang / FORCEWAKE discussion](https://lore-kernel.gnuweeb.org/intel-xe/20260520194426.1334262-1-sonny@milton.pro/T/) describes related LNL hangs and competing wake/throttling hypotheses. Those observations are not directly transferable to this PTL initialization path.

## 检验 / Validation

新增宿主测试直接编译修改后的 xe_ggtt_clear，检查 1、63、64、65、128、129 和大范围页数，验证逐页地址、PTE 值、批次数及其他设备对照。该测试验证实现行为，不能模拟 PCIe 排序或证明硬件挂死消失。

A host test compiles the modified xe_ggtt_clear function and checks page order, PTE contents, batch counts and other-device controls for small boundary cases and a large fill. It verifies software behavior, not PCIe ordering or hardware recovery.

保留 V18 日志、PC-start 诊断绕过、display=0、NVRAM trace=0 与单次 stage 4 请求。阶段返回不等于 Metal 或完整 GPU 加速。

V18 diagnostics, the PC-start diagnostic bypass, display=0, NVRAM trace=0 and one stage-4 request remain. A return does not establish Metal or full graphics acceleration.

## 部署结果 / Deployment

[CI 43569946951](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43569946951) 全部通过，源码 `a8ac275`，产物 `14104162532`。原有 16 项测试、GGTT 初始化/批次排空测试、GuC/PC/DPCPU 回归及架构签名固件检查通过。

All build checks pass, including 16 existing tests, GGTT init/batch tests, GuC/PC/DPCPU regressions and architecture/signature/firmware checks. Source: `a8ac275`; artifact: `14104162532`.

已备份并替换内部 EFI 开机与诊断驱动，双份回读 SHA256 相同；OpenCore 1.0.8 校验通过，配置未变，临时盘符已移除。

Internal EFI boot/diagnostic drivers and wrapper are backed up and replaced. Both binary hashes match readback; OpenCore 1.0.8 validation passes, configuration is unchanged and the temporary drive letter is removed.

- SHA256: `b5b029055ec681082c9f02fa9cec3de43738c64711c9033e697ba537d9b43bd7`
- Backup: `backups/before-xe-ggtt-drain-20261114-151714`

实机结果待验证。重启 macOS 后运行原 gpu-probe.command；脚本要求开机实际加载 V19，单次请求 stage 4 并显示日志。若再次挂死，报告仍用于比较是否完成 GGTT 清理，而不将最后可见 offset 当作精确故障地址。

Hardware result pending. Reboot macOS and run the existing gpu-probe.command; it requires a boot-loaded V19 driver, requests stage 4 once and streams logs. If it hangs again, compare whether GGTT clear returns; the last visible offset remains only an observation.
