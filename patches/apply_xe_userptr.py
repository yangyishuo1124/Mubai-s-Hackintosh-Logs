from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1])
p = root / 'xkpi/xe/src/xg_xe_glue.c'
s = p.read_text()
start = s.index('/* CONFIG_HMM_MIRROR is off:')
end = s.index('/* Match the shim notifier model:', start)
assert 'return -EOPNOTSUPP;' in s[start:end]
s = s[:start] + '#include "xg_xe_userptr.inc"\n\n' + s[end:]
s = s.replace(' * itself is rejected above; these do not enable unsupported HMM use. */',
              ' * holds physical pages until the VMA is destroyed. */')
p.write_text(s)
shutil.copy2(Path(__file__).with_name('xg_xe_userptr.inc'), p.parent / 'xg_xe_userptr.inc')
print('Applied opt-in Darwin Xe userptr wiring backend')
