"""Variants to bisect which CMS group breaks the parser in a single session.
v0 and v7 = full CMS; v1..v6: the non-empty groups whose index has bit (v-1) set are emptied.
If the error disappears in the variants with bit b, bit b of the culprit's index is 1.
Usage: cms_bisect.py <cms.json> <output dir>  (writes cms_var_N.json and bisect_groups.txt)"""
import sys, json, os
d = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
groups = [g for g, v in d.items() if g != '_meta' and v]
with open(os.path.join(out, 'bisect_groups.txt'), 'w') as f:
    for i, g in enumerate(groups): f.write(f"{i}\t{g}\n")
for v in range(8):
    x = json.loads(json.dumps(d))
    if 1 <= v <= 6:
        for i, g in enumerate(groups):
            if i >> (v - 1) & 1: x[g] = []; x['_meta'][g] = {'total': 0}
    x['_meta']['_content_version'] = f'gprevival-bisect-{v}'
    json.dump(x, open(os.path.join(out, f'cms_var_{v}.json'), 'w'), separators=(',', ':'))
print(len(groups), 'non-empty groups ->', 8, 'variants')
