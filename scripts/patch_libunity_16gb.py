"""Parche de libunity.so (Unity 2018.4.12f1, arm64) para el crash "Using memoryadresses from more that 16GB of memory".

Unity guarda qué memoria es suya en una tabla con 5 casillas indexadas por (dirección >> 32), o sea 4 GB por casilla.
En Android 16 el asignador del sistema reparte la memoria en más de 5 zonas de 4 GB; Unity usa entonces la casilla -1
(un contador), lo lee como puntero y truena con SIGSEGV.

El parche cambia la clave a (dirección >> 35) y la tabla raíz de 128 a 1024 entradas (bits 25..34),
con su contador en +0x2000. Así cada casilla cubre 32 GB y las 5 juntas 160 GB.
Toca solo las 3 funciones de la tabla: consulta 0x7415b8, registro 0x741684 y baja 0x7418dc.

Uso: python3 -I patch_libunity_16gb.py <libunity.so original> <salida>
"""
import sys

# dirección: (bytes originales, bytes nuevos, descripción)
PATCHES = {
    0x7415B8: ("28fc60d3", "28fc63d3", "consulta: lsr x8, x1, #32 -> #35"),
    0x741620: ("297c59d3", "298859d3", "consulta: ubfx x9, x1, #25, #7 -> #10"),
    0x74169C: ("89fe60d3", "89fe63d3", "registro: lsr x9, x20, #32 -> #35"),
    0x741764: ("20108052", "20808052", "registro: mov w0, #0x81 -> #0x401 (entradas raíz)"),
    0x741784: ("1f0102f9", "1f0110f9", "registro: str xzr, [x8, #0x400] -> #0x2000"),
    0x74178C: ("957e59d3", "958a59d3", "registro: ubfx x21, x20, #25, #7 -> #10"),
    0x741898: ("090144b9", "090160b9", "registro: ldr w9, [x8, #0x400] -> #0x2000"),
    0x7418A8: ("090104b9", "090120b9", "registro: str w9, [x8, #0x400] -> #0x2000"),
    0x7418F4: ("89fe60d3", "89fe63d3", "baja: lsr x9, x20, #32 -> #35"),
    0x7419B8: ("967e59d3", "968a59d3", "baja: ubfx x22, x20, #25, #7 -> #10"),
    0x741AB8: ("090144b9", "090160b9", "baja: ldr w9, [x8, #0x400] -> #0x2000"),
    0x741AC0: ("090104b9", "090120b9", "baja: str w9, [x8, #0x400] -> #0x2000"),
    0x741ACC: ("01818052", "01018452", "baja: mov w1, #0x408 -> #0x2008 (tamaño al liberar)"),
}

def main(src, dst):
    d = bytearray(open(src, "rb").read())
    for addr, (old, new, desc) in sorted(PATCHES.items()):
        cur = d[addr:addr + 4].hex()
        if cur == new:
            print(f"{addr:#x} ya parcheado ({desc})")
            continue
        if cur != old:
            sys.exit(f"{addr:#x}: se esperaba {old} y hay {cur}; libunity no es la versión 2018.4.12f1 esperada")
        d[addr:addr + 4] = bytes.fromhex(new)
        print(f"{addr:#x} ok: {desc}")
    open(dst, "wb").write(d)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
