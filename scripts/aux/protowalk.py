import sys, json, re, subprocess, bisect
dump, so, start = sys.argv[1], sys.argv[2], int(sys.argv[3], 16)
sj = json.load(open(dump + '/script.json'))
ms = sorted((m['Address'], m.get('Signature') or m['Name']) for m in sj['ScriptMethod'])
addrs = [a for a, _ in ms]
i = bisect.bisect_right(addrs, start) - 1
end = next(a for a in addrs[i:] if a > start)
names = dict(ms)
out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={start:#x}', f'--stop-address={end:#x}', so], capture_output=True, text=True).stdout
regs = {}
for l in out.splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
    if not m: continue
    op, args = m.group(2), m.group(3)
    mm = re.match(r'(w\d+|x\d+), #(-?0x[0-9a-f]+|-?\d+)', args)
    if op in ('mov', 'movz') and mm:
        regs[mm.group(1)[1:]] = int(mm.group(2), 0) & 0xffffffff
    elif op == 'movk' and mm:
        sh = re.search(r'lsl #(\d+)', args); s = int(sh.group(1)) if sh else 0
        r = mm.group(1)[1:]; regs[r] = (regs.get(r, 0) & ~(0xffff << s)) | (int(mm.group(2), 0) << s)
    elif op == 'orr' and re.match(r'w\d+, wzr, #', args):
        r, v = re.match(r'w(\d+), wzr, #(0x[0-9a-f]+|\d+)', args).groups(); regs[r] = int(v, 0)
    elif op == 'bl':
        t = int(args.split()[0], 16)
        n = names.get(t, hex(t))
        if 'WriteFieldHeader' in n: tag = regs.get('0')
        elif 'GeneratedProtoSerializer__Write' in n or 'Write (' in n or n.startswith('void GeneratedProtoSerializer'):
            t2 = re.search(r'Write \(([A-Za-z0-9_.]+)', n)
            print(f"{tag}\t{t2.group(1) if t2 else n[:80]}")
