# 2026-11-17：NVMTL self-snapshot 修复部署与性能排查

- 构建：GitHub Actions [44059572203](https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/44059572203)，源提交 `4ab0980324a75572cda1a11b14fc777ab4193bd9`，成功。
- 产物 ZIP SHA-256：`927bb5de2ed0a8d618415ac27c9b41d6239bcedcde4d4e20197c660110c92060`，下载后验证一致。
- 已安装并重新签名 `NVMTLDriver.bundle`，更新 EFI/Diagnostics/GPU/metal/NVMTLDriver；保留完整旧 bundle、配置和 EFI 二进制备份。
- 将 `xe-live` 从 256 恢复为 0；18:11 重启 WindowServer 后用户确认“显示正常，仍然卡顿”。说明显示修复已不再依赖该临时覆盖开关；不代表性能问题解决。
- 保留当前配置：`NVMTL_XE_UNIFIED=1`、`NVMTL_FBFETCH_WS=1`、`NVMTL_NO_SAMPVAR=1`。

## 性能现状

- 面板输出模式为 2560×1600 @165Hz。
- 持续 CoreAnimation 动画采样约 10 秒，`debug.nvaccel_iop_ok_h4` 计数增速约 14.5 次/秒。这是驱动呈现事务计数代理，不能等同于精确屏幕 FPS。
- 采样中 `nvaccel_iop_fail=0`，`nvaccel_iop_async_drop=0`。
- 当前 Intel 呈现路径使用 CPU 拷贝；局部源码中 `nvAccelIopFlip` 限定 `NVRMNVDAFramebuffer`，Intel 面板不能通过直接开启 NVIDIA 的 `nvaccel_iop_flip` 开关获得零拷贝。
- `debug.nvaccelfb` 的读取值来自 armed 状态，读回 1 不能单独说明软件合成或判断是否执行过级别 3/4。
- 下一步：WindowServer 调用栈采样，区分提交/等待、纹理同步、CPU 拷贝等耗时；尚未认定单一瓶颈。

## 18:14 后的性能实验

- 用户确认永久修复后显示正常、仍卡顿。
- WindowServer 主线程 1011 个采样中，313 个位于 IOSurface 私有纹理创建路径，298 个深入 ANV GEM 分配的内核调用等待。此为一次采样的热点，尚非完整因果证明。
- 创建基于同一上游提交的可选 `NVMTL_SURFACE_RETAIN` 补丁，只强保留最多 16 个不大于 1024×1024 的只读双/多平面 IOSurface backing，保留 seed 同步与 IOSurface 生命周期引用。
- 本地编译成功。50 次连续改写同一双平面 surface 并逐字节读回，关闭/开启缓存均通过；一次小测试分别为 489.65ms / 382.33ms，不作为桌面 FPS 提升结论。
- 源码、补丁、安装/回退脚本和日志保存在本工作目录。测试版本不更新 EFI。
- GitHub 插件写阶段记录返回 403 Resource not accessible by integration；未同步成功。

## 实验结果与回退

- 缓存测试版桌面采样约 7.13 / 7.32 次呈现事务每秒，未观察到提升。
- 18:22 已恢复备份的永久 self-snapshot 修复版，移除测试开关并重启 WindowServer。驱动与备份 SHA-256 均为 `c36b9092a5edd84978f49c607523d304b4feade17230d1ece982ae7b16171810`（含本地重新签名）；签名校验通过。
- 回退后同一探针约 7.89 次事务每秒。该结果与最早约 14.5 次/秒的差异表明桌面后台工作量等条件未完全受控，不能把两轮差异直接归因于补丁，更不能称为精确 FPS。
- EFI 保留永久显示修复版，未写入缓存实验版本。
- 恢复后日志确认：`IOSurface copies stage through a buffer (host import ABSENT, NVMTL_NO_SURFACE_HOST=unset)`。当前后端缺少该直接导入能力，仍需 staging 拷贝；这不是全部卡顿的唯一原因证明。
- 低帧率仍未修复。后续需要优化 Vulkan/Mesa 与 XeGfx 的共享内存或呈现路径，并以受控负载验证。

## 快速输入卡顿排查（18:36）

- 用户反馈英文、中文均卡，快速打字时明显。
- WindowServer 即时 CPU 占用约 99.7%（约一个逻辑核心），非整机 CPU 百分比。
- 新的 8 秒采样中，主线程共 2062 个样本：一个主要 `waitUntilCompleted` 分支占 597 个（约 29%），一个主要 IOSurface 纹理创建分支占 344 个（约 17%），其中 340 个深入 ANV 显存分配。
- 这些是采样时的调用栈占比，不是精确的帧耗时拆分，也没有直接测量每个按键的延迟。证据支持桌面渲染及同步等待为主要排查方向，尚不能完全排除其他输入延迟。
- 此轮只采样，没有再次修改驱动或重启桌面。
