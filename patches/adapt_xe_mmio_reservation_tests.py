from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old="""static void pci_read_config_dword(void *p, int reg, u32 *v) {
 *v=reg==0xc0 ? 0x80000000u : 1;
}"""
new="""static u64 mock_dsm=0x180000000ull;
#define DSMBASE 0x1080c0
#define BDSM_MASK (~0xfffffull)
static void *xe_root_tile_mmio(struct xe_device *xe) { return xe; }
static u64 xe_mmio_read64_2x32(void *mmio, int reg) { assert(reg==DSMBASE); return mock_dsm; }"""
assert s.count(old)==1
s=s.replace(old,new).replace(' void *pdev=0;\n','')
needle=' fb=dsm; bytes=0x4000000; run(&xe,&m,0x2000000); assert(remaining==0);'
assert s.count(needle)==1
s=s.replace(needle,needle+"""
 /* Actual B0A0 metadata: PCI DSM is zero; MMIO gives 0x7c800000. */
 mock_dsm=0x7c800000ull; fb=mock_dsm; bytes=0xfa0000;
 m=(struct mgr){bar,0x800000}; run(&xe,&m,0x2000000);
 assert(m.io_base==bar+0xfa0000 && m.stolen_base==0x17a0000);
 assert(remaining==0x1060000);
 mock_dsm=dsm;
""")
p.write_text(s)
