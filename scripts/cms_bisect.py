"""Variantes para bisectar qué grupo del CMS rompe el parser en una sola sesión.
v0 y v7 = CMS completo; v1..v6: se vacían los grupos con datos cuyo índice tiene el bit (v-1) encendido.
Si el error desaparece en las variantes con bit b, el bit b del índice del culpable es 1.
Uso: cms_bisect.py <cms.json> <carpeta salida>  (escribe cms_var_N.json y bisect_grupos.txt)"""
import sys, json, os
d = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
groups = [g for g, v in d.items() if g != '_meta' and v]
with open(os.path.join(out, 'bisect_grupos.txt'), 'w') as f:
    for i, g in enumerate(groups): f.write(f"{i}\t{g}\n")
for v in range(8):
    x = json.loads(json.dumps(d))
    if 1 <= v <= 6:
        for i, g in enumerate(groups):
            if i >> (v - 1) & 1: x[g] = []; x['_meta'][g] = {'total': 0}
    x['_meta']['_content_version'] = f'gprevival-bisect-{v}'
    json.dump(x, open(os.path.join(out, f'cms_var_{v}.json'), 'w'), separators=(',', ':'))
print(len(groups), 'grupos con datos ->', 8, 'variantes')
