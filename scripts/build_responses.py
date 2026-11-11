"""Default gateway responses for the embedded server.
For each request (Message<Req>) builds the body of Result<Resp> = {1: Resp} with recursive default values:
strings "", filled sub-messages, lists with one default element (protobuf-net leaves missing fields null).
Output: TSV "request_tag  result_tag  base64(Result body)  name"  -> assets/diag/responses.tsv
Usage: python3 -I build_responses.py <dump_dir> <libil2cpp.so> <message_tags.tsv> <output.tsv>"""
import sys, base64, re
sys.path.insert(0, __import__('os').path.dirname(__file__))
from dto_schema import Schema

dump, so, tags_path, outp = sys.argv[1:5]
S = Schema(dump, so)
tags = {}
for l in open(tags_path, encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) >= 2 and p[0].isdigit(): tags[p[1]] = int(p[0])

# Request -> response type (taken from RemoteServiceBase.SendRequest<Req, Resp> in script.json)
import json, os
PAIRS = json.load(open(os.path.join(os.path.dirname(tags_path), 'request_pairs.json')))
# Lists that must be empty: their elements reference CMS items by id (an empty id breaks the lookups)
EMPTY_LISTS = {'MutedPlayerDto', 'DailyLoginBonusDto', 'ActiveVanityItemDto', 'GearPackDto'}
# Maps the client iterates without null checks: they get one default entry (key 0 / 'gp_default')
ONE_ENTRY_MAPS = {('BountiesDto', 1)}   # (class, field number): the schema repeats the getter name
# Ids pointing to CMS items are sent as 'gp_default' (build_cms.py creates those items). The player's own ids, empty.
OWN_IDS = {'UserId', 'PublicId', 'SupportId', 'ClanId', 'AccountId'}
def id_value(prop): return b'' if prop in OWN_IDS else b'gp_default'

def varint(v):
    o = bytearray()
    while True:
        b = v & 0x7f; v >>= 7
        if v: o.append(b | 0x80)
        else: o.append(b); return bytes(o)

def field(num, wt, payload):
    return varint(num << 3 | wt) + payload

def ld(num, b): return field(num, 2, varint(len(b)) + b)

def elem_type(t):
    m = re.match(r'(?:List|HashSet|IList|IEnumerable)<(.+)>$', t)
    if m: return m.group(1)
    if t.endswith('[]'): return t[:-2]
    return None

def default_msg(cls, depth=0, stack=()):
    if cls in globals().get('OVERRIDE', {}): return OVERRIDE[cls]
    if depth > 6 or cls in stack: return b''
    fs = S.fields(cls)
    if not fs: return b''
    out = b''
    for num, prop, t, call in fs:
        prop = prop or ''
        et = elem_type(t)
        base = et or t
        if t.startswith('Dictionary<'):                          # maps: omitted (null), except ONE_ENTRY_MAPS
            if (cls, num) in ONE_ENTRY_MAPS:
                k, v = [x.strip() for x in t[11:-1].split(',', 1)]
                key = ld(1, b'gp_default') if k == 'string' else field(1, 0, varint(0))
                out += ld(num, key + ld(2, default_msg(v, depth + 1, stack + (cls,))))
            continue
        if call == 'WriteString' or base == 'string':
            is_id = prop == 'Id' or prop.endswith('Id') or prop.endswith('Ids') or prop in ('Cards',)
            if not et: out += ld(num, id_value(prop) if is_id else b'')
            elif is_id: out += ld(num, b'gp_default')
        elif call.startswith('StartSubItem') or call == 'StartSubItem':
            if base in ('DateTime', 'TimeSpan', 'Guid'): out += ld(num, b'')
            elif base in S.enums: pass
            elif et and base in EMPTY_LISTS: pass
            else:
                inner = default_msg(base, depth + 1, stack + (cls,))
                out += ld(num, inner)                            # in lists: one default element
        # numbers, bools and enums: the default value (0/false) need not be written
    return out

# Fixed fields per response type (appended to the default value). The schema does not see every getter.
EXTRA = {
    # BattleServerInformation.TryParse requires "https://host:port"
    'ServerInformationQueryResponse': ld(1, b'local') + ld(2, b'https://127.0.0.1:11111'),
}

# Complete messages per class (replace the default value)
def currency(cid, qty): return ld(1, ld(1, cid) + ld(2, cid) + field(3, 0, varint(qty)))
OVERRIDE = {
    # Profile currencies: ids of the CMS 'currencies' items (build_cms.py)
    # Active vanity: one item per type (gp_<type> in build_cms.py); without an emblem GetEmblem throws NullReference
    'ActiveVanityItemsDto': b''.join(ld(1, ld(1, b'gp_' + t)) for t in (b'head', b'torso', b'legs', b'skincolor', b'haircolor', b'emblem')),
    'CurrenciesDto': currency(b'hard_currency', 500) + currency(b'soft_currency', 5000),
}

rows = []
for req, resp in PAIRS.items():
    qt, rt = tags.get(f'Message<{req}>'), tags.get(f'Result<{resp}>')
    if not (qt and rt): print('no tag for', req, resp); continue
    body = ld(1, default_msg(resp) + EXTRA.get(resp, b''))
    rows.append(f"{qt}\t{rt}\t{base64.b64encode(body).decode()}\t{req}->{resp}")
    print(f"{req} ({qt}) -> Result<{resp}> ({rt}): {len(body)} bytes")
open(outp, 'w').write('\n'.join(rows) + '\n')
