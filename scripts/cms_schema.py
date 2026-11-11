"""CMS schema from the dump: [CMSGroup] groups and [CMSField]/[CMSReference]/[CMSDefault]/... fields of each class.
The keys come from the C strings loaded by the attribute generators (IL2CPP v24).
Usage: cms_schema.py <dump.cs> <libil2cpp.so> <output.json>"""
import sys, re, struct, json
dump, so, outp = sys.argv[1:4]
d = open(so, 'rb').read()
L = open(dump, encoding='utf-8', errors='replace').read().splitlines()
def w(a): return struct.unpack_from('<I', d, a)[0]
def cstrings(a, maxn=24):
    out = []
    for k in range(maxn):
        x = w(a + 4 * k)
        if (x & 0x9f000000) == 0x90000000:
            rd = x & 31
            imm = ((x >> 29) & 3) | (((x >> 5) & 0x7ffff) << 2)
            page = ((a + 4 * k) & ~0xfff) + (imm << 12)
            y = w(a + 4 * k + 4)
            if (y & 0xffc00000) == 0x91000000 and (y & 31) == rd and ((y >> 5) & 31) == rd:
                p = page + ((y >> 10) & 0xfff)
                if p < len(d):
                    e = d.find(b'\0', p, p + 200)
                    if e > p:
                        try: out.append(d[p:e].decode('utf-8'))
                        except UnicodeDecodeError: pass
        if (x & 0xfc000000) == 0x14000000 or x == 0xd65f03c0: break   # b (tail) or ret
    return out
CMS_ATTRS = ('CMSField', 'CMSReference', 'CMSDefault', 'CMSOptional', 'CMSCollection', 'CMSArray', 'CMSDictionary', 'CMSEnum')
classes = {}; cur = None; pend = []
for i, l in enumerate(L):
    m = re.match(r'\[CMSGroup\] // RVA: 0x([0-9A-F]+)', l)
    if m:
        s = cstrings(int(m.group(1), 16)); pend_group = s[0] if s else None
        continue
    m = re.match(r'(public|internal)[a-z ]* class ([A-Za-z0-9_.]+)(?: : ([A-Za-z0-9_.<>, ]+))? // TypeDefIndex', l)
    if m:
        grp = None
        if any(L[k].startswith('[CMSGroup]') for k in range(max(0, i - 4), i)): grp = pend_group
        cur = {'class': m.group(2), 'base': m.group(3), 'group': grp, 'fields': []}
        prev = classes.get(m.group(2))
        if prev is not None and (prev['group'] or prev['fields']):
            classes[m.group(2) + '#' + str(i)] = cur   # same name in another namespace: does not overwrite the CMS one
        else:
            classes[m.group(2)] = cur
        pend = []; continue
    m = re.match(r'\s*\[(CMS[A-Za-z]+)\] // RVA: 0x([0-9A-F]+)', l)
    if m and cur is not None:
        pend.append((m.group(1), cstrings(int(m.group(2), 16)))); continue
    m = re.match(r'\s*public ([A-Za-z0-9_.<>\[\], ]+) ([A-Za-z0-9_]+) \{ get', l) or re.match(r'\s*public (?!const |static )([A-Za-z0-9_.<>\[\], ]+) ([A-Za-z0-9_]+); // 0x', l)
    if m and cur is not None and pend:
        for attr, strs in pend:
            cur['fields'].append({'prop': m.group(2), 'type': m.group(1), 'attr': attr, 'keys': strs})
        pend = []; continue
    if l.strip().startswith('public') and '(' in l: pend = []
schema = {}
for k, v in classes.items():
    if not (v['group'] or v['fields']): continue
    base = k.split('#')[0]
    if base not in schema or (v['group'] and not schema[base]['group']): schema[base] = v
    elif k != base: schema[k] = v
json.dump(schema, open(outp, 'w'), indent=1, ensure_ascii=False)
g = [v for v in schema.values() if v['group']]
print(len(schema), 'classes with CMS data;', len(g), 'groups;', sum(len(v['fields']) for v in schema.values()), 'fields')
