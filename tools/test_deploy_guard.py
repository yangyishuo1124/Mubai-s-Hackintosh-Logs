"""deploy_efi.py 的 Metal 修复载荷保护 —— 对照测试。

用例 A：目标 EFI 带 .rpath-fixed 标记 -> metal/vulkan 必须保留磁盘上的已修复版本
用例 B：目标 EFI 无标记             -> metal/vulkan 应写入源 EFI 的未修复版本
两例都必须满足：OC/Diagnostics/Boot/Tools 读回校验通过、失败自动回滚可用。
"""
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
DEPLOY = Path(sys.argv[2])
REPO_EFI = Path(sys.argv[3])

SRC = ROOT / "src"
DST = ROOT / "dst"
BAK = ROOT / "bak"


def build(with_marker: bool, dst_tag: str, src_tag: str):
    for p in (SRC, DST, BAK):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)

    # 源 EFI
    (SRC / "OC").mkdir()
    shutil.copy2(REPO_EFI / "OC" / "config.plist", SRC / "OC" / "config.plist")
    (SRC / "OC" / "opencore.efi").write_bytes(b"SRC-OC")
    (SRC / "Diagnostics" / "GPU" / "metal").mkdir(parents=True)
    (SRC / "Diagnostics" / "GPU" / "vulkan").mkdir(parents=True)
    (SRC / "Diagnostics" / "GPU" / "metal" / "x.dylib").write_text(src_tag)
    (SRC / "Diagnostics" / "GPU" / "vulkan" / "y.dylib").write_text(src_tag)
    (SRC / "Diagnostics" / "gpu-display-capture.command").write_text("script\n")
    (SRC / "Boot").mkdir()
    (SRC / "Boot" / "boot.efi").write_bytes(b"SRC-BOOT")
    (SRC / "Tools").mkdir()
    (SRC / "Tools" / "t.command").write_text("tool\n")

    # 目标 EFI
    (DST / "OC").mkdir()
    shutil.copy2(REPO_EFI / "OC" / "config.plist", DST / "OC" / "config.plist")
    (DST / "OC" / "opencore.efi").write_bytes(b"OLD-OC")
    (DST / "Diagnostics" / "GPU" / "metal").mkdir(parents=True)
    (DST / "Diagnostics" / "GPU" / "vulkan").mkdir(parents=True)
    (DST / "Diagnostics" / "GPU" / "metal" / "x.dylib").write_text(dst_tag)
    (DST / "Diagnostics" / "GPU" / "vulkan" / "y.dylib").write_text(dst_tag)
    (DST / "Diagnostics" / "gpu-display-capture.command").write_text("old script\n")
    (DST / "Boot").mkdir()
    (DST / "Boot" / "boot.efi").write_bytes(b"OLD-BOOT")
    (DST / "Tools").mkdir()
    (DST / "Tools" / "t.command").write_text("old tool\n")
    if with_marker:
        (DST / "Diagnostics" / "GPU" / ".rpath-fixed").write_text("fixed-at: test\n")


def run():
    r = subprocess.run([sys.executable, str(DEPLOY), str(SRC), str(DST), str(BAK)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


fail = 0

# ---------------- 用例 A：带标记 ----------------
build(with_marker=True, dst_tag="FIXED", src_tag="SRC")
r = run()
got_metal = (DST / "Diagnostics" / "GPU" / "metal" / "x.dylib").read_text()
got_vulk = (DST / "Diagnostics" / "GPU" / "vulkan" / "y.dylib").read_text()
got_oc = (DST / "OC" / "opencore.efi").read_bytes()
got_script = (DST / "Diagnostics" / "gpu-display-capture.command").read_text()
print("=== 用例 A：目标带 .rpath-fixed 标记 ===")
print(r.stdout.strip()[-900:])
print(f"  metal/x.dylib   = {got_metal!r}   (期望 'FIXED')")
print(f"  vulkan/y.dylib  = {got_vulk!r}   (期望 'FIXED')")
print(f"  OC/opencore.efi = {got_oc!r}  (期望 b'SRC-OC')")
print(f"  采集脚本已更新  = {got_script.strip()!r}")
if got_metal != "FIXED" or got_vulk != "FIXED":
    print("  BAD: 已修复载荷被覆盖"); fail = 1
elif got_oc != b"SRC-OC" or got_script.strip() != "script":
    print("  BAD: 其他目录未正确更新"); fail = 1
else:
    print("  OK: 已修复载荷保留，其余目录正常更新")

# ---------------- 用例 B：无标记 ----------------
build(with_marker=False, dst_tag="FIXED", src_tag="SRC")
r = run()
got_metal = (DST / "Diagnostics" / "GPU" / "metal" / "x.dylib").read_text()
got_vulk = (DST / "Diagnostics" / "GPU" / "vulkan" / "y.dylib").read_text()
print()
print("=== 用例 B：目标无标记 ===")
print(r.stdout.strip()[-700:])
print(f"  metal/x.dylib   = {got_metal!r}   (期望 'SRC')")
print(f"  vulkan/y.dylib  = {got_vulk!r}   (期望 'SRC')")
if got_metal != "SRC" or got_vulk != "SRC":
    print("  BAD: 无标记时应写入源版本"); fail = 1
else:
    print("  OK: 无标记时正常写入源版本")

print()
print("=== 结果：" + ("全部通过" if fail == 0 else "存在失败") + " ===")
sys.exit(fail)
