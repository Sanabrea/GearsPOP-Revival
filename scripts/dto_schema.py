"""Protobuf schema of the gateway DTOs, taken from GeneratedProtoSerializer.Write(T) (field numbers and getter)
and from each class's properties in dump.cs (types).
Module usage: Schema(dump_dir, libil2cpp).fields('AllPlayerDataDto') -> [(num, prop, type, call)]"""
import json, re, subprocess, bisect


class Schema:
    def __init__(self, dump_dir, so):
        self.so = so
        sj = json.load(open(dump_dir + '/script.json'))
        self.names = {m['Address']: m['Name'] for m in sj['ScriptMethod']}
        self.ms = sorted(self.names)
        L = open(dump_dir + '/dump.cs', encoding='utf-8', errors='replace').read().splitlines()
        self.writers, self.props, self.enums, cur = {}, {}, set(), None
        for i, l in enumerate(L):
            m = re.match(r'\s*private static void Write\(([^,]+) , ProtoWriter \) \{ \}', l)
            if m and i > 0:
                r = re.search(r'RVA: 0x([0-9A-F]+)', L[i - 1])
                if r: self.writers.setdefault(m.group(1).strip(), int(r.group(1), 16))
            m = re.match(r'(?:public|internal)[a-z ]* (class|struct|enum) ([A-Za-z0-9_.]+)', l)
            if m:
                cur = m.group(2)
                if m.group(1) == 'enum': self.enums.add(cur)
                self.props.setdefault(cur, {})
                continue
            m = re.match(r'\s*public ([A-Za-z0-9_.<>\[\], ]+) ([A-Za-z0-9_]+) \{ get', l)
            if m and cur: self.props[cur].setdefault(m.group(2), m.group(1))
        self.cache = {}

    def fields(self, cls):
        if cls in self.cache: return self.cache[cls]
        a = self.writers.get(cls)
        if a is None: self.cache[cls] = None; return None
        b = self.ms[bisect.bisect_right(self.ms, a)]
        out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', f'--start-address={a:#x}', f'--stop-address={b:#x}', self.so],
                             capture_output=True, text=True).stdout
        res, w0, getter, pend = [], None, None, None
        for l in out.splitlines():
            m = re.search(r'(?:mov|orr)\tw0, (?:wzr, )?#(0x[0-9a-f]+|\d+)', l)
            if m: w0 = int(m.group(1), 0)
            m = re.search(r'\tbl\t(0x[0-9a-f]+)', l)
            if not m: continue
            n = self.names.get(int(m.group(1), 16), '').split('$$')[-1]
            if n.startswith('get_'): getter = n[4:]
            elif n == 'WriteFieldHeader': pend = (w0, getter)
            elif pend and n:
                num, prop = pend; pend = None
                t = self.props.get(cls, {}).get(prop, '?')
                if not any(r[0] == num for r in res): res.append((num, prop, t, n))
        self.cache[cls] = res
        return res
