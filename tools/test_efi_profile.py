"""验证 efi_profile.py --profile full 与当前磁盘配置等价（幂等），且 safe 往返仍可用。"""
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
src_efi = Path(sys.argv[2])          # 磁盘 EFI（Z:\EFI）
work = Path(sys.argv[3]) / "efiprofile-test"

if work.exists():
    shutil.rmtree(work)
(work / "EFI" / "OC").mkdir(parents=True)
shutil.copy2(src_efi / "OC" / "config.plist", work / "EFI" / "OC" / "config.plist")

G = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def pick(path):
    with open(path, "rb") as fh:
        c = plistlib.load(fh)
    m = c["Misc"]
    return {
        "ShowPicker": m["Boot"]["ShowPicker"],
        "HideAuxiliary": m["Boot"]["HideAuxiliary"],
        "Timeout": m["Boot"]["Timeout"],
        "ScanPolicy": m["Security"]["ScanPolicy"],
        "AppleDebug": m["Debug"]["AppleDebug"],
        "Target": m["Debug"]["Target"],
        "boot-args": c["NVRAM"]["Add"][G]["boot-args"],
        "Accel": [k["Enabled"] for k in c["Kernel"]["Add"] if k["BundlePath"] == "XeGfxAccel.kext"][0],
        "AGDC": [k["Enabled"] for k in c["Kernel"]["Add"] if k["BundlePath"] == "XeGfxAGDC.kext"][0],
        "Block": sorted(e["Identifier"] for e in c["Kernel"]["Block"] if e.get("Enabled")),
        "BlockTotal": len(c["Kernel"]["Block"]),
    }


def run(profile):
    return subprocess.run(
        [sys.executable, str(repo / "EFI" / "Tools" / "efi_profile.py"),
         "--efi", str(work / "EFI"), "--profile", profile],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


fail = 0
before = pick(work / "EFI" / "OC" / "config.plist")

print("=== 1) 切到 safe ===")
r = run("safe")
print(r.stdout.strip())
safe = pick(work / "EFI" / "OC" / "config.plist")
if safe["ShowPicker"] is not True or safe["Timeout"] != 5 or safe["ScanPolicy"] != 0:
    print("  BAD: safe profile 引导展示不正确"); fail = 1
if safe["Accel"] or safe["AGDC"]:
    print("  BAD: safe profile 未关闭 Accel/AGDC"); fail = 1
if len(safe["Block"]) != 5:
    print(f"  BAD: safe profile 启用的 Exclude 数 = {len(safe['Block'])}（应为 5）"); fail = 1
if safe["BlockTotal"] != 6:
    print(f"  BAD: safe profile Block 总条目 = {safe['BlockTotal']}（应为 6，含 IOSkywalkFamily）"); fail = 1
elif "com.apple.iokit.IOSkywalkFamily" not in safe["Block"]:
    print("  BAD: safe profile 丢了 IOSkywalkFamily 的 Exclude（AirPort_RTW89 需要）"); fail = 1
else:
    print(f"  OK: safe profile Block 共 {safe['BlockTotal']} 条（5 实验性启用 + IOSkywalkFamily 保留）")

print()
print("=== 2) 切回 full ===")
r = run("full")
print(r.stdout.strip()[-900:])
after = pick(work / "EFI" / "OC" / "config.plist")

print()
print("=== 3) 与磁盘当前配置逐键比对（应为幂等）===")
for k in before:
    same = before[k] == after[k]
    if not same:
        fail = 1
    print(f"  {'==' if same else '!='} {k}: {after[k]!r}")
    if not same:
        print(f"       磁盘原值: {before[k]!r}")

if before == after:
    print("  => 切换 full 往返后与磁盘配置完全一致（幂等）")
else:
    print("  BAD: 往返后配置发生变化")
    fail = 1

print()
print("=== 结果：" + ("全部通过" if fail == 0 else "存在失败") + " ===")
sys.exit(fail)
