package gpdiag; import java.net.*;
public class H2Test { public static void main(String[] a) throws Exception {
  Catapult.loadTags(new java.io.FileInputStream("/Users/Julian/Downloads/GearsPOP-Revival/analysis/protocol/message_tags.tsv")); ServerSocket ss = new ServerSocket(18080); System.out.println("ready");
  Socket c = ss.accept(); c.setSoTimeout(5000);
  try { new DiagProvider.H2("[test]", new java.io.BufferedInputStream(c.getInputStream()), c.getOutputStream()).run(); }
  catch (Exception e) { System.out.println("end: " + e); }
}}
