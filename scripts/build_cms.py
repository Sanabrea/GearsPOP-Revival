"""Builds the CMS served by the embedded server (Gamefuel format: {group: [items with "id"], "_meta": {...}}).
Step 2: complete items. Each [CMSField] field gets a default value for its type; references point to a
"gp_default" item in the target group (which is created and filled the same way); [CMSDefault] fields are omitted.
Usage: python3 -I build_cms.py <cms_schema.json> <cms_singletons.json> <dump.cs> <output.json>"""
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
    if t.startswith('Dictionary<'): return []   # Parsing uses ParseListToDictionary: in the JSON it is a list of items with id
    if t == 'Fix': return '0'          # Parsing.ParseFixed reads text ("1.5"), not numbers
    if t in ('int', 'uint', 'long', 'short', 'byte'): return 0
    if t in ('float', 'double'): return 0.0
    if t == 'bool': return False
    if t == 'string': return ''         # GameString is a group (game_strings): handled below as a reference
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
        # [CMSDefault] can be omitted, except for Fix: the attribute's default value is a float and Parse assigns it without
        # converting ("failed to convert parameters" in set_X). Those are written explicitly.
        if 'CMSDefault' in f['attrs'] and f['type'] not in ('Fix', 'Fix[]'): continue
        if 'CMSParseFunction' in f['attrs']:
            # Custom functions (take object): maps expect a JSON dictionary, lists a list, ParseStringAsInt text
            t = f['type']
            # With the function call disabled (patch_libil2cpp_cmslog.py), Dictionaries go through ParseListToDictionary: list
            item[f['key']] = [] if (t.startswith('Dictionary<') or t.startswith('List<') or t.endswith('[]')) else '0'
            continue
        item[f['key']] = value_for(f['type'], stack)
# Items with a fixed id requested outside ParseDataGroups: gear_pack_settings['singleton'] (GearPacksRemoteService),
# unranked_settings['default'] and unranked_event_visuals['blocked'] (UnrankedEventsService.Init)
singles = list(singles) + [('GearPackSettings', 'singleton'), ('UnrankedSettings', 'default'), ('UnrankedEventVisuals', 'blocked')]
for cls, ident in singles:
    g = group_of.get(cls)
    for i in dict.fromkeys(['singleton', ident]):
        if not any(x['id'] == i for x in groups[g]):
            item = {'id': i}; groups[g].append(item); fill(item, cls, set())
# Groups with a mandatory gp_default item: the player data (build_responses.py) references them by id
FORCED_DEFAULTS = ['vanity_items', 'vanity_item_colors', 'ultimates', 'cards']
for g in FORCED_DEFAULTS:
    if g in groups: ensure_default(g)
groups['daily_deals'] = []
# misc_settings: keys read with Dictionary<string, MiscSetting>.get_Item (il2cpp_metarefs.py); without them, KeyNotFound
MISC = {'max_number_gear_pack_owned': 4, 'max_squadname_length': 20, 'max_username_length': 20,
        'clan_bounties_default_slot_quantity': 3, 'gacha_medium_threshold': 10, 'gacha_small_threshold': 5,
        'gear_pack_auto_decrypt': 0, 'horde_defeat_retry_cost': 0, 'main_menu_doober_ratio_percent': 100,
        'ai_min_y_deploy_cell': 0, 'bot_match_deployment_probability_decrement': 0.0, 'unit_battle_pin_scale': 1.0,
        'unit_dizzy_spin_threshold': 1.0, 'unit_legendary_pin_glow_scale': 1.0, 'unit_management_pinframe_size': 1.0,
        'unit_tab_selection_delay': 0.0, 'victory_min_time_animation_switch': 1.0, 'analytics_onboarding_version_string': '1'}
groups['misc_settings'] = [x for x in groups['misc_settings'] if x['id'] not in MISC] + [{'id': k, 'value': v} for k, v in MISC.items()]
# Minimal avatar: AvatarFactory.SetVanityItems/GetEmblem look for one active vanity item of each type, plus 'emblem_default'.
# build_responses.py activates the gp_<type> ones.
VANITY_TYPES = ['head', 'torso', 'legs', 'skincolor', 'haircolor', 'emblem']
for vt in VANITY_TYPES:
    it = {'id': vt}; fill(it, 'VanityItemType', set()); groups['vanity_items_type'].append(it)
for vid, vt in [('gp_' + t, t) for t in VANITY_TYPES] + [('emblem_default', 'emblem')]:
    it = {'id': vid, 'type': vt, 'icon_sprite': value_for('Resource', set())}; fill(it, 'VanityItem', set()); groups['vanity_items'].append(it)
# Currencies: one per Currencies.CurrencyType (the player profile references them by id; see build_responses.py)
groups['currencies'] = []
for cid, ctype in (('hard_currency', 'HardCurrency'), ('soft_currency', 'SoftCurrency')):
    item = {'id': cid, 'currency_type': ctype, 'max': 999999}; fill(item, 'Currencies', set()); groups['currencies'].append(item)
# Killswitches: killswitch_enabled=true turns the feature OFF (no item = on). streaming_assets off = do not download remote asset bundles (they do not exist).
# tutorial off = TutorialManager treats the tutorial as completed (there is no tutorial battle data)
groups['killswitches'] = [{'id': 'streaming_assets', 'killswitch_enabled': True}, {'id': 'tutorial', 'killswitch_enabled': True}]
meta = {g: {'total': len(v)} for g, v in groups.items()}
meta.update({'_content_version': 'gprevival-2', '_segments': []})
groups['_meta'] = meta
json.dump(groups, open(sys.argv[4], 'w'), separators=(',', ':'))
nulls = sum(json.dumps(v).count('null') for k, v in groups.items() if k != '_meta')
print(len(groups) - 1, 'groups;', sum(len(v) for k, v in groups.items() if k != '_meta'), 'items;', nulls, 'null values (unresolved types)')
