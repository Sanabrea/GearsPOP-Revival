import csv,re,sys,os
D=sys.argv[1]
clj=open(os.path.join(D,"depressifier_data.cljs")).read()
# --- costs
costs={}
block=clj[clj.index("(def costs"):clj.index("(def xps")]
parts=re.split(r":(common|rare|epic|legendary)\s",block)
for i in range(1,len(parts),2):
    costs[parts[i]]=[tuple(map(int,m)) for m in re.findall(r"\(cost\. (\d+) (\d+) (\d+)\)",parts[i+1])]
xps=list(map(int,re.search(r"\(def xps \[(.*?)\]\)",clj).group(1).split()))
bad=0;n=0
for r in csv.DictReader(open(os.path.join(D,"gears_pop_pin_upgrade_costs.csv"))):
    rar=r["rarity"].lower(); lvl=int(r["pin_level"]); n+=1
    ref=costs[rar][lvl-2]
    mine=(int(r["duplicate_pins_required"]),int(r["coin_cost"]),int(r["xp_gained"]))
    if mine!=ref: bad+=1; print("  COSTO DIFERENTE",rar,lvl,"tuyo",mine,"depressifier",ref)
print(f"Costos de mejora: {n} filas, {bad} diferencias | niveles max: "+", ".join(f"{k}={len(v)+1}" for k,v in costs.items()))
bad=0;n=0
for r in csv.DictReader(open(os.path.join(D,"gears_pop_player_level_xp.csv"))):
    lvl=int(r["player_level"]); n+=1
    if int(r["xp_required_for_level"])!=xps[lvl-2]: bad+=1; print("  XP DIFERENTE",lvl)
print(f"XP de jugador: {n} filas, {bad} diferencias (depressifier tiene {len(xps)} niveles)")
