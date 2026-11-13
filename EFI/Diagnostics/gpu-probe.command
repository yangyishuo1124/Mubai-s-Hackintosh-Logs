#!/bin/zsh
# B0A0 bring-up: use the boot-injected diagnostic kext and stop at stage 2.
# No boot configuration, system-volume or AuxiliaryKC installation changes.
set -eu
base="${0:A:h}"
[[ "$(id -u)" == 0 ]] || { print '请用 sudo zsh 运行 / Run with sudo zsh'; exit 1; }
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || exit 1
[[ -d "$base/GPU/XeGfx.kext" ]] || { print '缺少探测驱动 / Probe kext missing'; exit 1; }
out="$base/reports/gpu-probe-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$base/reports"
exec > >(tee "$out") 2>&1
print '仅采集寄存器/GGTT 元数据；B0A0 不映射或读取显存像素。'
print 'Metadata only; B0A0 CPU framebuffer mapping and reads are blocked.'
cd "$base/GPU"
shasum -a 256 -c SHA256.txt
if ! sysctl -n debug.xegfx_stage >/dev/null 2>&1; then
    print '开机驱动尚未启动，采集后停止，不再尝试手动加载。'
    print 'Boot driver is not active; collecting without manual loading.'
    zsh "$base/collect.command"
    exit 1
fi

# Refuse an older boot-loaded binary even if the files on EFI were replaced.
policy="$(ioreg -r -c XeGfxResident -l)"
if [[ "$policy" != *'"XeGfxProbePolicy" = "ptl-metadata-only-v1"'* ]]; then
    print '当前加载的仍是旧版驱动，停止探测，请重启后再运行。'
    print 'Loaded driver lacks the metadata-only guard; reboot before probing.'
    zsh "$base/collect.command"
    exit 1
fi
stage="$(sysctl -n debug.xegfx_stage)"
[[ "$stage" == <0-2> ]] || { print '已有其他阶段运行，本脚本停止 / Unexpected existing stage; stopping'; exit 1; }
sysctl debug.xegfx_stage=2
sysctl debug.xegfx_stage
print '阶段结果数组（索引对应阶段号） / Signed results indexed by stage:'
sysctl -b debug.xegfx_results | od -An -v -t d4
sysctl -b debug.xegfx_log
print 'B0A0 预期停止于显存访问阻断，stage 2 未完成；不代表 Metal 已可用。'
print 'B0A0 is expected to stop at the CPU-access guard; stage 2 remains incomplete.'
zsh "$base/collect.command"
print '探测结束。驱动由 EFI 配置开机加载。 / Probe finished; EFI controls boot loading.'
