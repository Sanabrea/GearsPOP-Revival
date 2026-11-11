"""Minimal pseudo-decompilation of IL2CPP arm64 methods: calls, strings and referenced types, in order.
Usage: python3 -I il2cpp_calls.py <dump dir> <libil2cpp.so> <RVA hex> [<RVA hex> ...]"""
import sys, json, re, subprocess, bisect, struct
dump, so = sys.argv[1], sys.argv[2]
sj = json.load(open(dump + '/script.json'))
names = {m['Address']: m['Name'] for m in sj['ScriptMethod']}
ms = sorted(names)
lits = {m['Address']: ('"' + m['Value'][:60] + '"') for m in sj['ScriptString']}
lits.update({m['Address']: m['Name'][:70] for m in sj['ScriptMetadata']})
lits.update({m['Address']: 'm:' + m['Name'][:70] for m in sj.get('ScriptMetadataMethod', [])})
d = open(so, 'rb').read()
shoff, = struct.unpack_from('<Q', d, 0x28); es, n = struct.unpack_from('<HH', d, 0x3a)
rel = {}
for k in range(n):
    _, t, _, _, o, sz = struct.unpack_from('<IIQQQQ', d, shoff + k * es)
    if t == 4:
        for j in range(0, sz, 24):
            ro, info, add = struct.unpack_from('<QQq', d, o + j)
            if info & 0xffffffff == 1027: rel[ro] = add
for arg in sys.argv[3:]:
    a = int(arg, 16); i = bisect.bisect_right(ms, a) - 1; b = next(x for x in ms[i:] if x > a)
    print(f"== {names.get(a, hex(a))} ({a:#x}-{b:#x})")
    out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={a:#x}', f'--stop-address={b:#x}', so], capture_output=True, text=True).stdout
    page = {}; last = None
    for l in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
        if not m: continue
        op, args = m.group(2), m.group(3)
        if op == 'adrp':
            r, v = re.match(r'(x\d+), (0x[0-9a-f]+)', args).groups(); page[r] = int(v, 16)
        elif op in ('ldr', 'add'):
            mm = re.match(r'(x\d+), \[?(x\d+), #(0x[0-9a-f]+|\d+)', args)
            if mm and mm.group(2) in page:
                ad = page[mm.group(2)] + int(mm.group(3), 0)
                tgt = rel.get(ad, ad)
                s = lits.get(tgt) or lits.get(ad)
                if s and s != last: print('   ', s); last = s
        elif op == 'bl':
            t = int(args.split()[0], 16); nm = names.get(t)
            if nm: print('    ->', nm[:90])
        elif op in ('b',) and args.startswith('0x'):
            t = int(args.split()[0], 16)
            if t in names and not (a <= t < b): print('    => (jump)', names[t][:90])
