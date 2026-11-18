# 2026-11-18 启动恢复 / Boot recovery

已同步 origin/main 至 a671879。此前已实测 IOSurface 共享页 GPU 双向访问和独立 Metal 测试；桌面接入曾发生 Mesa RPATH 缺失及 WindowServer SIGABRT，修正后仍有 completion timeout，不能称为稳定桌面加速。

本次照片中的内核回溯包含 XeGfxAccel、IOAcceleratorFamily2 和 IOGraphicsFamily，位于 framebuffer / displayModeDidChange 路径。最新启动日志 opencore-2026-11-18-053431.txt 明确记录：

```
OC: Prelinked blocker (Disable) result 1 for org.watchthelight.XeGfxAccel (...) - Unsupported
```

关闭 Kernel/Add 没有移除已经进入系统辅助驱动缓存的驱动；现有 Disable 拦截没有成功。同时 EFI 开机脚本仍会升至 stage 7、加载 /Library/Extensions 中的加速驱动，并开启 nvaccelfb 1/3/4。仅移除启动参数没有完整关闭这些路径。

恢复操作：备份内置 EFI 的 config 和开机脚本；关闭实验 GPU 注入，将五个自定义 GPU 驱动的缓存拦截改成 Exclude；stage 0，禁用两种 framebuffer 接管；开机脚本只采集日志。保留已安装的 Metal/Mesa 文件，不在 Windows 修改 macOS 系统卷。EFI 文件读回一致、ocvalidate 通过。仍需实际启动验证，尤其检查下一次 OpenCore 日志中的排除结果。

The latest configuration disabled EFI injection but its cached XeGfxAccel blocker returned Unsupported. The boot helper also continued to load acceleration components and enable display gates. Recovery now excludes the experimental GPU identifiers, disables initialization and framebuffer adoption, and makes the helper read-only. Backups and configuration validation passed; successful boot and actual exclusion results remain pending hardware verification.

OpenCore strategy definitions: https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex
