import csv,re,sys,os
D=sys.argv[1]; OUT=sys.argv[2]
alias={"baird":"damon baird","shepherd":"shepherds","shocker barrier":"shock barrier","stun grenades":"stun grenade","power genertor":"power generator","e-hole":"emergence hole"}
norm=lambda n: alias.get(n.lower().strip(),n.lower().strip())
clj=open(os.path.join(D,"depressifier_data.cljs")).read()
roster=[(norm(n),r) for n,r in re.findall(r'\{:name "([^"]+)" :rarity :(\w+)\}',clj)]
pg={norm(r["pin"]):r for r in csv.DictReader(open(os.path.join(D,"gears_pop_pin_stats.csv")))}
wk={norm(r["title1"]):r for r in csv.DictReader(open(os.path.join(D,"gearspop_wiki_stats_2019.csv"))) if r.get("hit_points")}
roles={}
for line in open(os.path.join(D,"gow_wiki_roles.txt")):
    if line.startswith("#") or not line.strip(): continue
    n,ro,ty,g=line.strip().split("|"); roles[n]=(ro,ty,g)
cols=["pin","rarity","role","type","added","energy_cost","hp","damage","dps","attack_interval_s","attack_interval_origin","speed","range","target","damage_radius","capture_strength","troops","skill","extra","sources","notes"]
rows=[]
def num(x):
    try: return float(x)
    except: return None
for n,rar in roster:
    p=pg.get(n,{}); w=wk.get(n,{}); ro=roles.get(n,("","",""))
    r={c:"" for c in cols}
    r["pin"]=n.title().replace("Dr-1","DR-1").replace("Jd ","JD ").replace("Raam","RAAM")
    r["rarity"]=rar.capitalize(); r["role"]=ro[0] or w.get("role",""); r["type"]=ro[1]; r["added"]={"launch":"lanzamiento","gears5":"evento Gears 5","update1":"actualización 1","update2":"actualización 2"}.get(ro[2],"posterior / sin dato")
    src=["depressifier (rareza)"]
    if ro[0]: src.append("GoW Wiki (rol/tipo)")
    r["energy_cost"]=p.get("energy_cost") or w.get("power_cost","")
    r["hp"]=p.get("hp") or w.get("hit_points",""); r["damage"]=p.get("damage") or w.get("damage","")
    r["dps"]=p.get("dps") or w.get("damage_per_second",""); r["range"]=p.get("range") or w.get("range","")
    r["target"]=p.get("target") or w.get("target_type","")
    if p: src.append("Pocket Gamer 2019 (tu CSV)")
    if w:
        src.append("Gears PoP! Wiki 2019")
        r["speed"]=w.get("speed",""); r["damage_radius"]=w.get("damage_radius",""); r["capture_strength"]=w.get("capture_strength","")
        r["troops"]=w.get("number_of_troops",""); r["skill"]=w.get("skill","")
        ex=[f"{k}={w[k]}" for k in ("mantle_kicks","objectives_damage","stun_radius","stun_duration_(secs)") if w.get(k)]
        r["extra"]="; ".join(ex)
        if w.get("attack_speed_(secs)"): r["attack_interval_s"]=w["attack_speed_(secs)"]; r["attack_interval_origin"]="wiki"
    notes=[]
    dmg,dps=num(r["damage"]),num(r["dps"])
    if not r["attack_interval_s"] and dmg and dps:
        if r["type"]=="Projectile":
            r["extra"]=(r["extra"]+"; " if r["extra"] else "")+f"duración del efecto ≈ {dmg/dps:.1f} s (derivado daño/DPS)"
        else:
            r["attack_interval_s"]=f"{dmg/dps:.2f}"; r["attack_interval_origin"]="derivado (daño/DPS)"
    if p and w and p.get("range") and w.get("range") and p["range"]!=w["range"]:
        notes.append(f"alcance en conflicto: Pocket Gamer={p['range']}, wiki={w['range']}"); r["range"]=f"{w['range']}?"
    if n=="kait diaz": notes.append("objetivo 'Fortifications & Objectives' sin confirmar (tabla de Pocket Gamer con filas mezcladas)")
    if not (p or w): notes.append("SIN STATS en ninguna fuente")
    r["sources"]=" + ".join(src); r["notes"]="; ".join(notes)
    rows.append(r)
w=csv.DictWriter(open(OUT,"w",newline=""),fieldnames=cols); w.writeheader(); w.writerows(rows)
have=sum(1 for r in rows if r["hp"] or r["damage"])
print(f"{len(rows)} pins | con stats: {have} | con rol/tipo: {sum(1 for r in rows if r['role'])} | con velocidad: {sum(1 for r in rows if r['speed'])} | con cadencia: {sum(1 for r in rows if r['attack_interval_s'])}")
print("sin rol/tipo:",[r["pin"] for r in rows if not r["role"]])
