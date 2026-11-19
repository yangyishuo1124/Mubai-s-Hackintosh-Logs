#!/usr/bin/env python3
"""给 Mach-O dylib 补 @loader_path 的 LC_RPATH，并改写 LC_ID_DYLIB。

为什么需要它：
  2026-11-17 19:26 的桌面接入失败，根因是 CI 产物 libvulkan_intel.dylib 没有
  LC_RPATH，却用 @rpath/libdrm.2.dylib 引用依赖 -> @rpath 无法解析 -> Vulkan
  初始化失败 -> CoreDisplay 断言 -> WindowServer SIGABRT 循环。

为什么不用 otool/ install_name_tool：
  那些是 macOS 工具。但这四个 dylib 来自 CI 产物，头部通常有富余空间，
  在 Windows 上就能把结构改对，再由 macOS 侧的 prepare-metal-stack.command
  做 codesign（重算签名）与 dyld 实载验证。

本工具的关键约束：
  * **不改变文件大小**。LC_RPATH 插进 load command 区末尾与首个 section 之间的
    空闲区，因此所有段偏移、__LINKEDIT 位置、LC_CODE_SIGNATURE 的 codeLimit
    全部保持不变。
  * 改写 header 的 ncmds / sizeofcmds。
  * 只改 header 页内的字节 -> 已有签名失效，需要 macOS 侧重新 codesign。
    prepare-metal-stack.command 会自动做这一步。
  * 改写后必须重新解析并逐项校验，任何一项不符就拒绝写盘。

用法：
  python tools/patch_macho_rpath.py <file.dylib> [...]
  python tools/patch_macho_rpath.py --install-name libvulkan.1.dylib=@rpath/libvulkan.dylib <file>
  python tools/patch_macho_rpath.py --dry-run <file>
"""
import argparse
import struct
import sys
from pathlib import Path

MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
LC_ID_DYLIB = 0xD
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC
LC_RPATH = 0x8000001C
LC_CODE_SIGNATURE = 0x1D

HDR_SIZE = 32
RPATH_PATH = b"@loader_path"


class MachOError(Exception):
    pass


def _cstr(buf, off, end):
    raw = buf[off:end]
    idx = raw.find(b"\x00")
    if idx >= 0:
        raw = raw[:idx]
    return raw.decode("utf-8", "replace")


def parse(buf):
    """解析 64 位 Mach-O，返回头信息与 load command 清单。"""
    if len(buf) < HDR_SIZE:
        raise MachOError("文件太短，不是 Mach-O")
    magic = struct.unpack_from("<I", buf, 0)[0]
    if magic == MH_MAGIC_64:
        endian = "<"
    elif magic == MH_CIGAM_64:
        endian = ">"
    else:
        raise MachOError(f"不支持的 magic {magic:#x}（只支持 64 位 Mach-O）")

    ncmds, sizeofcmds = struct.unpack_from(endian + "II", buf, 16)
    end_of_cmds = HDR_SIZE + sizeofcmds
    if end_of_cmds > len(buf):
        raise MachOError("sizeofcmds 超出文件范围")

    cmds = []
    off = HDR_SIZE
    for _ in range(ncmds):
        if off + 8 > len(buf):
            raise MachOError("load command 越界")
        cmd, cmdsize = struct.unpack_from(endian + "II", buf, off)
        if cmdsize == 0 or off + cmdsize > len(buf):
            raise MachOError(f"load command cmdsize 非法 (cmd={cmd:#x}, cmdsize={cmdsize})")
        cmds.append({"cmd": cmd, "cmdsize": cmdsize, "off": off})
        off += cmdsize
    if off != end_of_cmds:
        raise MachOError("load command 累加长度与 sizeofcmds 不一致")

    rpaths = []
    id_dylib = None
    deps = []
    segments = []
    code_sig = None
    first_section = None
    for c in cmds:
        o = c["off"]
        if c["cmd"] == LC_RPATH:
            no = struct.unpack_from(endian + "I", buf, o + 8)[0]
            rpaths.append(_cstr(buf, o + no, o + c["cmdsize"]))
        elif c["cmd"] == LC_ID_DYLIB:
            no = struct.unpack_from(endian + "I", buf, o + 8)[0]
            id_dylib = {"name": _cstr(buf, o + no, o + c["cmdsize"]),
                        "name_off": no, "area": c["cmdsize"] - no, "off": o}
        elif c["cmd"] in (LC_LOAD_DYLIB, 0x80000018, 0x8000001F, 0x80000023):
            no = struct.unpack_from(endian + "I", buf, o + 8)[0]
            deps.append(_cstr(buf, o + no, o + c["cmdsize"]))
        elif c["cmd"] == LC_CODE_SIGNATURE:
            code_sig = struct.unpack_from(endian + "I", buf, o + 8)[0]
        elif c["cmd"] == LC_SEGMENT_64:
            segname = buf[o + 8:o + 24].split(b"\x00")[0].decode("utf-8", "replace")
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from(endian + "QQQQ", buf, o + 24)
            nsects = struct.unpack_from(endian + "I", buf, o + 64)[0]
            segments.append((segname, fileoff, filesize))
            base = o + 72
            for i in range(nsects):
                soff = struct.unpack_from(endian + "I", buf, base + i * 80 + 48)[0]
                if soff and (first_section is None or soff < first_section):
                    first_section = soff

    return {
        "endian": endian, "ncmds": ncmds, "sizeofcmds": sizeofcmds,
        "end_of_cmds": end_of_cmds, "cmds": cmds, "rpaths": rpaths,
        "id_dylib": id_dylib, "deps": deps, "segments": segments,
        "code_sig": code_sig, "first_section": first_section, "size": len(buf),
    }


