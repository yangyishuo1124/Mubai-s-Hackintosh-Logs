#!/bin/zsh
# B0A0 bring-up: use the boot-injected diagnostic kext and stop at stage 2.
# No boot configuration, system-volume or AuxiliaryKC installation changes.
set -eu
base="${0:A:h}"
[[ "$(id -u)" == 0 ]] || { print '请用 sudo zsh 运行 / Run with sudo zsh'; exit 1; }
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || exit 1
print '本版 stage 2 已触发黑屏重启；暂时只采集崩溃证据，不再次触发。'
print 'This stage 2 build caused a black-screen reboot; collecting only.'
zsh "$base/collect.command"
exit $?
[[ -d "$base/GPU/XeGfx.kext" ]] || { print '缺少探测驱动 / Probe kext missing'; exit 1; }
out="$base/reports/gpu-probe-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$base/reports"
exec > >(tee "$out") 2>&1
print '仅运行 stage 2 硬件探测，不启动 GPU 引擎或 Metal。'
print 'Stage 2 probe only; no GPU engine or Metal initialization.'
cd "$base/GPU"
shasum -a 256 -c SHA256.txt
if ! sysctl -n debug.xegfx_stage >/dev/null 2>&1; then
    print '开机驱动尚未启动，采集后停止，不再尝试手动加载。'
    print 'Boot driver is not active; collecting without manual loading.'
    zsh "$base/collect.command"
    exit 1
fi

stage="$(sysctl -n debug.xegfx_stage)"
[[ "$stage" == <0-2> ]] || { print '已有其他阶段运行，本脚本停止 / Unexpected existing stage; stopping'; exit 1; }
sysctl debug.xegfx_stage=2
sysctl debug.xegfx_stage
sysctl -b debug.xegfx_log
zsh "$base/collect.command"
print '探测结束。驱动由 EFI 配置开机加载。 / Probe finished; EFI controls boot loading.'
