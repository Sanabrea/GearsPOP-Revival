"""ProtoInclude tags of a GeneratedProtoSerializer.Write(T): tag -> class."""
import sys, json, re, subprocess, bisect
dump, so, start = sys.argv[1], sys.argv[2], int(sys.argv[3], 16)
sj = json.load(open(dump + '/script.json'))
meta0 = {m['Address']: m['Name'] for m in sj['ScriptMetadata']}
import struct
d = open(so, 'rb').read()
shoff, = struct.unpack_from('<Q', d, 0x28); shentsize, shnum = struct.unpack_from('<HH', d, 0x3a)
rel = {}
for k in range(shnum):
    name, typ, flags, addr, off, size = struct.unpack_from('<IIQQQQ', d, shoff + k * shentsize)
    if typ == 4:  # SHT_RELA
        for j in range(0, size, 24):
            ro, info, add = struct.unpack_from('<QQq', d, off + j)
            if info & 0xffffffff == 1027: rel[ro] = add   # R_AARCH64_RELATIVE
meta = {a: meta0[v] for a, v in rel.items() if v in meta0}
ms = sorted(m['Address'] for m in sj['ScriptMethod'])
i = bisect.bisect_right(ms, start) - 1
end = next(a for a in ms[i:] if a > start)
out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={start:#x}', f'--stop-address={end:#x}', so], capture_output=True, text=True).stdout
ins = []
for l in out.splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
    if m: ins.append((int(m.group(1), 16), m.group(2), m.group(3)))
def imm(op, args, regs):
    mm = re.match(r'(w\d+|x\d+), #(-?0x[0-9a-f]+|-?\d+)', args)
    if op in ('mov', 'movz') and mm: regs[mm.group(1)[1:]] = int(mm.group(2), 0) & 0xffffffff; return mm.group(1)[1:]
    if op == 'movk' and mm:
        sh = re.search(r'lsl #(\d+)', args); s_ = int(sh.group(1)) if sh else 0
        r = mm.group(1)[1:]; regs[r] = (regs.get(r, 0) & ~(0xffff << s_)) | (int(mm.group(2), 0) << s_); return r
    mm = re.match(r'w(\d+), wzr, #(0x[0-9a-f]+|\d+)', args)
    if op == 'orr' and mm: regs[mm.group(1)] = int(mm.group(2), 0); return mm.group(1)
    mm = re.match(r'w(\d+), w(\d+)$', args)
    if op == 'mov' and mm: regs[mm.group(1)] = regs.get(mm.group(2)); return mm.group(1)
page = {}; cur = None; target = {}; regs = {}; t21 = None
for a, op, args in ins:
    r = imm(op, args, regs)
    if r == '21': t21 = regs['21']
    if op == 'adrp':
        rr, v = re.match(r'(x\d+), (0x[0-9a-f]+)', args).groups(); page[rr] = int(v, 16)
    elif op == 'ldr':
        mm = re.match(r'(x\d+), \[(x\d+), #(0x[0-9a-f]+|\d+)\]', args)
        if mm and mm.group(2) in page and (page[mm.group(2)] + int(mm.group(3), 0)) in meta:
            cur = meta[page[mm.group(2)] + int(mm.group(3), 0)]
    elif op == 'b.eq' and cur:
        target[int(args.split()[0], 16)] = (cur, t21); t21 = None; cur = None
seen = set()
regs = {}; block = None
for a, op, args in ins:
    if a in target: block = target[a]; regs = {}
    imm(op, args, regs)
    if op == 'bl' and int(args.split()[0], 16) == 0x252155c and block and block[0] not in seen:
        tag = regs.get('0') if regs.get('0') is not None else block[1]
        seen.add(block[0]); print(f"{tag}\t{block[0]}")
