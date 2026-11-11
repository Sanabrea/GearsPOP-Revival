import java.lang.reflect.*;
public class Gen { public static void main(String[] a) throws Exception {
 Class<?> c = Class.forName("jdk.internal.net.http.hpack.QuickHuffman");
 Method v = c.getDeclaredMethod("codeValueOf", char.class), l = c.getDeclaredMethod("codeLengthOf", char.class);
 v.setAccessible(true); l.setAccessible(true);
 for (int ch : new int[]{32,48,97,256-1}) System.out.println(ch+" "+Long.toHexString((long)v.invoke(null,(char)ch))+" "+l.invoke(null,(char)ch));
}}
