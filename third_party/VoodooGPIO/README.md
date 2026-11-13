Source / 源码: VoodooI2C/VoodooGPIO commit 44fc744d26b3e4971d6d8f0027d75c25e1388637, with patches/voodoogpio-pantherlake.patch. Build / 构建: .github/workflows/gpio-build.yml. GPL-3.0; upstream license retained. Experimental, hardware test pending / 试验版，待实测。

This patched driver requires EFI/OC/ACPI/SSDT-PTL-GPIO.aml enabled in OpenCore. Its local PTIR/PTGR methods bridge firmware TPDI and G_IN evaluation. Forced polling remains enabled until hardware validation.

此补丁驱动需配套启用 SSDT-PTL-GPIO.aml，通过本地 PTIR/PTGR 桥接固件 TPDI 与 G_IN。保留轮询，等待实机验证。
