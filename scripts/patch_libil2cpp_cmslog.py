"""Diagnostic patch for libil2cpp.so (Gears POP 1.98): logs the exception that ParseCMSData swallows.
In ConnectionManager.<ParseCMSData>c__AnonStorey4.<>m__0 (catch of CMSManager.LoadCMSData) replaces
"end_catch + ClearDetailsStore" with "Debug.LogException(e) + end_catch". This way the CMS parser error shows up in logcat.
Intended side effect: the client keeps its ETag; the server changes the ETag when the CMS changes.
Usage: python3 -I patch_libil2cpp_cmslog.py <original libil2cpp.so> <output>"""
import sys, struct
def bl(pc, target): return 0x94000000 | (((target - pc) >> 2) & 0x3ffffff)
LOG_EXCEPTION = 0x1FF5360    # UnityEngine.Debug.LogException(Exception, MethodInfo*)
END_CATCH = 0xAF3DA0         # __cxa_end_catch@plt
PATCH = [
    (0x14F7BA8, bl(0x14F7BA8, END_CATCH), 0xF9400280),          # ldr x0, [x20]
    (0x14F7BAC, None, 0xAA1F03E1),                               # mov x1, xzr
    (0x14F7BB0, None, bl(0x14F7BB0, LOG_EXCEPTION)),             # bl Debug.LogException
    (0x14F7BB4, None, bl(0x14F7BB4, END_CATCH)),                 # bl __cxa_end_catch
    (0x14F7BB8, None, 0xD503201F), (0x14F7BBC, None, 0xD503201F), (0x14F7BC0, None, 0xD503201F),  # nop (no ClearDetailsStore)
]
# 2) The parser asserts (ParsingUtilsAssert) are empty in the release build: IsTrue(cond, msg) and Fail(msg) now go to
#    ParsingUtilsLogger.Error(msg) -> Debug.LogError. The IsTrue logic lives in the body of ParsingUtilsLogger.DebugFormat
#    (which becomes inert: it would only run with w1 == 0).
def b(pc, target): return 0x14000000 | (((target - pc) >> 2) & 0x3ffffff)
LOGGER_ERROR = 0x143AC5C
PATCH += [
    (0x143AA7C, None, b(0x143AA7C, 0x143AB04)),                  # ParsingUtilsAssert.IsTrue(bool, string) -> code cave
    (0x143AA88, None, b(0x143AA88, LOGGER_ERROR)),               # ParsingUtilsAssert.Fail(string) -> Logger.Error
    (0x143AB04, None, 0x35000061),                               # cbnz w1, +12 (condition true: nothing)
    (0x143AB08, None, 0xAA0203E1),                               # mov x1, x2 (message)
    (0x143AB0C, None, b(0x143AB0C, LOGGER_ERROR)),               # b Logger.Error
    (0x143AB10, None, 0xD65F03C0),                               # ret
]
# 3) [CMSParseFunction]: with DailyDeal.levels, assigning the result to LevelSlotContentDict gives "failed to convert parameters"
#    with any dictionary (even an empty one). Returning null, Parsing.Parse skips the assignment (cbz x19 at 0x1e6b774).
#    The shop's daily deals end up empty; this does not affect startup or battles.
#    Not even that works: the error comes from MethodBase.Invoke itself when converting the argument. The call in Parsing.Parse<T>
#    is disabled (0x1e6bbc4: bl MethodBase.Invoke -> mov x0, xzr): the 9 [CMSParseFunction] fields stay unassigned (null/0).
PATCH += [(0x1E6BBC4, None, 0xAA1F03E0)]   # mov x0, xzr
# 4) The dictionary branch of Parse<T> calls ParseListToDictionary<TKey, TValue> via reflection (MakeGenericMethod);
#    with TValue = SlotContent[] that generic instance does not exist in the game's IL2CPP and Invoke gives "failed to convert parameters".
#    The call is removed (0x1e6c6bc -> nop): the empty dictionary created with Activator is assigned. LIMITATION: the CMS
#    Dictionary<…> fields stay empty (today only DailyDeal.levels; revisit when real data comes in). They stay null.
#    Not even the empty dictionary can be assigned via reflection: x19 is left null so Parse skips the assignment.
PATCH += [(0x1E6C6BC, None, 0xAA1F03F3)]   # mov x19, xzr
# 5) SoftLaunchAccessGate.IsUserAllowedToLogin (0x14b8720): Google Play license check (Java class + RSA signature).
#    Without the Play Store (emulator) it blocks the login ("Sending error as not allow to log in"). Always true.
PATCH += [(0X14B8720, None, 0x52800020), (0X14B8724, None, 0xD65F03C0)]   # mov w0, #1 ; ret
# 6) DailyDeal cannot be parsed (assigning LevelSlotContentDict via reflection always fails, even with null).
#    The CMS leaves daily_deals empty and CMSData.ParseDataGroups does not look up the daily_deals_default item
#    (0x16aed40: bl ParseCMSGroupItem<DailyDeal> -> mov x0, xzr). CMSData+0x430 (default daily deal) stays null.
PATCH += [(0x16AED40, None, 0xAA1F03E0)]   # mov x0, xzr
# 7) Diagnostics: in MonoMethod.Invoke, the "failed to convert parameters" ArgumentException carries the method NAME
#    (MonoMethod.get_Name) instead of the fixed text, to know which setter/method fails.
PATCH += [
    (0x1BE1ED8, None, 0xAA0003F3),                     # mov x19, x0   (exception already created)
    (0x1BE1EDC, None, 0xAA1503E0),                     # mov x0, x21   (this = MonoMethod)
    (0x1BE1FA8, None, bl(0x1BE1FA8, 0x1BE2274)),       # bl MonoMethod.get_Name
    (0x1BE1FAC, None, 0xAA0003E1),                     # mov x1, x0    (message = name)
    (0x1BE1FB0, None, 0xAA1303E0),                     # mov x0, x19
]
ORIG = {0x1BE1EE0: 0x14000032, 0x16AED40: 0x940389c7, 0x1E6C6BC: bl(0x1E6C6BC, 0x1BDCFD8), 0x1E6BBC4: bl(0x1E6BBC4, 0x1BDCFD8), 0x143AA7C: 0xD65F03C0, 0x143AA88: 0xD65F03C0, 0x14F7BA8: bl(0x14F7BA8, END_CATCH), 0x14F7BAC: 0xF9400A74, 0x14F7BC0: bl(0x14F7BC0, 0x14F8BA8)}
d = bytearray(open(sys.argv[1], 'rb').read())
for a, v in ORIG.items():
    cur = struct.unpack_from('<I', d, a)[0]
    if cur != v: sys.exit(f"{a:#x}: expected {v:08x} but found {cur:08x}")
for a, _, new in PATCH: struct.pack_into('<I', d, a, new)
open(sys.argv[2], 'wb').write(d); print("ok:", len(PATCH), "instructions")