def build_rpath_cmd(endian):
    """LC_RPATH: cmd(4) cmdsize(4) path_offset(4) + 路径串。cmdsize 必须是 8 的倍数。"""
    path = RPATH_PATH + b"\x00"
    pad = (-len(path)) % 4
    path = path + b"\x00" * pad
    base = 12
    total = base + len(path)
    total = (total + 7) // 8 * 8
    body = struct.pack(endian + "III", LC_RPATH, total, base) + path
    body += b"\x00" * (total - len(body))
    return body


def patch(buf, new_install_name=None):
    """返回 (新字节, 变更说明列表)。文件大小保持不变。"""
    info = parse(buf)
    endian = info["endian"]
    notes = []
    out = bytearray(buf)

    # 1) 改写 LC_ID_DYLIB（若指定）
    if new_install_name:
        d = info["id_dylib"]
        if d is None:
            raise MachOError("该文件没有 LC_ID_DYLIB")
        new = new_install_name.encode()
        if len(new) + 1 > d["area"]:
            raise MachOError(f"新 install name 过长：需要 {len(new)+1} 字节，可用 {d['area']}")
        o = d["off"]
        no = d["name_off"]
        start, end = o + no, o + no + d["area"]
        out[start:end] = new + b"\x00" * (d["area"] - len(new))
        if len(out) != len(buf):
            raise MachOError(f"改写 install name 后长度变了：{len(buf)} -> {len(out)}")
        notes.append(f"LC_ID_DYLIB: {d['name']} -> {new_install_name}")

    # 2) 补 LC_RPATH @loader_path
    if not any(rp == RPATH_PATH.decode() for rp in info["rpaths"]):
        cmd = build_rpath_cmd(endian)
        need = len(cmd)
        slack = (info["first_section"] - info["end_of_cmds"]) if info["first_section"] else -1
        if slack < need:
            raise MachOError(f"头部空间不足：可用 {slack} 字节，需要 {need}")
        at = info["end_of_cmds"]
        out[at:at + need] = cmd
        struct.pack_into(endian + "II", out, 16,
                         info["ncmds"] + 1, info["sizeofcmds"] + need)
        if len(out) != len(buf):
            raise MachOError(f"插入 LC_RPATH 后长度变了：{len(buf)} -> {len(out)}")
        notes.append(f"新增 LC_RPATH @loader_path（{need} 字节，插入于 {at}，余量 {slack}）")
    else:
        notes.append("已有 @loader_path RPATH，跳过")

    return bytes(out), notes


def verify(original, patched, expect_install_name=None):
    """改写后逐项校验；任何不符都抛错。"""
    a, b = parse(original), parse(patched)
    problems = []
    if len(original) != len(patched):
        problems.append(f"文件大小变了：{len(original)} -> {len(patched)}")
    if b["size"] != a["size"]:
        problems.append("size 字段不一致")
    if a["segments"] != b["segments"]:
        problems.append(f"段布局变了：{a['segments']} -> {b['segments']}")
    if a["code_sig"] != b["code_sig"]:
        problems.append(f"LC_CODE_SIGNATURE 偏移变了：{a['code_sig']} -> {b['code_sig']}")
    if b["end_of_cmds"] > (b["first_section"] or 1 << 62):
        problems.append("load command 区越过首个 section")
    if b["end_of_cmds"] > 4096:
        problems.append(f"load command 区越过首个 4K 页（{b['end_of_cmds']}），会移动后续内容")
    if a["deps"] != b["deps"]:
        problems.append("依赖列表被意外改动")
    if not any(rp == RPATH_PATH.decode() for rp in b["rpaths"]):
        problems.append("改写后仍没有 @loader_path RPATH")
    if expect_install_name:
        if not b["id_dylib"] or b["id_dylib"]["name"] != expect_install_name:
            got = b["id_dylib"]["name"] if b["id_dylib"] else None
            problems.append(f"install name 不符：{got} != {expect_install_name}")
    # 所有 load command 必须仍在文件内且 cmdsize 合法
    for c in b["cmds"]:
        if c["off"] + c["cmdsize"] > len(patched):
            problems.append(f"load command 越界：off={c['off']} size={c['cmdsize']}")
    if problems:
        raise MachOError("校验失败：" + "；".join(problems))
    return b


def main():
    ap = argparse.ArgumentParser(description="给 Mach-O dylib 补 @loader_path LC_RPATH")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--install-name", help="改写 LC_ID_DYLIB，格式 旧名=新名（只对单个文件生效）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    old = new = None
    if args.install_name:
        if "=" not in args.install_name:
            print("停止：--install-name 需要 旧名=新名 格式", file=sys.stderr)
            return 2
        old, new = args.install_name.split("=", 1)

    rc = 0
    for f in args.files:
        p = Path(f)
        try:
            raw = p.read_bytes()
            target = new if (old and p.name == old) else None
            patched, notes = patch(raw, target)
            info = verify(raw, patched, target)
            print(f"=== {p.name} ===")
            for n in notes:
                print(f"    {n}")
            print(f"    LC_RPATH 现在: {info['rpaths']}")
            if info["id_dylib"]:
                print(f"    LC_ID_DYLIB   : {info['id_dylib']['name']}")
            print(f"    文件大小不变   : {len(raw)} -> {len(patched)}")
            print(f"    段布局不变     : {info['segments']}")
            print(f"    签名偏移不变   : {info['code_sig']}")
            if not args.dry_run:
                p.write_bytes(patched)
                print(f"    已写入 {p}")
            print()
        except (MachOError, OSError) as exc:
            print(f"停止：{p.name} 处理失败：{exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
