"""CMS group name of each [CMSGroup] class: reads the C string the attribute generator passes to CMSGroup..ctor.
Usage: cms_groups.py <dump.cs> <libil2cpp.so>  -> TSV: group, class"""
import sys, re, struct
dump, so = sys.argv[1], sys.argv[2]
d = open(so, 'rb').read()
lines = open(dump, encoding='utf-8', errors='replace').read().splitlines()
def word(a): return struct.unpack_from('<I', d, a)[0]
for i, l in enumerate(lines):
    m = re.match(r'\[CMSGroup\] // RVA: 0x([0-9A-F]+)', l)
    if not m: continue
    cls = None
    for j in range(i + 1, i + 4):
        mm = re.search(r'class ([A-Za-z0-9_.]+)', lines[j])
        if mm: cls = mm.group(1); break
    a = int(m.group(1), 16); name = None
    for k in range(0, 12):
        x = word(a + 4 * k)
        if (x & 0x9f00001f) == 0x90000000:            # adrp x0
            imm = ((x >> 29) & 3) | (((x >> 5) & 0x7ffff) << 2)
            page = ((a + 4 * k) & ~0xfff) + (imm << 12)
            y = word(a + 4 * k + 4)
            if (y & 0xffc003ff) == 0x91000000:        # add x0, x0, #imm
                p = page + ((y >> 10) & 0xfff)
                name = d[p:d.index(b'\0', p)].decode('utf-8', 'replace')
            break
    print(f"{name}\t{cls}")
