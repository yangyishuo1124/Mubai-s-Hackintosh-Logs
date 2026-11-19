#!/usr/bin/env python3
"""EFI 结构校验 / Structural validator for the OpenCore EFI in this repository.

官方 ocvalidate 只在 macOS 上分发，本脚本用 Python 实现同等关键检查，Windows 与 macOS 都能跑：

  1. Kernel/Add 中每一条启用的 kext，其 BundlePath / PlistPath / ExecutablePath 实际存在
  2. Kernel/Block 的 Identifier 合法，且实验性驱动的 Exclude 与 profile 一致
  3. NVRAM/Add 的 GUID 键合法、boot-args 非空
  4. ACPI/Add 中每一条启用的 AML 实际存在
  5. OpenCore.efi / bootx64.efi 存在且非空
  6. EFI/Tools 里的 shell 脚本使用 LF 换行（CRLF 会让 macOS 上的脚本直接失败）
  7. Metal 栈的 @rpath 依赖是否都能在同目录解析（可解析 = 已修复 RPATH）

用法 / Usage:
    python validate_efi.py                 # 校验仓库内 EFI/
    python validate_efi.py --efi Z:/EFI    # 校验已挂载的 EFI 分区
"""

import argparse
import plistlib
import struct
import sys
from pathlib import Path

GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
DEBUG_GUID = "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14"
EXPERIMENTAL = {
    "org.watchthelight.XeGfx",
    "org.watchthelight.XeGfxAGDC",
    "org.watchthelight.XeGfxAccel",
    "org.watchthelight.XeGfxIntelFB",
    "com.nullmoth.NMIntelFB",
}

errors: list[str] = []
warnings: list[str] = []
notes: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


