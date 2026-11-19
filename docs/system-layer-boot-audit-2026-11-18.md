# 系统层启动改动审计

证据来自 GitHub 仓库文档和已读回的 EFI 脚本；尚未读取当前 macOS APFS 中的文件，不能将脚本动作等同于本次全部执行成功。

1. `docs/xe-iosurface-shared-memory.md` 明确记录：11 月 17 日更新了 `/Library/Extensions/XeGfxAccel.kext`，kextd 自动更新 AuxKC。记录的实验驱动 UUID 为 `582FA4EC-C798-3643-BD08-781E26D2B30C`。EFI 回退不能回退 AuxKC 或该路径的驱动。
2. 同文档记录替换 Mesa 后，WindowServer 曾因 `@rpath/libdrm.2.dylib` 无法解析反复 SIGABRT，最终 watchdog。后续曾回退，又进行了共享内存桌面实验，当前系统文件版本必须实读核实。
3. 安装器在系统创建 `/Library/LaunchDaemons/org.mubai.gpu-capture.plist` 与 `/Library/Application Support/MubaiGPUCapture/capture.zsh`。包装脚本挂载 SYSTEM，再执行 EFI 中的 gpu-display-capture.command。
4. 恢复后的历史脚本在第 114–122 行仅在两个系统 kext 之一不存在时才复制旧驱动；若新版都存在，就直接 kextload 现有版本。因此历史 EFI 与新版系统驱动混用是明确存在的机制。
5. 历史脚本第 106–109 行推进 stage 7；130–138 行开启 AGDC 并依次写 nvaccelfb=1/3/4。这不是只读日志采集。第 72 行重写 nvmtl-allow.txt，第 86 行重写 nvrm610.conf；可能覆盖之后的 WindowServer 单独禁用策略。
6. `/Library/GPUBundles/NVMTLDriver.bundle`、`/Library/GPUBundles/nvmtl/` 的 Metal/Vulkan/Mesa 动态库及配置不在所恢复 EFI 的完整系统快照范围内。该 EFI 没有足够文件保证系统组件自动回退。
7. 历史脚本还修改显示覆盖、透明度/动画偏好和防睡眠设置。这些是附带改动，目前没有证据证明它们导致本次苹果进度条停住。

结论：恢复 GitHub EFI 并不等于恢复当时系统运行环境；旧 EFI 可以加载系统盘中的新版加速驱动，开机服务还会执行显示接管设置。本次停在苹果标志，尚不能仅凭此确定是早期 kext 挂死还是 WindowServer 无法显示。优先从恢复环境读取上述 LaunchDaemon、kext Info.plist/UUID、AuxKC、Metal/Mesa 哈希及 panic/WindowServer 报告，再针对性恢复对应组件与缓存；不清空全部 GPU 驱动。

本轮没有再次修改 EFI 或 APFS 系统卷；挂载 EFI 只用于核查，已卸载。
