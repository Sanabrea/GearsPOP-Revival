import sys, json, re, subprocess, bisect
dump, so, start = sys.argv[1], sys.argv[2], int(sys.argv[3], 16)
sj = json.load(open(dump + '/script.json'))
meta = {m['Address']: m['Name'] for m in sj.get('ScriptMetadata', [])}
ms = sorted(m['Address'] for m in sj['ScriptMethod'])
i = bisect.bisect_right(ms, start) - 1
end = next(a for a in ms[i:] if a > start)
out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={start:#x}', f'--stop-address={end:#x}', so], capture_output=True, text=True).stdout
page = {}; regs = {}; lastmeta = None
for l in out.splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
    if not m: continue
    op, args = m.group(2), m.group(3)
    if op == 'adrp':
        r, a = re.match(r'(x\d+), (0x[0-9a-f]+)', args).groups(); page[r] = int(a, 16)
    elif op == 'ldr':
        mm = re.match(r'(x\d+), \[(x\d+), #(0x[0-9a-f]+|\d+)\]', args)
        if mm and mm.group(2) in page:
            a = page[mm.group(2)] + int(mm.group(3), 0)
            if a in meta: lastmeta = meta[a]
    mm = re.match(r'(w\d+|x\d+), #(-?0x[0-9a-f]+|-?\d+)', args)
    if op in ('mov', 'movz') and mm: regs[mm.group(1)[1:]] = int(mm.group(2), 0) & 0xffffffff
    elif op == 'movk' and mm:
        sh = re.search(r'lsl #(\d+)', args); s = int(sh.group(1)) if sh else 0
        r = mm.group(1)[1:]; regs[r] = (regs.get(r, 0) & ~(0xffff << s)) | (int(mm.group(2), 0) << s)
    elif op == 'orr' and re.match(r'w\d+, wzr, #', args):
        r, v = re.match(r'w(\d+), wzr, #(0x[0-9a-f]+|\d+)', args).groups(); regs[r] = int(v, 0)
    elif op == 'bl' and lastmeta is not None and m.group(1) and 'WriteFieldHeader' in str(regs):
        pass
    if op == 'bl':
        t = int(args.split()[0], 16)
        # WriteFieldHeader has w1 = WireType; printed with the last type checked
        if regs.get('1') in (2, 3) and regs.get('0', 0) > 2:
            print(f"{regs.get('0')}\t{regs.get('1')}\t{lastmeta}")