def macho_rpath_and_deps(path: Path):
    """返回 (rpaths, 依赖列表)。只处理单架构 Mach-O。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None, None
    if len(data) < 32:
        return None, None
    magic_le = struct.unpack_from("<I", data, 0)[0]
    if magic_le == 0xcafebabe:
        return None, None
    if magic_le == 0xfeedfacf:
        ncmds = struct.unpack_from("<I", data, 16)[0]
        pos = 32
    elif magic_le == 0xfeedface:
        ncmds = struct.unpack_from("<I", data, 12)[0]
        pos = 28
    else:
        return None, None
    rpaths, deps = [], []
    for _ in range(ncmds):
        if pos + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from("<II", data, pos)
        if cmd in (0x8000001C, 0x8000001D):
            off = struct.unpack_from("<I", data, pos + 8)[0]
            p = pos + off
            rpaths.append(data[p:data.index(b"\x00", p)].decode("utf-8", "replace"))
        elif cmd in (0x0C, 0x0D):
            off = struct.unpack_from("<I", data, pos + 8)[0]
            p = pos + off
            deps.append(data[p:data.index(b"\x00", p)].decode("utf-8", "replace"))
        pos += cmdsize
    return rpaths, deps


def validate(efi: Path) -> None:
    config_path = efi / "OC" / "config.plist"
    if not config_path.is_file():
        err(f"缺少 {config_path}")
        return

    with open(config_path, "rb") as fh:
        config = plistlib.load(fh)

    # --- 1. Kernel/Add -------------------------------------------------
    kexts_dir = efi / "OC" / "Kexts"
    enabled_count = 0
    for entry in config.get("Kernel", {}).get("Add", []):
        bundle = entry.get("BundlePath")
        if not entry.get("Enabled"):
            continue
        enabled_count += 1
        target = kexts_dir / bundle
        if not target.is_dir():
            err(f"Kernel/Add 启用但目录不存在：{bundle}")
            continue
        for key in ("PlistPath", "ExecutablePath"):
            rel = entry.get(key)
            if rel and not (target / rel).is_file():
                err(f"启用 kext {bundle} 的 {key} 不存在：{rel}")
        # 插件包也要确认
        if bundle.endswith(".kext") and (target / "Contents" / "PlugIns").is_dir():
            for plug in (target / "Contents" / "PlugIns").iterdir():
                if not (plug / "Contents" / "Info.plist").is_file():
                    err(f"插件缺少 Info.plist：{bundle}/Contents/PlugIns/{plug.name}")
    note(f"Kernel/Add 启用 kext：{enabled_count} 项")

    # --- 2. Kernel/Block ------------------------------------------------
    block = config.get("Kernel", {}).get("Block", [])
    excluded = {e.get("Identifier") for e in block} & EXPERIMENTAL
    accel_on = any(e.get("BundlePath") == "XeGfxAccel.kext" and e.get("Enabled")
                   for e in config.get("Kernel", {}).get("Add", []))
    agdc_on = any(e.get("BundlePath") == "XeGfxAGDC.kext" and e.get("Enabled")
                  for e in config.get("Kernel", {}).get("Add", []))
    if accel_on and "org.watchthelight.XeGfxAccel" in excluded:
        err("XeGfxAccel 在 Kernel/Add 启用，却被 Kernel/Block Exclude —— 引导期注入与缓存排除互相矛盾")
    if agdc_on and "org.watchthelight.XeGfxAGDC" in excluded:
        err("XeGfxAGDC 在 Kernel/Add 启用，却被 Kernel/Block Exclude")
    for e in block:
        ident = e.get("Identifier", "")
        if not ident:
            err("Kernel/Block 存在缺少 Identifier 的条目")
        if e.get("Strategy") not in ("Disable", "Exclude"):
            err(f"Kernel/Block {ident} 的 Strategy 非法：{e.get('Strategy')}")
    if excluded:
        note(f"实验性驱动 Exclude：{sorted(excluded)}")
    else:
        note("实验性驱动 Exclude：无（全功能 profile）")
    profile = "FULL" if (accel_on and not excluded) else "SAFE"
    note(f"判定 profile：{profile}")

    # --- 3. NVRAM -------------------------------------------------------
    nvram_add = config.get("NVRAM", {}).get("Add", {})
    if GUID not in nvram_add:
        err(f"NVRAM/Add 缺少 {GUID}")
    else:
        args = nvram_add[GUID].get("boot-args")
        if not args:
            err("boot-args 为空")
        else:
            note(f"boot-args：{args}")
            if "xegfx_bootstage=" not in args:
                warn("boot-args 没有 xegfx_bootstage=，XeGfx 初始化阶段未指定")
    for key in nvram_add:
        if key.upper() not in (GUID, DEBUG_GUID, "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102"):
            warn(f"NVRAM/Add 出现非 GUID 键：{key}")

    # --- 4. ACPI --------------------------------------------------------
    acpi_dir = efi / "OC" / "ACPI"
    for entry in config.get("ACPI", {}).get("Add", []):
        if not entry.get("Enabled"):
            continue
        rel = entry.get("Path")
        if rel and not (acpi_dir / rel).is_file():
            err(f"ACPI/Add 启用但文件不存在：{rel}")

    # --- 5. 引导文件 ----------------------------------------------------
    for rel in ("OC/OpenCore.efi", "BOOT/bootx64.efi"):
        p = efi / rel
        if not p.is_file():
            err(f"缺少 {rel}")
        elif p.stat().st_size == 0:
            err(f"{rel} 为空")

    # --- 6. 脚本换行符 ---------------------------------------------------
    scripts = list((efi / "Tools").glob("*.command")) + list((efi / "Diagnostics").glob("*.command"))
    scripts += list((efi / "Diagnostics" / "profiles").glob("*.command"))
    for s in scripts:
        if not s.is_file():
            continue
        raw = s.read_bytes()
        if b"\r\n" in raw:
            err(f"脚本含 CRLF 换行，macOS 上会执行失败：{s.relative_to(efi)}")
    note(f"检查脚本换行符：{len(scripts)} 个")

    # --- 7. Metal 栈 @rpath ---------------------------------------------
    gpu = efi / "Diagnostics" / "GPU"
    vulkan = gpu / "vulkan"
    metal = gpu / "metal"
    if not vulkan.is_dir() or not metal.is_dir():
        warn("缺少 Diagnostics/GPU/vulkan 或 metal —— Metal 栈未随 EFI 提供")
    else:
        # 运行时这些 dylib 全部平铺到 /Library/GPUBundles/nvmtl/，
        # 且 libvulkan.1.dylib 部署时改名为 libvulkan.dylib。
        # 按「部署后的名字集合」判断能否解析，而不是按 EFI 里的源目录。
        deploy_rename = {"libvulkan.1.dylib": "libvulkan.dylib"}
        deployed = set()
        for d in (vulkan, metal):
            for f in d.iterdir():
                if f.is_file():
                    deployed.add(deploy_rename.get(f.name, f.name))
        for target_dir in (vulkan, metal):
            for binary in sorted(target_dir.iterdir()):
                if not binary.is_file():
                    continue
                rpaths, deps = macho_rpath_and_deps(binary)
                if rpaths is None:
                    note(f"{binary.name}：非单架构 Mach-O，跳过")
                    continue
                rdeps = [d for d in (deps or []) if d.startswith("@rpath/")]
                if not rdeps:
                    continue
                if not rpaths:
                    warn(f"{binary.name} 没有 LC_RPATH，但依赖 {rdeps} —— "
                         f"macOS 上会解析失败（这正是 2026-11-17 19:26 的崩溃原因）")
                    continue
                for dep in rdeps:
                    target = dep.split("/", 1)[1]
                    if target not in deployed:
                        warn(f"{binary.name} 依赖 {dep}，但部署目录里没有 {target}")
        if not (vulkan / "libvulkan_intel.dylib").is_file():
            err("缺少 libvulkan_intel.dylib")
        if not (metal / "NVMTLDriver").is_file():
            err("缺少 NVMTLDriver")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--efi", default=None, help="EFI 根目录；默认校验脚本同级仓库的 EFI/")
    args = ap.parse_args()

    if args.efi:
        efi = Path(args.efi)
    else:
        efi = Path(__file__).resolve().parent.parent / "EFI"
    if not efi.is_dir():
        print(f"EFI 目录不存在：{efi}", file=sys.stderr)
        return 2

    print(f"校验 EFI：{efi}")
    print("=" * 68)
    validate(efi)

    for n in notes:
        print(f"  · {n}")
    for w in warnings:
        print(f"  ! 警告：{w}")
    for e in errors:
        print(f"  × 错误：{e}")
    print("=" * 68)
    if errors:
        print(f"校验未通过：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"校验通过：0 错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
