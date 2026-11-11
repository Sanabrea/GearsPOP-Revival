import json,re,sys; sj=json.load(open(sys.argv[1]))
pat=re.compile(sys.argv[2])
for m in sj['ScriptMethod']:
    if pat.search(m['Name']): print(hex(m['Address']), m['Name'])
