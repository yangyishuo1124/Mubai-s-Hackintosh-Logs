# Xe / IOSurface shared-memory work

The target is direct sharing of IOSurface pages between Mesa ANV, XeGfx and the
GPU. The desktop texture-cache experiment is not part of this implementation.

## Baseline and implementation

- The installed Vulkan driver does not advertise `VK_EXT_external_memory_host`.
  The standalone IOSurface probe exits 77 before submitting GPU work.
- The pinned XeGfx source explicitly rejects `xe_hmm_userptr_populate_range`.
- `patches/xg_xe_userptr.inc` replaces that rejection with opt-in wired pages,
  a DMA scatter/gather mapping, VMA-lifetime holds and fence-ordered teardown.
- Runtime gate: append `compat.linuxkpi.xe_userptr=1` to the existing
  `debug.xegfx_env` value while testing. The default remains disabled.
- First population requires the calling process to own the VMA's mm. A worker
  may reuse an existing pinned mapping but cannot pin another process's pointer.
- `patches/apply_mesa_userptr.py` exposes the ANV capability on Darwin only when
  `ANV_XE_USERPTR=1` is present in the test process. This gate alone does not
  implement or validate host-memory import.
- The current plugin already has host-pointer and explicit-layout IOSurface
  alias paths; the initial implementation does not change it.

## Validation completed

The actual userptr backend passes host tests under AddressSanitizer and UBSan:
disabled gate, wrong owner, alignment, short/failed page pin, SG allocation
failure, DMA mapping failure, repeated bind, DMA unmap/remap, unexpected notifier
sequence, read-only teardown and repeated cleanup. These tests mock the OS and
DMA boundary; they do not prove physical GPU mapping or coherency.

`diagnostics/vk-iosurface-host.c` builds locally. After import support is available,
it will verify a GPU fill through the original IOSurface pointer and 16 CPU/GPU
round trips over the same imported allocation, without a staging buffer.

## Builds and pending work

- Experimental branch: `experimental/xe-iosurface-userptr`.
- Kernel build: https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/44070376590
- Mesa build: https://github.com/yangyishuo1124/Mubai-s-Hackintosh-Logs/actions/runs/44069820333
- No new kernel or Mesa library has been installed yet.
- Hardware import, coherency, repeated allocation/release, direct image aliasing
  and WindowServer performance remain unverified.

## Mesa build result

Mesa build 44069820333 succeeded. The ZIP digest matches GitHub's
`6e90d2e777bc63c6d40a281dff4a14e6195ca407577fea250ef304285ecea72b`.
The new library was loaded only by a standalone probe. With `ANV_XE_USERPTR=0`,
host import is absent; with `ANV_XE_USERPTR=1`, it is advertised. No host pages
were imported during this enumeration-only check. System libraries are unchanged.

## Kernel build result

Kernel build 44070376590 succeeded. ZIP digest:
`cba5ddc7c604f123e59aacb6e17205220c82fc40ce4393deca6ea2cbbc54fea2`.
The kernel UUID is `81DDE75D-CD72-326D-8A7F-8D6F5A697A12`. Link, KPI,
shadow-symbol and signature checks passed, as did the 16 existing stage tests.
The PTL GuC digest matches the pinned firmware.

After EFI installation and a normal reboot, run
`python3 scripts/verify-userptr-kernel.py` before the privileged
`scripts/run-shared-memory-probe.command`. The probe enables the runtime gate
only for its test interval and restores the previous tunables on exit. The new
Mesa is loaded by that test process only; desktop libraries remain unchanged.

EFI installation completed. The old kernel is preserved as
`EFI/OC/Kexts/XeGfx-pre-userptr.kext` and in a workspace backup. The active
kernel is still the old UUID until reboot. No system Mesa library was replaced.

## First hardware success after reboot

The new UUID was verified loaded after the 19:11 reboot; Stage 7 initialization
succeeded. With the runtime gate enabled for an isolated test process:

- `VK_EXT_external_memory_host` is present.
- GPU fill of the original 4 MiB IOSurface: 0 / 1,048,576 wrong words.
- CPU writes -> GPU reads/copies -> original IOSurface: all 16 patterns pass.
- No staging buffer is used by this test. The old runtime tunables were
  restored after it. WindowServer is still using the original system Mesa.

This verifies buffer-level shared pages. Direct image aliasing and desktop
performance are the next checks; they are not implied by the buffer test.


## 19:26 桌面接入失败与恢复

WindowServer 重启后连续 SIGABRT，最终 watchdog 超时。启动日志确认新 Mesa 的 @rpath/libdrm.2.dylib 无法解析：产物没有 LC_RPATH；Vulkan 初始化失败，CoreDisplay 随后断言退出。独立测试通过 DYLD_LIBRARY_PATH 掩盖了打包问题，不能作为桌面接入成功的证据。

19:23 重启后启动脚本恢复了旧 Mesa、旧插件和旧配置。已核对两项二进制 SHA256 与安装前备份一致；debug.xegfx_env 不含 xe_userptr 开关。未再次启用实验桌面。

本地产物已添加 @loader_path 并重新签名；在 env -i 空环境中 ctypes 加载 Mesa、解析 Vulkan 入口通过。安装脚本改为使用修正产物，并新增空环境加载检查，Metal 预检也去掉 DYLD_LIBRARY_PATH。修正产物尚未重新接入桌面，仍需独立 Metal 验证和带自动恢复的桌面验证。共享内存硬件小测试成功仍有效，桌面稳定性尚未验证。


修正 RPATH 后完成无 DYLD_LIBRARY_PATH 的硬件复测：2560×1600 Metal IOSurface 双向访问零错误，20 次独立导入/提交/释放均通过（每次 16 种数据模式）。退出后确认 xe_userptr 开关恢复关闭。桌面仍使用基线组件。自动回退部署尚待完善，未再次重启 WindowServer。


## 21:10 Intel completion bridge hardware trial

Loaded accelerator UUID 582FA4EC-C798-3643-BD08-781E26D2B30C. First WindowServer selected Metal without automatic restart after early initialization, but its display-pipe presents stayed at zero until a controlled WindowServer restart. Early initialization alone does not yet fully solve first-login presentation.

Intel completion marks now travel over XGDR selector 1 with WindowServer identity checks. Initial plugin incorrectly looked up NVAccel rather than NMXAccel for NVAccelSurfaceWait, choosing publication-before-release and producing repeated 100 ms waits. Corrected capability lookup. With the corrected plugin, identical 10-second animation trials observed 25.51 present events/s with kernel waiting off and 29.67 with it on, zero additional timeout during the measured animation. These are presentation event rates, not measured display FPS, and background load is uncontrolled. A subsequent 30-second retention check observed one additional timeout, so the check disabled kernel waiting and did not persist the experimental plugin. Current shared-memory desktop remains active with completion waits on the userspace side. Further diagnosis must distinguish actual GPU latency from remaining lock/contention waits.

KDK download and installer wait were cancelled. kextd had automatically refreshed AuxKC with the new accelerator after the /Library/Extensions update, so a KDK was unnecessary for this system's update path.
