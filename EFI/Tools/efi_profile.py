#!/usr/bin/env python3
"""EFI profile switcher — 在 FULL（全功能）与 SAFE（apps-only）之间切换。

Windows 与 macOS 通用，只依赖 Python 3 标准库（plistlib）。

用法 / Usage:
    # 查看当前 profile
    python efi_profile.py --efi <EFI 路径>

    # 切到全功能（11-17 实机验证过的状态）
    python efi_profile.py --efi <EFI 路径> --profile full

    # 切到安全模式（11-18 回退后的 apps-only 状态）
    python efi_profile.py --efi <EFI 路径> --profile safe

<EFI 路径> 指向包含 OC/ 与 Diagnostics/ 的目录，例如
    Windows:  Z:\\EFI
    macOS  :  /Volumes/ESP/EFI
"""

import argparse
import plistlib
import shutil
import sys
import datetime
from pathlib import Path

GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"

# 11-17 实机验证过的全功能状态（commit 5a2bbd1），
# 引导展示部分套用 08ab2ba 那套调试组合（跑码 + 启动项选择器），
# GPU 相关部分（Accel/AGDC/Exclude）保持 5a2bbd1 的实装状态不变。
FULL = {
    "boot_args": (
        "-v keepsyms=1 msgbuf=1048576 -no_compat_check -rtw89nowpa3 revpatch=cpuname "
        "revcpu=1 -amfipassbeta amfi_get_out_of_my_way=1 ipc_control_port_options=0 "
        "alcid=3 xegfx_bootstage=4 nvaccelfb=1 -nmintelfboff"
    ),
    "accel_enabled": True,
    "agdc_enabled": True,
    "exclude_block": [],                      # 不排除任何实验性驱动
    "boot": {"ShowPicker": True, "HideAuxiliary": False, "Timeout": 5},
    "security": {"ScanPolicy": 0},
    "debug": {"AppleDebug": True, "Target": 67},
}

# 11-18 回退后的 apps-only 状态（commit 5f0de92）
SAFE = {
    "boot_args": (
        "-v keepsyms=1 msgbuf=1048576 -no_compat_check -rtw89nowpa3 revpatch=cpuname "
        "revcpu=1 -amfipassbeta amfi_get_out_of_my_way=1 ipc_control_port_options=0 "
        "alcid=3 -nmintelfboff -xeintelfboff xegfx_bootstage=4"
    ),
    "accel_enabled": False,
    "agdc_enabled": False,
    "exclude_block": [
        ("org.watchthelight.XeGfxAccel", True, "Exclude", "x86_64",
         "Block XeGfxAccel to prevent early boot framebuffer panic"),
        ("org.watchthelight.XeGfx", False, "Exclude", "Any",
         "Recovery: exclude experimental GPU driver from cached collections"),
        ("org.watchthelight.XeGfxAGDC", True, "Exclude", "Any",
         "Recovery: exclude experimental GPU driver from cached collections"),
        ("org.watchthelight.XeGfxIntelFB", True, "Exclude", "Any",
         "Recovery: exclude experimental GPU driver from cached collections"),
        ("com.nullmoth.NMIntelFB", True, "Exclude", "Any",
         "Recovery: exclude experimental GPU driver from cached collections"),
    ],
    "boot": {"ShowPicker": True, "HideAuxiliary": False, "Timeout": 5},
    "security": {"ScanPolicy": 0},
    "debug": {"AppleDebug": True, "Target": 67},
}

EXPERIMENTAL_IDS = {
    "org.watchthelight.XeGfx",
    "org.watchthelight.XeGfxAGDC",
    "org.watchthelight.XeGfxAccel",
    "org.watchthelight.XeGfxIntelFB",
    "com.nullmoth.NMIntelFB",
}


def read_plist(path: Path) -> dict:
    with open(path, "rb") as fh:
        return plistlib.load(fh)


