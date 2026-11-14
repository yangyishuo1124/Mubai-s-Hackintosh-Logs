# V20 开机自动初始化 / Automatic boot initialization

按用户要求，初始化由桌面脚本触发改为开机驱动 IOService::start 自动执行。内部 EFI boot-args 增加 xegfx_bootstage=4；已有 -v 保留。服务启动后先设定 display=0、PC-start bypass=1、NVRAM trace=0，再启动 watchdog 并持有原 stage 锁顺序执行 1–4，打印每阶段 BEGIN/RETURN 和返回值。负值立即停止，不调用 stage 5 或 Metal。

At the user's request, initialization moves from the desktop probe to driver IOService::start. Internal EFI boot arguments enable xegfx_bootstage=4 while retaining -v. The service sets display=0, PC-start bypass=1 and NVRAM trace=0, starts the watchdog and executes stages 1–4 under the existing stage lock, logging BEGIN/RETURN and return values. A negative result stops the loop. Stage 5 and Metal are not invoked.

入口不放在 kext 的 _start 内；该入口仅注册资源，由 IOService 匹配后进入初始化。无开关、值为 0 或不等于 4 时均不自动初始化，保留手动诊断能力。V19 的 64-PTE 排空实验和 V18 检查点保留，本次不关闭内核控制台输出。

The kext _start routine still registers resources; initialization runs after IOService matching. Missing, zero or unsupported boot-argument values leave the driver idle for manual diagnostics. V19's 64-PTE drain experiment and V18 checkpoints remain; kernel console mirroring is retained.

开机预期显示 XeGfx BOOT V20 和各阶段边界。如果最后输出已冻结，拍摄完整最后一屏；这仍是最后可见的调用边界，不保证最后一条已提交日志就是故障指令，也不保证硬件完全锁死前所有日志均显示。

Expected boot output includes XeGfx BOOT V20 and stage boundaries. If it freezes, photograph the last full screen. These remain last-visible call boundaries rather than proof of the exact faulting instruction; pending output may be lost during a hardware lockup.

恢复方式：从 Windows 编辑内部 EFI/OC/config.plist 的 NVRAM/Add/7C436110-AB2A-4BBB-A880-FE41995C9F82/boot-args，仅移除 xegfx_bootstage=4，恢复为驱动驻留而不自动初始化；或恢复本次备份的配置。V20 驱动本身仍支持手动调用。

Recovery: from Windows, remove only xegfx_bootstage=4 from that boot-args property in the internal EFI config, or restore the pre-change config backup. The V20 driver then remains resident and accepts manual requests.

宿主测试直接执行生成后的开机 helper，验证缺失/0/非法参数、watchdog 失败、阶段失败及 1–4 完整调用顺序。它不能验证启动时序、跑码可见性或硬件初始化成功。

A host test executes the generated boot helper and checks absent/zero/unsupported arguments, watchdog failure, stage failure and stage 1–4 ordering. It cannot establish actual boot timing, visible verbose output or successful hardware initialization.

## 构建与部署 / Build and deployment

[CI 43573175507](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/43573175507) 成功；源码提交 0d0154c，产物 14105820193。开机 helper 测试、原有 16 项测试、GGTT/GuC/PC/DPCPU 回归以及架构、签名和固件检查均通过。

CI passes boot-helper tests, 16 existing tests, GGTT/GuC/PC/DPCPU regressions and architecture/signature/firmware checks. Source: 0d0154c; artifact: 14105820193.

内部 EFI 开机/诊断二进制和脚本已备份并替换，开机开关已启用；两份二进制回读一致，OpenCore 1.0.8 校验通过，临时盘符已移除。

Internal EFI boot/diagnostic binaries and wrapper are backed up and replaced; the boot-init argument is enabled. Both binaries match readback, OpenCore 1.0.8 validation passes and the temporary drive letter is removed.

- SHA256: `5121fa1b8fd92935c9cd005b0e9cbe0f524182d3aceff42023e370d4a74673a5`
- Backup: `backups/before-xe-boot-stage4-20261114-155513`

下一步直接重启 macOS，拍摄卡住时的跑码画面；无需桌面命令。当前仅证明构建和安装，尚未验证实机启动入口、输出可见性或 GPU 初始化成功。

Next, reboot macOS directly and photograph the last verbose-boot screen if it freezes. No desktop command is needed. Build and installation are verified; actual boot execution, output visibility and GPU initialization remain unverified.

## V20 实机：音量键仍发声、画面不刷新 / Hardware observation

用户报告开机后画面停留在普通系统跑码，音量键仍产生新的声音。照片可见区域未出现 XeGfx BOOT 或阶段边界。输入/音频链路仍响应，不支持将其描述为整机完全锁死；尚不能确定 Xe 初始化阶段是否完成、其线程是否单独阻塞、或显示交接是否失败。照片末尾的 NVMe/ACM 消息不是已确认的故障点。

The user reports a static verbose screen while volume-key presses still generate new sounds. The visible photo contains no XeGfx BOOT/stage boundary. Input/audio responsiveness argues against a complete system lockup; neither Xe stage completion, a separately blocked initializer nor display handoff failure is established. The last NVMe/ACM line is not a confirmed fault site.

新增 gpu-display-capture.command，仅读取阶段/进度/驱动日志和进程列表，并记录 60 秒用户态心跳，不发起阶段请求、不改启动参数。状态和日志读取分开启动，避免日志锁阻塞时连独立心跳都无法保存。首次读取 60 秒后仍未完成会标记 pending，而不持续叠加读取进程。脚本已复制内部 EFI 并回读一致；未替换 V20 驱动，尚未取得该脚本的实机结果。

The new gpu-display-capture.command reads stage/progress/log and process lists and records a 60-second userspace heartbeat. It does not request initialization or modify boot arguments. Separate background reads avoid making heartbeat capture wait on the log lock. Pending first reads are marked after 60 seconds instead of accumulating more readers. The script is copied to internal EFI with matching readback; the V20 driver is unchanged and capture results remain pending.
