"""把全功能 EFI 覆盖到磁盘 EFI 分区（带校验的部署）。

安全约束：
  - 先完整备份 OC / Diagnostics / Boot / Tools，并逐文件 SHA-256 校验
  - EFI\\Microsoft（Windows 引导）绝不触碰，前后哈希比对
  - 覆盖后逐文件读回校验
  - 覆盖失败自动从备份回滚
  - **已修复的 Metal 载荷保护**：如果目标 EFI 上存在 Diagnostics/GPU/.rpath-fixed 标记
    （由 macOS 侧的 prepare-metal-stack.command 成功后写入），说明该 EFI 分区上的
    GPU/metal 与 GPU/vulkan 已经被 install_name_tool 修好并重签名。此时覆盖会跳过这两个
    目录，保留磁盘上的已修复版本 —— 否则会静默回退成未修复版本，重演 2026-11-17 19:26
    的 WindowServer SIGABRT 崩溃循环。
"""
import hashlib
import json
import os
import plistlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SRC = Path(sys.argv[1])          # 新 EFI 源目录
DST = Path(sys.argv[2])          # 磁盘 EFI 根目录（如 Z:\EFI）
BACKUP_ROOT = Path(sys.argv[3])  # 备份根目录

SCOPES = ("OC", "Diagnostics", "Boot", "Tools")
PROTECTED = ("Microsoft",)

# Metal 修复标记与需要保护的子目录（相对 Diagnostics/）
METAL_MARKER = Path("GPU/.rpath-fixed")
METAL_KEEP = (Path("GPU/metal"), Path("GPU/vulkan"))


def manifest(folder: Path) -> dict:
    out = {}
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        key = p.relative_to(folder).as_posix()
        try:
            out[key] = hashlib.sha256(p.read_bytes()).hexdigest()
        except PermissionError:
            # 受 ACL 保护（如 EFI\Microsoft\Boot\BCD）：改用大小与修改时间作为指纹
            st = p.stat()
            out[key] = f"meta:{st.st_size}:{int(st.st_mtime)}"
    return out


def die(msg):
    print(f"停止：{msg}")
    sys.exit(1)


def copy_verify(src: Path, dst: Path, skip_prefixes=()):
    """复制目录并读回校验；skip_prefixes 下的文件允许与源不同（被有意保留）。"""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    s, d = manifest(src), manifest(dst)
    bad = []
    for k, v in s.items():
        if any(k.startswith(p) for p in skip_prefixes):
            continue
        if d.get(k) != v:
            bad.append((k, v, d.get(k)))
    return bad


stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = BACKUP_ROOT / f"disk-efi-backup-{stamp}"
backup.mkdir(parents=True)

print("=== 0. 前置检查 ===")
if not (SRC / "OC" / "config.plist").is_file():
    die(f"源 EFI 不完整：{SRC}")
if not DST.is_dir():
    die(f"目标不存在：{DST}")
with open(SRC / "OC" / "config.plist", "rb") as fh:
    cfg = plistlib.load(fh)
print(f"  源   : {SRC}")
print(f"  目标 : {DST}")
print(f"  备份 : {backup}")
protected_before = {}
for name in PROTECTED:
    p = DST / name
    if p.is_dir():
        protected_before[name] = manifest(p)
        print(f"  受保护目录 {name}：{len(protected_before[name])} 个文件")

def source_has_loader_rpath() -> bool:
    """源 EFI 里的 metal/vulkan dylib 是否已带 @loader_path 的 LC_RPATH。"""
    import struct as _struct
    for rel in ("Diagnostics/GPU/vulkan/libvulkan_intel.dylib",
                "Diagnostics/GPU/vulkan/libvulkan.1.dylib",
                "Diagnostics/GPU/vulkan/libdrm.2.dylib",
                "Diagnostics/GPU/metal/libnvmtl_translate.dylib"):
        p = SRC / rel
        if not p.is_file():
            continue
        data = p.read_bytes()
        if len(data) < 32:
            continue
        try:
            ncmds, sizeofcmds = _struct.unpack_from("<II", data, 16)
            pos = 32
            for _ in range(ncmds):
                cmd, cmdsize = _struct.unpack_from("<II", data, pos)
                if cmd == 0x8000001C:            # LC_RPATH
                    off = _struct.unpack_from("<I", data, pos + 8)[0]
                    s = data[pos + off:data.index(b"\x00", pos + off)].decode("utf-8", "replace")
                    if "@loader_path" in s:
                        return True
                pos += cmdsize
        except (ValueError, struct.error):
            continue
    return False


