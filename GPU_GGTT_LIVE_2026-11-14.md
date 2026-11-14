# V18 GGTT 内部实时诊断 / GGTT internal live diagnostics

V17 的保存日志最后到达 42002（GGTT init begin），两个早期 GuC 实例此前返回 ret=0。最后保存的位置不能直接作为根因，新增日志会改变时序；此前更深的 PC 观察仍然有效。

V17 persisted logs end at 42002 (GGTT init begin), after both early GuC waits return ret=0. The last persisted boundary does not prove the cause. Logging may change timing; earlier deeper PC observations remain valid.

V18 在原有操作前后增加日志，保留 scratch 分配、清零、加锁、完整页表填充、屏障和两个 GT 的 TLB 失效。填充每经过 16 MiB 对齐地址打印位置，不逐页刷屏，不增加 GPU 寄存器读取。

V18 logs the existing scratch allocation, zeroing, locking, full page-table fill, barrier and both GT TLB invalidations. Fill position is logged at 16 MiB aligned addresses; no extra GPU register reads are added.

| 检查点 / Checkpoint | 操作 / Operation |
| --- | --- |
| 42100 / 42101 | scratch 分配与映射 / scratch allocation and mapping |
| 42102 / 42103 | scratch 清零 / scratch zeroing |
| 42110 / 42111 | clear 锁获取 / clear lock acquisition |
| 42112 / 42113 | 单个地址空洞填充 / individual hole fill |
| 42120 / 42121 | scratch PTE 编码 / scratch PTE encoding |
| 42114 / 42115 | 初始 TLB 失效调用 / initial invalidation call |
| 42130 / 42131 | 既有 MMIO 屏障读取 / existing MMIO barrier read |
| 42132 / 42133 / 42134 | primary 与 media GT 失效 / primary and media GT invalidation |
| 42116 | 释放 clear 锁 / clear lock released |
| 42104 / 42105 | 清理动作注册与返回值 / cleanup registration and result |

数字表示事件标识，不要求按数值递增。保留 V16 DPCPU 锁修正、PC-start 诊断绕过、display=0、NVRAM trace=0 和单次 stage 4 请求。即使返回，也不等于完整 stage 4、执行提交或 Metal 可用。

Checkpoint numbers identify events rather than a strictly increasing sequence. The V16 DPCPU lock correction, diagnostic PC-start bypass, display=0, NVRAM trace=0 and single stage-4 request remain. A return does not establish full stage-4, submission or Metal support.

源码回归测试直接提取补丁后的 xe_ggtt_init 并用宿主 C 编译器执行，检查内存标志、分配失败退出、调用顺序和清理注册错误传播。

A host C test compiles the actual patched xe_ggtt_init function and checks memory flags, allocation-failure exit, operation order and cleanup-registration error propagation.

## 构建与部署 / Build and deployment

[CI 43568116094](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43568116094) 成功，源码提交 `7b9ebc4`，产物 `14103224398`。原有 16 项测试以及 GGTT、GuC 错误传播、PC 等待/选择器、DPCPU 锁、架构和签名检查均通过。

CI passes the 16 existing tests plus actual-function GGTT flow, GuC error propagation, PC wait/selector, DPCPU lock, architecture and signature checks. Source commit: `7b9ebc4`; artifact: `14103224398`.

内部 EFI 的开机/诊断驱动与脚本已备份并替换。两份二进制独立回读一致，OpenCore 1.0.8 校验通过，临时盘符已移除；开机配置未变。

The internal EFI boot/diagnostic drivers and wrapper are backed up and replaced. Both binaries match independent readback; OpenCore 1.0.8 validation passes and the temporary drive letter is removed. Boot configuration is unchanged.

- SHA256: `846e1e2f2bc53f92518bbdeb9371a8c4f4175253bddc9906238e4a517459caf8`
- Local backup: `backups/before-xe-ggtt-live-20261114-145726`

重启进入 macOS 后运行原 gpu-probe.command；若冻结，记录最后前台输出并手动重启。当前完成的是诊断版本部署，实机结果待验证。

After rebooting macOS, run the existing gpu-probe.command. If it freezes, capture the final foreground output and reboot manually. This is a deployed diagnostic build; hardware results remain unverified.
