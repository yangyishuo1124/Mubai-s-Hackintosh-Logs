from pathlib import Path
import sys

p=Path(sys.argv[1])/'plugin/NVMTLObjects.m'
s=p.read_text()
anchor='&& strcmp(key, "INTEL_DEBUG")) continue;'
assert s.count(anchor)==1
s=s.replace(anchor,'&& strcmp(key, "INTEL_DEBUG") && strcmp(key, "ANV_XE_USERPTR")) continue;')
p.write_text(s)
print('Allowed the specific ANV host-import switch in the plugin configuration')
