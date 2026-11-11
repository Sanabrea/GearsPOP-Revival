"""Compare the Pocket Gamer 2019 CSV with the 2019 Gears POP! wiki stats and list pins
with no stats in any source (roster from depressifier). Offline. Usage: pins_compare.py
"""
import csv,re,sys,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW=os.path.join(ROOT,"data","raw_sources")
def norm(n):
    n=n.lower().strip()
    alias={"baird":"damon baird","shepherd":"shepherds","shocker barrier":"shock barrier","stun grenades":"stun grenade","power genertor":"power generator"}
    return alias.get(n,n)
pg={norm(r["pin"]):r for r in csv.DictReader(open(os.path.join(RAW,"pocketgamer_2019_pin_stats.csv")))}
wk={norm(r["title1"]):r for r in csv.DictReader(open(os.path.join(RAW,"gearspop_wiki_stats_2019.csv"))) if r.get("hit_points")}
clj=open(os.path.join(ROOT,"sources","github","Jschii_gears-pop-depressifier_data.cljs")).read()
rar={norm(n):r for n,r in re.findall(r'\{:name "([^"]+)" :rarity :(\w+)\}',clj)}
print(f"Your CSV: {len(pg)} pins | wiki: {len(wk)} pins | full list (depressifier): {len(rar)} pins")
print("\n== Pins in both (your CSV vs wiki): differences")
for k in sorted(set(pg)&set(wk)):
    a,b=pg[k],wk[k]; diffs=[]
    for fa,fb in [("hp","hit_points"),("damage","damage"),("dps","damage_per_second"),("range","range"),("target","target_type"),("energy_cost","power_cost")]:
        va,vb=(a.get(fa) or "").strip(),(b.get(fb) or "").strip()
        if va and vb and va.lower()!=vb.lower(): diffs.append(f"{fa}: yours={va} wiki={vb}")
    print(f"  {k:18s}", "; ".join(diffs) if diffs else "same")
print("\n== Names with no known rarity:",[k for k in set(pg)|set(wk) if k not in rar])
print("== Pins from the full list with NO stats in any source:")
print("  ",sorted(k for k in rar if k not in pg and k not in wk))
