"""Cross-check data/gears_pop_pin_upgrade_costs.csv and data/gears_pop_player_level_xp.csv
against the depressifier source (sources/github). Offline. Usage: crosscheck.py
"""
import csv,re,sys,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,"data")
clj=open(os.path.join(ROOT,"sources","github","Jschii_gears-pop-depressifier_data.cljs")).read()
# --- upgrade costs
costs={}
block=clj[clj.index("(def costs"):clj.index("(def xps")]
parts=re.split(r":(common|rare|epic|legendary)\s",block)
for i in range(1,len(parts),2):
    costs[parts[i]]=[tuple(map(int,m)) for m in re.findall(r"\(cost\. (\d+) (\d+) (\d+)\)",parts[i+1])]
xps=list(map(int,re.search(r"\(def xps \[(.*?)\]\)",clj).group(1).split()))
bad=0;n=0
for r in csv.DictReader(open(os.path.join(DATA,"gears_pop_pin_upgrade_costs.csv"))):
    rar=r["rarity"].lower(); lvl=int(r["pin_level"]); n+=1
    ref=costs[rar][lvl-2]
    mine=(int(r["duplicate_pins_required"]),int(r["coin_cost"]),int(r["xp_gained"]))
    if mine!=ref: bad+=1; print("  COST MISMATCH",rar,lvl,"yours",mine,"depressifier",ref)
print(f"Upgrade costs: {n} rows, {bad} mismatches | max levels: "+", ".join(f"{k}={len(v)+1}" for k,v in costs.items()))
bad=0;n=0
for r in csv.DictReader(open(os.path.join(DATA,"gears_pop_player_level_xp.csv"))):
    lvl=int(r["player_level"]); n+=1
    if int(r["xp_required_for_level"])!=xps[lvl-2]: bad+=1; print("  XP MISMATCH",lvl)
print(f"Player XP: {n} rows, {bad} mismatches (depressifier has {len(xps)} levels)")
