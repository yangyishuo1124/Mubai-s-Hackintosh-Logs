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