def write_plist(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    tmp.replace(path)


def set_kadd(config: dict, bundle: str, enabled: bool) -> bool:
    for entry in config.get("Kernel", {}).get("Add", []):
        if entry.get("BundlePath") == bundle:
            entry["Enabled"] = enabled
            return True
    return False


def apply_block(config: dict, spec) -> None:
    kernel = config.setdefault("Kernel", {})
    block = kernel.setdefault("Block", [])
    # 先移除所有实验性驱动的排除条目
    kernel["Block"] = [
        e for e in block if e.get("Identifier") not in EXPERIMENTAL_IDS
    ]
    block = kernel["Block"]
    if not spec:
        return
    existing = {e.get("Identifier") for e in block}
    for identifier, enabled, strategy, arch, comment in spec:
        if identifier in existing:
            continue
        block.append({
            "Arch": arch,
            "Comment": comment,
            "Enabled": enabled,
            "Identifier": identifier,
            "MaxKernel": "",
            "MinKernel": "",
            "Strategy": strategy,
        })


def describe(config: dict) -> str:
    kadd = {e.get("BundlePath"): bool(e.get("Enabled"))
            for e in config.get("Kernel", {}).get("Add", [])}
    block = config.get("Kernel", {}).get("Block", [])
    excl = sorted(e["Identifier"] for e in block
                  if e.get("Identifier") in EXPERIMENTAL_IDS)
    args = config.get("NVRAM", {}).get("Add", {}).get(GUID, {}).get("boot-args", "")
    boot = config.get("Misc", {}).get("Boot", {})
    lines = [
        "当前状态 / current state:",
        f"  XeGfx.kext           = {'ON ' if kadd.get('XeGfx.kext') else 'off'}",
        f"  XeGfxAGDC.kext       = {'ON ' if kadd.get('XeGfxAGDC.kext') else 'off'}",
        f"  XeGfxAccel.kext      = {'ON ' if kadd.get('XeGfxAccel.kext') else 'off'}",
        f"  实验性驱动 Exclude   = {excl if excl else '(无)'}",
        f"  boot-args            = {args}",
        f"  ShowPicker={boot.get('ShowPicker')}  Timeout={boot.get('Timeout')}  "
        f"ScanPolicy={config.get('Misc', {}).get('Security', {}).get('ScanPolicy')}",
    ]
    detected = "full" if (kadd.get("XeGfxAccel.kext") and not excl) else "safe"
    lines.append(f"  判定 profile          = {detected.upper()}")
    return "\n".join(lines)


def switch_script(efi: Path, profile: str) -> None:
    profiles_dir = efi / "Diagnostics" / "profiles"
    src = profiles_dir / f"gpu-display-capture.{profile}.command"
    dst = efi / "Diagnostics" / "gpu-display-capture.command"
    if not src.is_file():
        print(f"  提示：找不到 {src}，启动脚本保持不变", file=sys.stderr)
        return
    shutil.copy2(src, dst)
    print(f"  启动脚本 -> {src.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="切换 EFI profile：full / safe")
    ap.add_argument("--efi", required=True, help="EFI 根目录（含 OC/ 与 Diagnostics/）")
    ap.add_argument("--profile", choices=["full", "safe"], help="目标 profile；省略则只显示状态")
    ap.add_argument("--no-backup", action="store_true", help="不生成备份")
    args = ap.parse_args()

    efi = Path(args.efi)
    config_path = efi / "OC" / "config.plist"
    if not config_path.is_file():
        print(f"找不到 {config_path}", file=sys.stderr)
        return 2

    config = read_plist(config_path)
    if not args.profile:
        print(describe(config))
        return 0

    spec = FULL if args.profile == "full" else SAFE
    print(f"切换到 {args.profile.upper()} profile：{efi}")

    if not args.no_backup:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = config_path.with_suffix(f".plist.bak-{stamp}")
        shutil.copy2(config_path, backup)
        print(f"  已备份 -> {backup.name}")

    set_kadd(config, "XeGfxAGDC.kext", spec["agdc_enabled"])
    set_kadd(config, "XeGfxAccel.kext", spec["accel_enabled"])
    apply_block(config, spec["exclude_block"])
    config["NVRAM"]["Add"][GUID]["boot-args"] = spec["boot_args"]
    config["Misc"]["Boot"].update(spec["boot"])
    config["Misc"]["Security"].update(spec["security"])
    config["Misc"]["Debug"].update(spec["debug"])

    write_plist(config_path, config)
    print("  config.plist 已更新")

    switch_script(efi, args.profile)

    print()
    print(describe(read_plist(config_path)))
    print()
    if args.profile == "full":
        print("下一步（macOS 上，按顺序）：")
        print("  1. sudo bash <EFI>/EFI/Tools/prepare-metal-stack.command   # 修复 @rpath 并重签")
        print("  2. sudo bash <EFI>/EFI/Tools/full-install.command          # 安装系统卷组件")
        print("  3. 正常重启，等待约 3 分钟，回 Windows 读 Diagnostics/reports/")
        print("  若停在苹果标志：运行 efi_profile.py --profile safe，再执行 full-rollback.command")
    else:
        print("已切到 SAFE profile。若系统卷仍装着实验性 kext，请执行：")
        print("  sudo bash <EFI>/EFI/Tools/full-rollback.command")
    return 0


if __name__ == "__main__":
    sys.exit(main())
