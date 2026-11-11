"""Patch for libunity.so (Unity 2018.4.12f1, arm64) for the "Using memoryadresses from more that 16GB of memory" crash.

Unity tracks which memory is its own in a table with 5 slots indexed by (address >> 32), i.e. 4 GB per slot.
On Android 16 the system allocator spreads memory over more than 5 zones of 4 GB; Unity then uses slot -1
(a counter), reads it as a pointer and crashes with SIGSEGV.

The patch changes the key to (address >> 35) and the root table from 128 to 1024 entries (bits 25..34),
with its counter at +0x2000. That way each slot covers 32 GB and the 5 together 160 GB.
It only touches the table's 3 functions: lookup 0x7415b8, register 0x741684 and unregister 0x7418dc.

Usage: python3 -I patch_libunity_16gb.py <original libunity.so> <output>
"""
import sys

# address: (original bytes, new bytes, description)
PATCHES = {
    0x7415B8: ("28fc60d3", "28fc63d3", "lookup: lsr x8, x1, #32 -> #35"),
    0x741620: ("297c59d3", "298859d3", "lookup: ubfx x9, x1, #25, #7 -> #10"),
    0x74169C: ("89fe60d3", "89fe63d3", "register: lsr x9, x20, #32 -> #35"),
    0x741764: ("20108052", "20808052", "register: mov w0, #0x81 -> #0x401 (root entries)"),
    0x741784: ("1f0102f9", "1f0110f9", "register: str xzr, [x8, #0x400] -> #0x2000"),
    0x74178C: ("957e59d3", "958a59d3", "register: ubfx x21, x20, #25, #7 -> #10"),
    0x741898: ("090144b9", "090160b9", "register: ldr w9, [x8, #0x400] -> #0x2000"),
    0x7418A8: ("090104b9", "090120b9", "register: str w9, [x8, #0x400] -> #0x2000"),
    0x7418F4: ("89fe60d3", "89fe63d3", "unregister: lsr x9, x20, #32 -> #35"),
    0x7419B8: ("967e59d3", "968a59d3", "unregister: ubfx x22, x20, #25, #7 -> #10"),
    0x741AB8: ("090144b9", "090160b9", "unregister: ldr w9, [x8, #0x400] -> #0x2000"),
    0x741AC0: ("090104b9", "090120b9", "unregister: str w9, [x8, #0x400] -> #0x2000"),
    0x741ACC: ("01818052", "01018452", "unregister: mov w1, #0x408 -> #0x2008 (size on free)"),
}

def main(src, dst):
    d = bytearray(open(src, "rb").read())
    for addr, (old, new, desc) in sorted(PATCHES.items()):
        cur = d[addr:addr + 4].hex()
        if cur == new:
            print(f"{addr:#x} already patched ({desc})")
            continue
        if cur != old:
            sys.exit(f"{addr:#x}: expected {old} but found {cur}; libunity is not the expected 2018.4.12f1 version")
        d[addr:addr + 4] = bytes.fromhex(new)
        print(f"{addr:#x} ok: {desc}")
    open(dst, "wb").write(d)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
