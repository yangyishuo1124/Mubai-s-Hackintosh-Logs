#!/bin/zsh
# B0A0 bring-up: metadata baseline and stage-3 bus/DMA initialization only.
# No boot configuration, system-volume or AuxiliaryKC installation changes.
set -eu
base="${0:A:h}"
[[ "$(id -u)" == 0 ]] || { print '请用 sudo zsh 运行 / Run with sudo zsh'; exit 1; }
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || exit 1
[[ -d "$base/GPU/XeGfx.kext" ]] || { print '缺少探测驱动 / Probe kext missing'; exit 1; }
out="$base/reports/gpu-probe-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$base/reports"
exec > >(tee "$out") 2>&1
print '运行元数据基线及 stage 3 总线/DMA 初始化，随后核对显示状态；不进入 GPU 初始化。'
print 'Metadata baseline and stage-3 bus/DMA initialization; no GPU SYSINIT or pixel access.'
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
if [[ "$policy" != *'"XeGfxProbePolicy" = "ptl-stage3-metadata-v3"'* ]]; then
    print '当前加载的仍是旧版驱动，停止探测，请重启后再运行。'
    print 'Loaded driver lacks the stage-3 policy; reboot before probing.'
    zsh "$base/collect.command"
    exit 1
fi
stage="$(sysctl -n debug.xegfx_stage)"
[[ "$stage" == <0-3> ]] || { print '已有其他阶段运行，本脚本停止 / Unexpected existing stage; stopping'; exit 1; }
sysctl debug.xegfx_stage=3
sysctl debug.xegfx_stage
print '阶段结果数组（索引对应阶段号） / Signed results indexed by stage:'
sysctl -b debug.xegfx_results | od -An -v -t d4
sysctl -b debug.xegfx_log
print '预期完成 stage 3 并保存初始化后的 GOP 检查；stage 4 由驱动阻断，Metal 未启用。'
print 'Expected boundary: stage 3 with post-bus GOP checks. Stage 4 is blocked; no Metal.'
zsh "$base/collect.command"
print '探测结束。驱动由 EFI 配置开机加载。 / Probe finished; EFI controls boot loading.'
