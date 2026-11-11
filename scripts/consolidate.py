"""Build the first consolidated pin table (format of data/raw_sources/gears_pop_pins_consolidated.csv).

Merges the depressifier roster (rarity), the Pocket Gamer 2019 CSV, the 2019 Gears POP! wiki
infoboxes and the GoW wiki roles. Offline. Usage: consolidate.py OUT_CSV
"""
import csv,re,sys,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW=os.path.join(ROOT,"data","raw_sources")
CLJ=os.path.join(ROOT,"sources","github","Jschii_gears-pop-depressifier_data.cljs")
OUT=sys.argv[1]
alias={"baird":"damon baird","shepherd":"shepherds","shocker barrier":"shock barrier","stun grenades":"stun grenade","power genertor":"power generator","e-hole":"emergence hole"}
norm=lambda n: alias.get(n.lower().strip(),n.lower().strip())
clj=open(CLJ).read()
roster=[(norm(n),r) for n,r in re.findall(r'\{:name "([^"]+)" :rarity :(\w+)\}',clj)]
pg={norm(r["pin"]):r for r in csv.DictReader(open(os.path.join(RAW,"pocketgamer_2019_pin_stats.csv")))}
wk={norm(r["title1"]):r for r in csv.DictReader(open(os.path.join(RAW,"gearspop_wiki_stats_2019.csv"))) if r.get("hit_points")}
roles={}
for line in open(os.path.join(RAW,"gow_wiki_roles.txt")):
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
    r["rarity"]=rar.capitalize(); r["role"]=ro[0] or w.get("role",""); r["type"]=ro[1]; r["added"]={"launch":"launch","gears5":"Gears 5 event","update1":"update 1","update2":"update 2"}.get(ro[2],"later / no data")
    src=["depressifier (rarity)"]
    if ro[0]: src.append("GoW Wiki (role/type)")
    r["energy_cost"]=p.get("energy_cost") or w.get("power_cost","")
    r["hp"]=p.get("hp") or w.get("hit_points",""); r["damage"]=p.get("damage") or w.get("damage","")
    r["dps"]=p.get("dps") or w.get("damage_per_second",""); r["range"]=p.get("range") or w.get("range","")
    r["target"]=p.get("target") or w.get("target_type","")
    if p: src.append("Pocket Gamer 2019 (your CSV)")
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
            r["extra"]=(r["extra"]+"; " if r["extra"] else "")+f"effect duration ≈ {dmg/dps:.1f} s (derived damage/DPS)"
        else:
            r["attack_interval_s"]=f"{dmg/dps:.2f}"; r["attack_interval_origin"]="derived (damage/DPS)"
    if p and w and p.get("range") and w.get("range") and p["range"]!=w["range"]:
        notes.append(f"range conflict: Pocket Gamer={p['range']}, wiki={w['range']}"); r["range"]=f"{w['range']}?"
    if n=="kait diaz": notes.append("target 'Fortifications & Objectives' unconfirmed (Pocket Gamer table with mixed-up rows)")
    if not (p or w): notes.append("NO STATS in any source")
    r["sources"]=" + ".join(src); r["notes"]="; ".join(notes)
    rows.append(r)
w=csv.DictWriter(open(OUT,"w",newline=""),fieldnames=cols); w.writeheader(); w.writerows(rows)
have=sum(1 for r in rows if r["hp"] or r["damage"])
print(f"{len(rows)} pins | with stats: {have} | with role/type: {sum(1 for r in rows if r['role'])} | with speed: {sum(1 for r in rows if r['speed'])} | with attack rate: {sum(1 for r in rows if r['attack_interval_s'])}")
print("without role/type:",[r["pin"] for r in rows if not r["role"]])
