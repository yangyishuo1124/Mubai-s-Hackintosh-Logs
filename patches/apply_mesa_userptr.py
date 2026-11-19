from pathlib import Path
import sys

p = Path(sys.argv[1]) / 'src/intel/dev/xe/intel_device_info.c'
s = p.read_text()
anchor = '   devinfo->has_userptr_uapi = true;'
assert s.count(anchor) == 1
s = s.replace('#include "util/log.h"', '#include "util/log.h"\n#include "util/u_debug.h"')
s = s.replace(anchor, '''#ifdef __APPLE__
   /* Enable only while testing with the matching opt-in XeGfx userptr kernel.
    * Ordinary BO paths continue to work when the extension is disabled. */
   devinfo->has_userptr_uapi = debug_get_bool_option("ANV_XE_USERPTR", false);
#else
   devinfo->has_userptr_uapi = true;
#endif''')
p.write_text(s)
print('Applied opt-in Darwin ANV host-pointer capability')
