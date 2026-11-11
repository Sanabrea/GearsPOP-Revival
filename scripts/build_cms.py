"""Arma el CMS que sirve el servidor embebido (formato Gamefuel: {grupo: [items con "id"], "_meta": {...}}).
Paso 2: items completos. Cada campo [CMSField] lleva un valor por defecto según su tipo; las referencias apuntan a un item
"gp_default" del grupo destino (que se crea y se llena igual); los campos con [CMSDefault] se omiten.
Uso: python3 -I build_cms.py <cms_schema.json> <cms_singletons.json> <dump.cs> <salida.json>"""
import sys, json, re
schema = json.load(open(sys.argv[1])); singles = json.load(open(sys.argv[2]))
dump = open(sys.argv[3], encoding='utf-8', errors='replace').read().splitlines()
enums = {}
for i, l in enumerate(dump):
    m = re.match(r'public enum ([A-Za-z0-9_.]+) ', l)
    if m:
        for j in range(i + 1, i + 60):
            c = re.match(r'\s*public const [A-Za-z0-9_.]+ ([A-Za-z0-9_]+) = (-?\d+);', dump[j])
            if c: enums[m.group(1)] = c.group(1); break
            if dump[j].startswith('}'): break
by_class = {v['class']: v for v in schema.values()}
group_of = {v['class']: v['group'] for v in schema.values() if v.get('group')}
groups = {v['group']: [] for v in schema.values() if v.get('group')}
DEFAULT_ID = 'gp_default'
def fields_of(cls, seen=None):
    seen = seen or set(); out = {}
    c = by_class.get(cls)
    if not c or cls in seen: return out
    seen.add(cls)
    base = (c.get('base') or '').split(',')[0].strip()
    if base in by_class: out.update(fields_of(base, seen))
    for f in c['fields']:
        e = out.setdefault(f['prop'], {'type': f['type'], 'attrs': set(), 'key': None})
        e['attrs'].add(f['attr'])
        if f['keys'] and not e['key']: e['key'] = f['keys'][0]
    return out
def ensure_default(g):
    if not any(x['id'] == DEFAULT_ID for x in groups[g]):
        item = {'id': DEFAULT_ID}; groups[g].append(item)
        cls = next(k for k, v in group_of.items() if v == g)
        fill(item, cls, set())
    return DEFAULT_ID
def value_for(t, stack):
    if t.endswith('[]') or t.startswith(('List<', 'HashSet<')): return []
    if t.startswith('Dictionary<'): return []   # Parsing usa ParseListToDictionary: en el JSON es una lista de items con id
    if t == 'Fix': return '0'          # Parsing.ParseFixed lee texto ("1.5"), no números
    if t in ('int', 'uint', 'long', 'short', 'byte'): return 0
    if t in ('float', 'double'): return 0.0
    if t == 'bool': return False
    if t == 'string': return ''         # GameString es un grupo (game_strings): se trata abajo como referencia
    if t == 'DateTime': return '2019-01-01T00:00:00Z'
    if t in group_of: return ensure_default(group_of[t])
    if t in by_class:
        if t in stack: return None
        d = {}; fill(d, t, stack | {t}); return d
    if t in enums: return enums[t]
    return None
def fill(item, cls, stack):
    for prop, f in fields_of(cls).items():
        if not f['key'] or f['key'] in item: continue
        # [CMSDefault] se puede omitir, salvo en Fix: el valor por defecto del atributo es float y Parse lo asigna sin
        # convertir ("failed to convert parameters" en set_X). Esos van explícitos.
        if 'CMSDefault' in f['attrs'] and f['type'] not in ('Fix', 'Fix[]'): continue
        if 'CMSParseFunction' in f['attrs']:
            # Funciones propias (reciben object): los mapas esperan un diccionario JSON, las listas una lista, ParseStringAsInt texto
            t = f['type']
            # Con la llamada a la función anulada (patch_libil2cpp_cmslog.py), los Dictionary pasan por ParseListToDictionary: lista
            item[f['key']] = [] if (t.startswith('Dictionary<') or t.startswith('List<') or t.endswith('[]')) else '0'
            continue
        item[f['key']] = value_for(f['type'], stack)
