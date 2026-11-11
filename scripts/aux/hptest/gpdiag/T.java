package gpdiag;
import java.util.*;
public class T { public static void main(String[] a) {
  // RFC 7541 C.4.1: :method GET, :scheme http, :path /, :authority www.example.com (Huffman)
  byte[] b = hex("828684418cf1e3c2e5f23a6ba0ab90f4ff");
  for (String[] h : new Hpack().decode(b)) System.out.println(h[0]+"="+h[1]);
  // literal without huffman, with indexing: :path /x/y
  byte[] c = hex("4405"+ "2f782f792f".substring(0,10));
  for (String[] h : new Hpack().decode(c)) System.out.println(h[0]+"="+h[1]);
}
static byte[] hex(String s){byte[] r=new byte[s.length()/2];for(int i=0;i<r.length;i++)r[i]=(byte)Integer.parseInt(s.substring(2*i,2*i+2),16);return r;}}
