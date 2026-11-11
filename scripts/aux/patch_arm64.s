lsr x8, x1, #35
ubfx x9, x1, #25, #10
lsr x9, x20, #35
mov w0, #0x401
str xzr, [x8, #0x2000]
ubfx x21, x20, #25, #10
ldr w9, [x8, #0x2000]
str w9, [x8, #0x2000]
lsr x9, x20, #35
ubfx x22, x20, #25, #10
ldr w9, [x8, #0x2000]
str w9, [x8, #0x2000]
mov w1, #0x2008
