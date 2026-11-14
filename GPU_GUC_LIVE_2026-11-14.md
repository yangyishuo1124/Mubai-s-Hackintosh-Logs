# V17 GuC 返回值与实时检查点 / GuC results and live checkpoints

上次照片末尾为 progress=30，EFI 保存的报告则到达 45011 (`guc_wait_ucode returned`)。该函数返回不等于成功：v13 起会检查返回值，失败进入 LOAD_FAIL 路径。现有日志没有返回值，不能选择后续修复方向。

The photograph ends at progress=30 while the EFI report reaches 45011 (`guc_wait_ucode returned`). A return does not imply success: v13 checks the result and follows LOAD_FAIL on error. The prior observation lacks the result needed to distinguish the paths.

V17 增加以下诊断，不改变初始化返回值、状态选择或控制流程：

V17 adds diagnostics without changing return values, status choices or initialization flow:

- 内部 `xg_init_checkpoint` 先更新进度，再将编号及名称写入驱动日志，即使 NVRAM trace=0 也可由前台脚本读取。Each checkpoint updates progress then logs its number and label, including when NVRAM tracing is off.
- GuC 等待返回后打印 GuC 实例指针及 ret，区分两次初始化；不额外读取 GPU 寄存器。Log the GuC instance and wait return value without extra MMIO reads.
- 正常分支打印 RUNNING，提交状态后标记 45012。The success branch logs RUNNING and marks 45012 after status commit.
- 错误分支打印 ret/LOAD_FAIL，并以 45013/45014 包围状态更新。The error branch logs ret/LOAD_FAIL and brackets status update with 45013/45014.

保留 v16 锁修正及 PC-start bypass，保持 display=0、NVRAM trace=0、单次 stage 4 请求及前台日志读取，不恢复轮询式阶段拆分。日志增加可能改变时序；用户态读取仍可能错过冻结前最后消息。最后可见检查点不自动等同于根因。

V16's lock correction and PC-start bypass remain. Display probing and NVRAM tracing remain off; the wrapper requests stage 4 once and streams logs in the foreground. Logging can change timing and userspace may still miss final messages. The final visible checkpoint is not automatically the fault cause.

## 构建与部署 / Build and deployment

[CI 43566667225](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43566667225) 成功；源码提交 `2f6fe9a`，产物 `14103300736`。原有 16 项测试、GuC 错误传播、PC 等待与 bypass 选择器、DPCPU 锁测试、架构/签名和固定固件检查均通过。下载后验证二进制含 v17 标记、实时检查点格式和 GuC 返回值/两分支日志。

CI succeeds with all 16 existing tests, GuC error propagation, PC wait/selector, DPCPU, architecture/signature and firmware checks. Downloaded binary strings verify the v17 policy, live checkpoint format and GuC return/status messages.

已备份并替换内部 EFI 开机/诊断驱动及包装脚本，两份二进制独立回读一致，OpenCore 1.0.8 校验通过，临时盘符已移除。未修改开机配置。

The internal EFI boot/diagnostic drivers and wrapper are backed up and replaced. Independent binary readback matches, OpenCore 1.0.8 validation passes and the temporary drive letter is removed. Boot configuration is unchanged.

- SHA256: `4724c48402365652ff8e2c59ea751d0982de7f129c91603e42f98809ab2722f3`
- Local backup: `backups/before-xe-guc-live-20261114-143545`

下一次进入 macOS 后运行原 `gpu-probe.command`，查看返回值及紧随其后的检查点。不要求手工拆分阶段。当前仅完成构建和部署，尚无实机成功结论。

After rebooting macOS, run the existing probe and inspect the return value and following checkpoint labels. No manual stage splitting is needed. Build and deployment are complete; hardware success remains unverified.
