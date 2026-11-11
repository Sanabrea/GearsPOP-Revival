"""Métodos que referencian un metadato IL2CPP (TypeInfo, MethodInfo o string) por nombre exacto.
Uso: il2cpp_metarefs.py <volcado> <so> "<nombre en ScriptMetadata/ScriptMetadataMethod>" ..."""
import sys, json, struct, bisect, array
sj = json.load(open(sys.argv[1] + '/script.json')); names = {m['Address']: m['Name'] for m in sj['ScriptMethod']}; ms = sorted(names)
meta = {}
for k in ('ScriptMetadata', 'ScriptMetadataMethod'):
    for m in sj.get(k, []): meta.setdefault(m['Name'], m['Address'])
for m in sj.get('ScriptString', []): meta.setdefault('"' + m['Value'] + '"', m['Address'])
d = open(sys.argv[2], 'rb').read()
shoff, = struct.unpack_from('<Q', d, 0x28); es, n = struct.unpack_from('<HH', d, 0x3a)
slots = {}
for k in range(n):
    _, t, _, _, o, sz = struct.unpack_from('<IIQQQQ', d, shoff + k * es)
    if t == 4:
        for j in range(0, sz, 24):
            ro, info, add = struct.unpack_from('<QQq', d, o + j)
            if info & 0xffffffff == 1027: slots.setdefault(add, []).append(ro)
w = array.array('I'); w.frombytes(d[:0x3200000])
for want in sys.argv[3:]:
    ma = meta.get(want)
    if ma is None: print("no encontrado:", want); continue
    cands = set(slots.get(ma, [])) | {ma}
    print(f"== {want} (casillas {[hex(c) for c in cands]})")
    hits = set()
    for i in range(0x100000 // 4, len(w)):
        x = w[i]
        if (x & 0xffc00000) != 0xf9400000: continue
        off = ((x >> 10) & 0xfff) * 8; rn = (x >> 5) & 31
        for c in cands:
            if c & 0xfff != off: continue
            for j in range(i - 1, max(i - 6, 0), -1):
                y = w[j]
                if (y & 0x9f000000) == 0x90000000 and (y & 31) == rn:
                    imm = ((y >> 29) & 3) | (((y >> 5) & 0x7ffff) << 2)
                    if imm & (1 << 20): imm -= 1 << 21
                    if ((j * 4) & ~0xfff) + (imm << 12) == c & ~0xfff:
                        k = bisect.bisect_right(ms, i * 4) - 1; hits.add(names[ms[k]])
                    break
    for h in sorted(hits): print("  ", h[:120])
