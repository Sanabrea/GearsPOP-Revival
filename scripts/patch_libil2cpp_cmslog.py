"""Parche de diagnóstico de libil2cpp.so (Gears POP 1.98): registra la excepción que se traga ParseCMSData.
En ConnectionManager.<ParseCMSData>c__AnonStorey4.<>m__0 (catch de CMSManager.LoadCMSData) cambia
"end_catch + ClearDetailsStore" por "Debug.LogException(e) + end_catch". Así el error del parser del CMS sale en logcat.
Efecto secundario buscado: el cliente conserva su ETag; el servidor cambia el ETag cuando cambia el CMS.
Uso: python3 -I patch_libil2cpp_cmslog.py <libil2cpp.so original> <salida>"""
import sys, struct
def bl(pc, target): return 0x94000000 | (((target - pc) >> 2) & 0x3ffffff)
LOG_EXCEPTION = 0x1FF5360    # UnityEngine.Debug.LogException(Exception, MethodInfo*)
END_CATCH = 0xAF3DA0         # __cxa_end_catch@plt
PATCH = [
    (0x14F7BA8, bl(0x14F7BA8, END_CATCH), 0xF9400280),          # ldr x0, [x20]
    (0x14F7BAC, None, 0xAA1F03E1),                               # mov x1, xzr
    (0x14F7BB0, None, bl(0x14F7BB0, LOG_EXCEPTION)),             # bl Debug.LogException
    (0x14F7BB4, None, bl(0x14F7BB4, END_CATCH)),                 # bl __cxa_end_catch
    (0x14F7BB8, None, 0xD503201F), (0x14F7BBC, None, 0xD503201F), (0x14F7BC0, None, 0xD503201F),  # nop (sin ClearDetailsStore)
]
# 2) Los asserts del parser (ParsingUtilsAssert) están vacíos en la versión final: IsTrue(cond, msg) y Fail(msg) pasan a
#    ParsingUtilsLogger.Error(msg) -> Debug.LogError. La lógica de IsTrue va en el cuerpo de ParsingUtilsLogger.DebugFormat
#    (que queda inerte: solo se ejecutaría con w1 == 0).
def b(pc, target): return 0x14000000 | (((target - pc) >> 2) & 0x3ffffff)
LOGGER_ERROR = 0x143AC5C
PATCH += [
    (0x143AA7C, None, b(0x143AA7C, 0x143AB04)),                  # ParsingUtilsAssert.IsTrue(bool, string) -> cueva
    (0x143AA88, None, b(0x143AA88, LOGGER_ERROR)),               # ParsingUtilsAssert.Fail(string) -> Logger.Error
    (0x143AB04, None, 0x35000061),                               # cbnz w1, +12 (condición verdadera: nada)
    (0x143AB08, None, 0xAA0203E1),                               # mov x1, x2 (mensaje)
    (0x143AB0C, None, b(0x143AB0C, LOGGER_ERROR)),               # b Logger.Error
    (0x143AB10, None, 0xD65F03C0),                               # ret
]
# 3) [CMSParseFunction]: con DailyDeal.levels, asignar el resultado a LevelSlotContentDict da "failed to convert parameters"
#    con cualquier diccionario (incluso vacío). Devolviendo null, Parsing.Parse se salta la asignación (cbz x19 en 0x1e6b774).
#    Las ofertas diarias de la tienda quedan vacías; no afecta al arranque ni a las batallas.
#    Ni así: el error es del propio MethodBase.Invoke al convertir el argumento. Se anula la llamada en Parsing.Parse<T>
#    (0x1e6bbc4: bl MethodBase.Invoke -> mov x0, xzr): los 9 campos con [CMSParseFunction] quedan sin asignar (null/0).
PATCH += [(0x1E6BBC4, None, 0xAA1F03E0)]   # mov x0, xzr
# 4) La rama de diccionarios de Parse<T> llama por reflexión a ParseListToDictionary<TKey, TValor> (MakeGenericMethod);
#    con TValor = SlotContent[] esa instancia genérica no existe en el IL2CPP del juego y Invoke da "failed to convert parameters".
#    Se quita la llamada (0x1e6c6bc -> nop): se asigna el diccionario vacío creado con Activator. LIMITACIÓN: los campos
#    Dictionary<…> del CMS quedan vacíos (hoy solo DailyDeal.levels; revisar cuando entren datos reales). Quedan en null.
#    Ni el diccionario vacío se puede asignar por reflexión: se deja x19 = null para que Parse se salte la asignación.
PATCH += [(0x1E6C6BC, None, 0xAA1F03F3)]   # mov x19, xzr
# 5) SoftLaunchAccessGate.IsUserAllowedToLogin (0x14b8720): control de licencia de Google Play (clase Java + firma RSA).
#    Sin Play Store (emulador) bloquea el login ("Sending error as not allow to log in"). Siempre true.
PATCH += [(0X14B8720, None, 0x52800020), (0X14B8724, None, 0xD65F03C0)]   # mov w0, #1 ; ret
# 6) DailyDeal no se puede parsear (asignar LevelSlotContentDict por reflexión falla siempre, incluso con null).
#    El CMS deja daily_deals vacío y CMSData.ParseDataGroups no busca el item daily_deals_default
#    (0x16aed40: bl ParseCMSGroupItem<DailyDeal> -> mov x0, xzr). CMSData+0x430 (oferta diaria por defecto) queda null.
PATCH += [(0x16AED40, None, 0xAA1F03E0)]   # mov x0, xzr
# 7) Diagnóstico: en MonoMethod.Invoke, la ArgumentException "failed to convert parameters" lleva el NOMBRE del método
#    (MonoMethod.get_Name) en vez del texto fijo, para saber qué setter/método falla.
PATCH += [
    (0x1BE1ED8, None, 0xAA0003F3),                     # mov x19, x0   (excepción ya creada)
    (0x1BE1EDC, None, 0xAA1503E0),                     # mov x0, x21   (this = MonoMethod)
    (0x1BE1FA8, None, bl(0x1BE1FA8, 0x1BE2274)),       # bl MonoMethod.get_Name
    (0x1BE1FAC, None, 0xAA0003E1),                     # mov x1, x0    (mensaje = nombre)
    (0x1BE1FB0, None, 0xAA1303E0),                     # mov x0, x19
]
ORIG = {0x1BE1EE0: 0x14000032, 0x16AED40: 0x940389c7, 0x1E6C6BC: bl(0x1E6C6BC, 0x1BDCFD8), 0x1E6BBC4: bl(0x1E6BBC4, 0x1BDCFD8), 0x143AA7C: 0xD65F03C0, 0x143AA88: 0xD65F03C0, 0x14F7BA8: bl(0x14F7BA8, END_CATCH), 0x14F7BAC: 0xF9400A74, 0x14F7BC0: bl(0x14F7BC0, 0x14F8BA8)}
d = bytearray(open(sys.argv[1], 'rb').read())
for a, v in ORIG.items():
    cur = struct.unpack_from('<I', d, a)[0]
    if cur != v: sys.exit(f"{a:#x}: se esperaba {v:08x} y hay {cur:08x}")
for a, _, new in PATCH: struct.pack_into('<I', d, a, new)
open(sys.argv[2], 'wb').write(d); print("ok:", len(PATCH), "instrucciones")
