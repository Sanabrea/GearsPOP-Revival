import struct,sys
def v(n):
    o=b''
    while n>0x7f: o+=bytes([(n&0x7f)|0x80]); n>>=7
    return o+bytes([n])
def f(num,b): return v(num<<3|2)+v(len(b))+b
def u(num,x): return v(num<<3)+v(x)
lr=f(1,b'DeviceId')+f(2,b'K'*88)+f(3,b'1.98')+f(5,b'Android')
guid=b'\x09'+bytes(range(8))+b'\x11'+bytes(range(8,16))
hdr=f(51110556, f(1,guid)+u(2,2))
msg=f(71269765, f(1,lr))+f(1,hdr)
open(sys.argv[1],'wb').write(b'\x00'+struct.pack('>I',len(msg))+msg)
