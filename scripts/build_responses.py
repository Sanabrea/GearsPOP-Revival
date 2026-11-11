"""Respuestas por defecto del gateway para el servidor embebido.
Para cada petición (Message<Req>) arma el cuerpo de Result<Resp> = {1: Resp} con valores por defecto recursivos:
textos "", sub-mensajes llenos, listas con un elemento por defecto (protobuf-net deja null lo que no viene).
Salida: TSV "etiqueta_peticion  etiqueta_resultado  base64(cuerpo del Result)  nombre"  -> assets/diag/responses.tsv
Uso: python3 -I build_responses.py <dump_dir> <libil2cpp.so> <message_tags.tsv> <salida.tsv>"""
import sys, base64, re
sys.path.insert(0, __import__('os').path.dirname(__file__))
from dto_schema import Schema

dump, so, tags_path, outp = sys.argv[1:5]
S = Schema(dump, so)
tags = {}
for l in open(tags_path, encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) >= 2 and p[0].isdigit(): tags[p[1]] = int(p[0])

# Petición -> tipo de respuesta (sacado de RemoteServiceBase.SendRequest<Req, Resp> en script.json)
import json, os
PAIRS = json.load(open(os.path.join(os.path.dirname(tags_path), 'request_pairs.json')))
# Listas que deben ir vacías: sus elementos referencian items del CMS por id (un id vacío rompe las búsquedas)
EMPTY_LISTS = {'MutedPlayerDto', 'DailyLoginBonusDto', 'ActiveVanityItemDto', 'GearPackDto'}
# Mapas que el cliente recorre sin revisar null: van con una entrada por defecto (clave 0 / 'gp_default')
ONE_ENTRY_MAPS = {('BountiesDto', 1)}   # (clase, número de campo): el esquema repite el nombre del getter
# Ids que apuntan a items del CMS: van como 'gp_default' (build_cms.py crea esos items). Los ids propios del jugador, vacíos.
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
        if t.startswith('Dictionary<'):                          # mapas: se omiten (null), salvo ONE_ENTRY_MAPS
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
                out += ld(num, inner)                            # en listas: un elemento por defecto
        # números, bool y enums: el valor por defecto (0/false) no hace falta escribirlo
    return out

# Campos fijos por tipo de respuesta (se agregan al valor por defecto). El esquema no ve todos los getters.
EXTRA = {
    # BattleServerInformation.TryParse exige "https://host:puerto"
    'ServerInformationQueryResponse': ld(1, b'local') + ld(2, b'https://127.0.0.1:11111'),
}

# Mensajes completos por clase (reemplazan el valor por defecto)
def currency(cid, qty): return ld(1, ld(1, cid) + ld(2, cid) + field(3, 0, varint(qty)))
OVERRIDE = {
    # Monedas del perfil: ids de los items 'currencies' del CMS (build_cms.py)
    # Vanidad activa: un item por tipo (gp_<tipo> en build_cms.py); sin emblema GetEmblem da NullReference
    'ActiveVanityItemsDto': b''.join(ld(1, ld(1, b'gp_' + t)) for t in (b'head', b'torso', b'legs', b'skincolor', b'haircolor', b'emblem')),
    'CurrenciesDto': currency(b'hard_currency', 500) + currency(b'soft_currency', 5000),
}

rows = []
for req, resp in PAIRS.items():
    qt, rt = tags.get(f'Message<{req}>'), tags.get(f'Result<{resp}>')
    if not (qt and rt): print('sin etiqueta para', req, resp); continue
    body = ld(1, default_msg(resp) + EXTRA.get(resp, b''))
    rows.append(f"{qt}\t{rt}\t{base64.b64encode(body).decode()}\t{req}->{resp}")
    print(f"{req} ({qt}) -> Result<{resp}> ({rt}): {len(body)} bytes")
open(outp, 'w').write('\n'.join(rows) + '\n')