marker = DST / "Diagnostics" / METAL_MARKER
if marker.is_file():
    print(f"  ★ 检测到 Metal 修复标记 {METAL_MARKER} —— 部署时保留磁盘上已重签名的 metal/vulkan 载荷")
else:
    print("  · 未检测到 Metal 修复标记 —— 将写入源 EFI 中的 metal/vulkan 载荷")
if source_has_loader_rpath():
    print("  ★ 源载荷已含 @loader_path 的 LC_RPATH（只需在 macOS 上跑 prepare-metal-stack.command 重签名）")
else:
    print("  ! 源载荷缺少 @loader_path 的 LC_RPATH —— 必须先在 macOS 上跑 prepare-metal-stack.command")

print()
print("=== 1. 备份现有 EFI ===")
for scope in SCOPES:
    src = DST / scope
    if not src.is_dir():
        continue
    shutil.copytree(src, backup / scope)
    if manifest(backup / scope) != manifest(src):
        die(f"{scope} 备份校验失败，已中止")
    print(f"  已备份并校验 {scope}（{len(manifest(src))} 个文件）")
(backup / "protected-sha256.json").write_text(
    json.dumps(protected_before, indent=2), encoding="utf-8")
print("  备份完成")

print()
print("=== 2. 写入新 EFI ===")
try:
    for scope in SCOPES:
        src = SRC / scope
        dst = DST / scope
        if not src.is_dir():
            continue

        kept = []
        stash = backup / "_fixed-metal-stash"
        if scope == "Diagnostics" and marker.is_file():
            for rel in METAL_KEEP:
                s = dst / rel
                if s.is_dir():
                    (stash / rel.name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(s, stash / rel.name)
                    kept.append(rel)

        skip = tuple()
        if kept:
            skip = tuple(rel.as_posix() + "/" for rel in kept)

        bad = copy_verify(src, dst, skip_prefixes=skip)

        if kept:
            for rel in kept:
                target = dst / rel
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(stash / rel.name, target)
            print(f"  已写入并读回校验 {scope}（保留已修复载荷：{', '.join(r.as_posix() for r in kept)}）")
        else:
            print(f"  已写入并读回校验 {scope}（{len(manifest(dst))} 个文件）")

        if bad:
            raise RuntimeError(f"{scope} 读回校验失败：{bad[:5]}")
except Exception as exc:
    print(f"  写入失败：{exc}")
    print("  正在从备份回滚 ...")
    for scope in SCOPES:
        b = backup / scope
        if not b.is_dir():
            continue
        d = DST / scope
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(b, d)
    die("已回滚到备份状态")

print()
print("=== 3. 受保护目录比对 ===")
for name in PROTECTED:
    p = DST / name
    if not p.is_dir():
        continue
    after = manifest(p)
    if after != protected_before.get(name):
        die(f"{name} 发生变化，已中止")
    print(f"  {name} 未改动（{len(after)} 个文件哈希一致）")

print()
print("=== 4. 部署后状态 ===")
with open(DST / "OC" / "config.plist", "rb") as fh:
    now = plistlib.load(fh)
kadd = {e.get("BundlePath"): bool(e.get("Enabled")) for e in now["Kernel"]["Add"]}
block = now.get("Kernel", {}).get("Block", [])
excl = sorted(e["Identifier"] for e in block if e.get("Enabled"))
for name in ("XeGfx.kext", "XeGfxAGDC.kext", "XeGfxAccel.kext"):
    print(f"  {name:<20} {'ON ' if kadd.get(name) else 'off'}")
print(f"  实验性驱动 Exclude（启用中）: {excl or '(无)'}")
print(f"  boot-args: {now['NVRAM']['Add']['7C436110-AB2A-4BBB-A880-FE41995C9F82']['boot-args']}")
print(f"  ShowPicker={now['Misc']['Boot'].get('ShowPicker')} "
      f"HideAuxiliary={now['Misc']['Boot'].get('HideAuxiliary')} "
      f"Timeout={now['Misc']['Boot'].get('Timeout')} "
      f"ScanPolicy={now['Misc']['Security'].get('ScanPolicy')} "
      f"AppleDebug={now['Misc']['Debug'].get('AppleDebug')} "
      f"Target={now['Misc']['Debug'].get('Target')}")
print(f"  Tools/ 已部署: {(DST / 'Tools').is_dir()}")
if (DST / 'Diagnostics' / METAL_MARKER).is_file():
    print("  ★ Metal 修复标记仍在（磁盘载荷为已重签名版本）")
else:
    print("  · 无 Metal 修复标记（磁盘载荷尚未在 macOS 上重签名，需跑 prepare-metal-stack.command）")
print()
print(f"完成。备份目录：{backup}")
