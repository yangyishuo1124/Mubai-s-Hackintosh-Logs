from pathlib import Path
import sys,tempfile,subprocess
s=Path(sys.argv[1]).read_text()
guard=s[s.index(' // B0A0 stage 3 is the current boundary.'):s.index('\n#endif\n\tgRunning = s;',s.index(' // B0A0 stage 3 is the current boundary.'))]
commit=s[s.index('  if (metadata_rc != 1)'):s.index('\n }\n /* FreeBSD',s.index('  if (metadata_rc != 1)'))]
assert 'if (rc == 1 && gPtlMetadataBaseline) rc = xg_display_check();' in s
assert 'ptl-stage3-metadata-v3' in s
code=r'''
#include <cassert>
#include <cerrno>
#include <cstdint>
bool gPtlMetadataBaseline=false,gXeBaseline=true;
struct Snapshot { uint64_t pte_hash; } gPtlBootSnapshot;
uint64_t gXePhysStart,gXePhysSize,gXePteSum;
int gXeBootFound=-6,calls=0;
void IOLog(const char*,...) {}
int stage(int s){
''' + guard + r'''
 calls++;return 1;
}
int capture(int metadata_rc){
 Snapshot after{123};uint64_t lo=0x7c800000,hi=lo+0xfa0000;
''' + commit + r'''
}
int main(){
 assert(capture(-EPROTO)==-EPROTO && !gPtlMetadataBaseline);
 assert(capture(0)==0 && !gPtlMetadataBaseline && gXeBootFound==0);
 assert(capture(1)==0 && gPtlMetadataBaseline && !gXeBaseline);
 assert(gXeBootFound==1 && gXePhysStart==0x7c800000 && gXePhysSize==0xfa0000);
 assert(gXePteSum==123 && gPtlBootSnapshot.pte_hash==123);
 assert(stage(3)==1 && calls==1);
 assert(stage(4)==-EOPNOTSUPP && calls==1);
 assert(stage(7)==-EOPNOTSUPP && calls==1);
 gPtlMetadataBaseline=false;assert(stage(4)==1 && calls==2);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'policy.cpp';p.write_text(code);exe=Path(d)/'policy'
 subprocess.run(['c++','-std=c++17','-Wall','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Stage-3 policy passed: failed baseline rejected, metadata commit distinguished from pixel baseline, stages 4+ blocked before initialization.')
