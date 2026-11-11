"""Quién llama (BL/B directo) a una dirección en libil2cpp.so arm64. Uso: il2cpp_xrefs.py <volcado> <so> <RVA hex>..."""
import sys, json, struct, bisect
sj = json.load(open(sys.argv[1] + '/script.json')); names = {m['Address']: m['Name'] for m in sj['ScriptMethod']}; ms = sorted(names)
d = open(sys.argv[2], 'rb').read()
targets = [int(x, 16) for x in sys.argv[3:]]
import array
w = array.array('I'); w.frombytes(d[:len(d) // 4 * 4])
for t in targets:
    print(f"== llamadas a {names.get(t, hex(t))}")
    for i in range(0x100000 // 4, min(len(w), 0x3200000 // 4)):
        x = w[i]
        if (x & 0xfc000000) in (0x94000000, 0x14000000):
            off = x & 0x3ffffff
            if off & 0x2000000: off -= 0x4000000
            if i * 4 + off * 4 == t:
                k = bisect.bisect_right(ms, i * 4) - 1
                print(f"   {i*4:#x} en {names[ms[k]][:110]}")
