Source / 源码: VoodooI2C/VoodooGPIO commit 44fc744d26b3e4971d6d8f0027d75c25e1388637, with patches/voodoogpio-pantherlake.patch. Build / 构建: .github/workflows/gpio-build.yml. GPL-3.0; upstream license retained. Experimental, hardware test pending / 试验版，待实测。

This patched driver requires EFI/OC/ACPI/SSDT-PTL-GPIO.aml enabled in OpenCore. Its local PTIR/PTGR methods bridge firmware TPDI and G_IN evaluation. Forced polling is disabled for the current interrupt trial; hardware validation is pending.

此补丁驱动需配套启用 SSDT-PTL-GPIO.aml，通过本地 PTIR/PTGR 桥接固件 TPDI 与 G_IN。当前已关闭强制轮询，进行中断试验，等待实机验证。

The current SSDT also supplies GPI1 PTG0/PTG1 for GPPF/GPPE packages. This is machine-specific, with unsupported layouts rejected. / 当前 SSDT 另提供 GPI1 PTG0/PTG1 返回 GPPF/GPPE；仅针对本机，不支持的布局拒绝启动。

Hardware result / 实测结果: GPIO mode on GPI1 pin 46 and touchpad input confirmed. Sleep/wake and long-term stability remain unverified. / 已确认 GPIO 模式和输入可用；休眠与长期稳定性待验证。
