# Metal 已验证，桌面显示修复待实机验证 / Metal verified, desktop fix awaiting boot

## 证据 / Evidence

以用户指定的 `gpu-probe-20261115-024055.txt` 和 `s5650aa-20261115-024103.zip` 为准。Metal 计算 1024 项全对，绘图像素回读通过；Vulkan 离屏测试通过，NMXAccel 已匹配。屏幕仍使用 `.Display_boot` / `IONDRVFramebuffer`，没有加载 XeGfxIntelFB。系统信息显示 Metal 3 与这些结果一致，但不能证明桌面合成使用 Metal。

The designated reports verify Metal compute (0/1024 incorrect), Metal pixel readback, Vulkan offscreen rendering, and an active NMXAccel. The screen still uses IONDRVFramebuffer; XeGfxIntelFB is absent. These reports do not establish accelerated WindowServer composition.

上游 `XeGfxIntelFB/intelfb.cpp` 记录 I-108：CoreDisplay 从 framebuffer 类名识别厂商，IONDRVFramebuffer 不提供 Intel 厂商识别，导致关闭 IOPresentment。这是当前首要修复方向，尚不是已证实的唯一卡顿原因。

Upstream documents I-108: the framebuffer class name affects vendor detection and IOPresentment. This makes framebuffer adoption the leading fault location, not a proven sole cause of lag.

Source: https://github.com/InSnh-Gd/WTLIntelGfx/blob/5ffc79fb9e53eb820899edd644b83681bea3aa39/kexts/XeGfxIntelFB/intelfb.cpp

## 本次修复 / Prepared change

- 使用 EFI 已有的 PTL 匹配版 XeGfxIntelFB，二进制 SHA-256 为 `e70d2d2f8e3605f5e25a405338a95a85876a29dd627c36278eac735338728505`。安装前校验二进制和 Info.plist。
- 按上游 AuxKC 安装方法放入 `/Library/Extensions`，在旁边生成并检查新辅助驱动缓存；确认新 framebuffer 存在且旧缓存的驱动标识没有遗漏后才替换。
- 开启 `-xeintelfbnoedid -xeintelfbnohwc`，跳过该 kext 针对旧显示硬件的 EDID、刷新率采样和硬件光标 MMIO 路径。首轮只验证 framebuffer 类接管。
- 保留现有 XeGfx / Mesa / Metal 插件及 `nvaccelfb=1`；不强杀 WindowServer，不重新尝试之前回退的 level 3 加重启组合。
- 一次性安装请求在执行前移走，失败不循环安装。原 kext、AuxKC 和 NVRAM 参数备份于 `/Library/Application Support/MubaiGPUUI/attempt-*`；构建失败保留旧 AuxKC 并恢复原 kext。
- 自动采集 framebuffer 类、显示提交计数、WindowServer 映射的 Metal 库、调用栈及相关日志；报告位于 EFI 的 `Diagnostics/reports/gpu-display-*/ui-*`。

The one-shot boot hook installs the existing PTL-matched framebuffer into the auxiliary collection, verifies hashes and preserves existing auxiliary bundle identifiers before committing. EDID and hardware-cursor extensions are disabled. Existing Metal components and display gates remain unchanged. The installer backs up the old collection/extension/arguments and does not restart WindowServer or reboot. New captures distinguish device discovery from real desktop presentation.

## 生效步骤与边界 / Apply and verify

1. 从 Windows 正常进入 macOS，留出约三分钟让后台安装和采集完成。
2. 如果安装日志显示 `INSTALLED; REBOOT REQUIRED`，正常重启一次 macOS 后，新 framebuffer 才能在启动时接管。若安装失败，查看日志，不反复重启尝试。
3. 以 `XeGfxIntelFramebuffer` 实际匹配、WindowServer 使用驱动、显示提交计数增长及真实 UI 表现作为验收条件。仅安装成功或再次看到 Metal 3 不算修复完成。

Boot macOS to run the staged one-shot installation. A second normal macOS boot is required after the installer reports success. Actual framebuffer attachment, WindowServer driver use, presentation counters and visible UI behavior remain unverified until then. A build failure must be investigated from the log rather than retried in a boot loop.

Windows 无法执行 macOS 的 AuxKC 构建，本次交付状态为“EFI 安装入口与回退已部署”；没有宣称桌面卡顿已修复。

Windows cannot execute the macOS AuxKC build. This change is staged for device verification, not a claim of repaired desktop performance.

## 回退 / Recovery

在可用桌面运行 `sudo /bin/bash /Volumes/SYSTEM/EFI/Diagnostics/gpu-ui-install.command rollback`，然后正常重启。若新 framebuffer 导致无法显示桌面，可从 Windows 在 OpenCore 参数中加入 `-xeintelfboff`（保留 boot-args 的 Delete 项，使参数能实际更新），回到旧 framebuffer，再执行回退。EFI 改动前的备份另保存在 Windows 工作目录 `backups/gpu-ui-*`。

From a working macOS desktop run the rollback command above and reboot. If the framebuffer prevents desktop display, set `-xeintelfboff` from Windows to decline the new framebuffer, then boot and roll back. Keep the boot-args Delete entry so the recovery argument is applied. Original EFI files are also backed up in the Windows workspace.
