"""Lists (field, wire type, next call) for each WriteFieldHeader in a generated Write function."""
import sys, json, re, subprocess, bisect
dump, so = sys.argv[1], sys.argv[2]
sj = json.load(open(dump + '/script.json'))
names = {m['Address']: m['Name'] for m in sj['ScriptMethod']}
ms = sorted(names)
WFH = [a for a, n in names.items() if n == 'ProtoBuf.ProtoWriter$$WriteFieldHeader'][0]
for arg in sys.argv[3:]:
    label, start = arg.split('=')[0], int(arg.split('=')[1], 16)
    i = bisect.bisect_right(ms, start) - 1; end = next(a for a in ms[i:] if a > start)
    out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={start:#x}', f'--stop-address={end:#x}', so], capture_output=True, text=True).stdout
    regs = {}; pend = None; res = []
    for l in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
        if not m: continue
        op, args = m.group(2), m.group(3)
        mm = re.match(r'w(\d+), #(0x[0-9a-f]+|\d+)', args)
        if op in ('mov', 'movz') and mm: regs[mm.group(1)] = int(mm.group(2), 0)
        elif op == 'movk' and mm:
            sh = re.search(r'lsl #(\d+)', args); regs[mm.group(1)] = regs.get(mm.group(1), 0) | (int(mm.group(2), 0) << int(sh.group(1) if sh else 0))
        elif op == 'orr' and re.match(r'w\d+, wzr, #', args):
            r, v = re.match(r'w(\d+), wzr, #(0x[0-9a-f]+|\d+)', args).groups(); regs[r] = int(v, 0)
        elif op == 'bl':
            t = int(args.split()[0], 16)
            if t == WFH: pend = (regs.get('0'), regs.get('1'))
            elif pend: res.append(f"{pend[0]}/{pend[1]} -> {names.get(t, hex(t)).replace('ProtoBuf.','')[:45]}"); pend = None
    print(f"== {label}: " + "; ".join(dict.fromkeys(res)))
