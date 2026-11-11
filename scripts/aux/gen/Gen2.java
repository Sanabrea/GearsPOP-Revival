import java.lang.reflect.*;
public class Gen2 { public static void main(String[] a) throws Exception {
 Class<?> c = Class.forName("jdk.internal.net.http.hpack.QuickHuffman");
 Method v = c.getDeclaredMethod("codeValueOf", char.class), l = c.getDeclaredMethod("codeLengthOf", char.class);
 v.setAccessible(true); l.setAccessible(true);
 StringBuilder cs = new StringBuilder(), ls = new StringBuilder();
 for (int ch = 0; ch < 256; ch++) { long len = (long) l.invoke(null,(char)ch); long code = ((long) v.invoke(null,(char)ch)) >>> (64 - len);
   cs.append("0x").append(Long.toHexString(code)).append(ch%12==11?",\n        ":","); ls.append(len).append(ch%32==31?",\n        ":","); }
 System.out.println("    static final int[] CODES = {\n        " + cs + "};\n    static final byte[] LENS = {\n        " + ls + "};");
}}
