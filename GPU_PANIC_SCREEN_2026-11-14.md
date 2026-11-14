# V23 panic 画面保留 / Preserve panic screen

照片 1794649644246.jpg 最后可见 CLEAN guc_exec_queue_fini returned；用户报告随后黑屏自动重启。异步清理入口尚未在照片出现，不能确定具体崩溃指令或最终释放是否运行。

Photo 1794649644246.jpg ends at CLEAN guc_exec_queue_fini returned. The user reports a later black screen and automatic reboot. The photo does not show asynchronous cleanup entry and cannot identify the faulting instruction.

源码 instrument_watchdog.py 在初始化请求持续超过 60 秒时主动 panic，消息为 XeGfx request watchdog，带 running_stage/completed_stage/progress/IRQ/自旋统计。自动重启可能源于该 panic，尚未证实。EFI 没有新增自动采集目录；OpenCore 日志只记录启动加载过程，不能替代 XNU panic 日志。

The dedicated request watchdog intentionally panics after 60 seconds of initialization and includes stage/progress/IRQ/spin counters. It may explain the reboot but remains unconfirmed. No new EFI capture directory was found; OpenCore boot logs are not XNU panic reports.

本次仅在现有 boot-args 增加 debug=0x100，以尝试保留 panic 画面；keepsyms=1 原已存在，V23 驱动及其看门狗保持不变。对配置做解析比较确认仅此字段变化，备份原文件并回读。若是固件/硬件复位，该参数不保证阻止重启。

Only debug=0x100 was appended to boot-args to attempt to preserve the panic screen. Existing keepsyms=1, V23 binary and its watchdog remain. Parsed comparison confirms no other config changes; original bytes were backed up and writes read back. This cannot guarantee prevention of firmware/hardware resets.

Reference: [Dortania boot arguments](https://github.com/dortania/OpenCore-Install-Guide/blob/master/config-laptop.plist/icelake.md).

下一次启动等约 90 秒，若出现 panic 文字，拍摄最上面的 panic 原因行和调用栈；如果仍黑屏自动重启，记录这一现象即可，无需盲操作。

On the next boot wait about 90 seconds. If panic text appears, capture the top panic reason and backtrace. If it still resets with a black screen, report that outcome without blind interaction.
