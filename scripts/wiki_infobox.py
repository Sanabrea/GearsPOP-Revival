import sys,os,re,csv,glob
pages=sorted(glob.glob(os.path.join(sys.argv[1],"w2022__*.txt")))
rows=[];keys=[]
for p in pages:
    t=open(p).read()
    m=re.search(r"\{\{\s*Gears[_ ]POP[^|]*\|(.*?)\}\}",t,re.S)
    if not m: continue
    d={}
    for part in m.group(1).split("|"):
        if "=" in part:
            k,v=part.split("=",1); k=k.strip(); v=v.strip()
            if k.startswith("image"): continue
            d[k]=v
            if k not in keys: keys.append(k)
    rows.append(d)
w=csv.DictWriter(open(sys.argv[2],"w",newline=""),fieldnames=keys); w.writeheader(); [w.writerow(r) for r in rows]
cols=["title1","role","rarity","power_cost","hit_points","damage","damage_per_second","attack_speed_(secs)","speed","range","target_type","damage_radius","capture_strength","units","skill"]
cols=[c for c in cols if c in keys]+[k for k in keys if k not in cols]
print(len(rows),"pins | campos:",keys)
print(" | ".join(c.replace("attack_speed_(secs)","atk_s").replace("damage_per_second","dps").replace("power_cost","cost").replace("hit_points","hp").replace("title1","pin") for c in cols))
for r in rows: print(" | ".join(r.get(c,"-") for c in cols))
