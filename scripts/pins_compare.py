import csv,re,sys,os
D=sys.argv[1]
def norm(n):
    n=n.lower().strip()
    alias={"baird":"damon baird","shepherd":"shepherds","shocker barrier":"shock barrier","stun grenades":"stun grenade","power genertor":"power generator"}
    return alias.get(n,n)
pg={norm(r["pin"]):r for r in csv.DictReader(open(os.path.join(D,"gears_pop_pin_stats.csv")))}
wk={norm(r["title1"]):r for r in csv.DictReader(open(os.path.join(D,"gearspop_wiki_stats_2019.csv"))) if r.get("hit_points")}
clj=open(os.path.join(D,"depressifier_data.cljs")).read()
rar={norm(n):r for n,r in re.findall(r'\{:name "([^"]+)" :rarity :(\w+)\}',clj)}
print(f"Tu CSV: {len(pg)} pins | wiki: {len(wk)} pins | lista completa (depressifier): {len(rar)} pins")
print("\n== Pins en ambos (tu CSV vs wiki): diferencias")
for k in sorted(set(pg)&set(wk)):
    a,b=pg[k],wk[k]; diffs=[]
    for fa,fb in [("hp","hit_points"),("damage","damage"),("dps","damage_per_second"),("range","range"),("target","target_type"),("energy_cost","power_cost")]:
        va,vb=(a.get(fa) or "").strip(),(b.get(fb) or "").strip()
        if va and vb and va.lower()!=vb.lower(): diffs.append(f"{fa}: tuyo={va} wiki={vb}")
    print(f"  {k:18s}", "; ".join(diffs) if diffs else "igual")
print("\n== Nombres sin rareza conocida:",[k for k in set(pg)|set(wk) if k not in rar])
print("== Pins de la lista completa SIN stats en ninguna fuente:")
print("  ",sorted(k for k in rar if k not in pg and k not in wk))