# Items con id fijo pedidos fuera de ParseDataGroups: gear_pack_settings['singleton'] (GearPacksRemoteService),
# unranked_settings['default'] y unranked_event_visuals['blocked'] (UnrankedEventsService.Init)
singles = list(singles) + [('GearPackSettings', 'singleton'), ('UnrankedSettings', 'default'), ('UnrankedEventVisuals', 'blocked')]
for cls, ident in singles:
    g = group_of.get(cls)
    for i in dict.fromkeys(['singleton', ident]):
        if not any(x['id'] == i for x in groups[g]):
            item = {'id': i}; groups[g].append(item); fill(item, cls, set())
# Grupos con un item gp_default obligatorio: los datos del jugador (build_responses.py) los referencian por id
FORCED_DEFAULTS = ['vanity_items', 'vanity_item_colors', 'ultimates', 'cards']
for g in FORCED_DEFAULTS:
    if g in groups: ensure_default(g)
groups['daily_deals'] = []
# misc_settings: claves leídas con Dictionary<string, MiscSetting>.get_Item (il2cpp_metarefs.py); sin ellas, KeyNotFound
MISC = {'max_number_gear_pack_owned': 4, 'max_squadname_length': 20, 'max_username_length': 20,
        'clan_bounties_default_slot_quantity': 3, 'gacha_medium_threshold': 10, 'gacha_small_threshold': 5,
        'gear_pack_auto_decrypt': 0, 'horde_defeat_retry_cost': 0, 'main_menu_doober_ratio_percent': 100,
        'ai_min_y_deploy_cell': 0, 'bot_match_deployment_probability_decrement': 0.0, 'unit_battle_pin_scale': 1.0,
        'unit_dizzy_spin_threshold': 1.0, 'unit_legendary_pin_glow_scale': 1.0, 'unit_management_pinframe_size': 1.0,
        'unit_tab_selection_delay': 0.0, 'victory_min_time_animation_switch': 1.0, 'analytics_onboarding_version_string': '1'}
groups['misc_settings'] = [x for x in groups['misc_settings'] if x['id'] not in MISC] + [{'id': k, 'value': v} for k, v in MISC.items()]
# Avatar mínimo: AvatarFactory.SetVanityItems/GetEmblem buscan un vanity item activo de cada tipo, más 'emblem_default'.
# build_responses.py activa los gp_<tipo>.
VANITY_TYPES = ['head', 'torso', 'legs', 'skincolor', 'haircolor', 'emblem']
for vt in VANITY_TYPES:
    it = {'id': vt}; fill(it, 'VanityItemType', set()); groups['vanity_items_type'].append(it)
for vid, vt in [('gp_' + t, t) for t in VANITY_TYPES] + [('emblem_default', 'emblem')]:
    it = {'id': vid, 'type': vt, 'icon_sprite': value_for('Resource', set())}; fill(it, 'VanityItem', set()); groups['vanity_items'].append(it)
# Monedas: una por cada Currencies.CurrencyType (el perfil del jugador las referencia por id; ver build_responses.py)
groups['currencies'] = []
for cid, ctype in (('hard_currency', 'HardCurrency'), ('soft_currency', 'SoftCurrency')):
    item = {'id': cid, 'currency_type': ctype, 'max': 999999}; fill(item, 'Currencies', set()); groups['currencies'].append(item)
# Killswitches: killswitch_enabled=true APAGA la función (sin el item = encendida). streaming_assets apagado = no descargar asset bundles remotos (no existen).
# tutorial apagado = TutorialManager da el tutorial por completado (no hay datos de batallas de tutorial)
groups['killswitches'] = [{'id': 'streaming_assets', 'killswitch_enabled': True}, {'id': 'tutorial', 'killswitch_enabled': True}]
meta = {g: {'total': len(v)} for g, v in groups.items()}
meta.update({'_content_version': 'gprevival-2', '_segments': []})
groups['_meta'] = meta
json.dump(groups, open(sys.argv[4], 'w'), separators=(',', ':'))
nulls = sum(json.dumps(v).count('null') for k, v in groups.items() if k != '_meta')
print(len(groups) - 1, 'grupos;', sum(len(v) for k, v in groups.items() if k != '_meta'), 'items;', nulls, 'valores null (tipos sin resolver)')
