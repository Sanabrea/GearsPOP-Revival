package gpdiag;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.util.Log;

import java.io.*;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.text.SimpleDateFormat;
import java.util.*;

import javax.net.ssl.*;

/**
 * Servidor de diagnóstico de Gears POP Revival (entrega 0).
 * Un ContentProvider se crea al iniciar el proceso de la app, antes de la Activity de Unity,
 * así que arranca los sockets sin tocar el código del juego.
 * Solo registra lo que pide el cliente (servicio, método, tamaño). No implementa lógica de juego:
 * a cada llamada gRPC responde UNIMPLEMENTED (12) para que el cliente falle rápido en vez de colgarse.
 *
 * Puertos en assets/diag/ports.txt, una línea por puerto: "<puerto> <tls|plain> <etiqueta>".
 */
public class DiagProvider extends ContentProvider {
    static final String TAG = "GPDiag";
    static File logFile;
    static final SimpleDateFormat TS = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);

    static synchronized void log(String msg) {
        Log.i(TAG, msg);
        if (logFile == null) return;
        try (FileWriter w = new FileWriter(logFile, true)) {
            w.write(TS.format(new Date()) + " " + msg + "\n");
        } catch (IOException ignored) { }
    }

    @Override
    public boolean onCreate() {
        final Context ctx = getContext();
        appCtx = ctx;
        try {
            File dir = ctx.getExternalFilesDir(null);
            if (dir == null) dir = ctx.getFilesDir();
            logFile = new File(dir, "gpdiag.log");
        } catch (Throwable t) { Log.e(TAG, "sin archivo de log", t); }
        log("=== GPDiag inicia, pid " + android.os.Process.myPid() + ", log en " + logFile);
        captureLogcat();
        log("GPDiag versión " + VERSION);
        checkPatches(ctx);
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((th, ex) -> {
            StringWriter sw = new StringWriter(); ex.printStackTrace(new PrintWriter(sw));
            log("CRASH Java en hilo " + th.getName() + ": " + sw);
            if (prev != null) prev.uncaughtException(th, ex);
        });
        new Thread(() -> startAll(ctx), "gpdiag-main").start();
        new Thread(DiagProvider::watchdog, "gpdiag-watchdog").start();
        new Thread(() -> exitReasons(ctx), "gpdiag-exit").start();
        return true;
    }

    /** Android 11+: por qué murieron los procesos anteriores de la app (crash nativo, ANR, sistema, congelador…). */
    static void exitReasons(Context ctx) {
        if (android.os.Build.VERSION.SDK_INT < 30) { log("exit-info: requiere Android 11+"); return; }
        try {
            android.app.ActivityManager am = (android.app.ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE);
            List<android.app.ApplicationExitInfo> list = am.getHistoricalProcessExitReasons(null, 0, 6);
            SimpleDateFormat f = new SimpleDateFormat("HH:mm:ss", Locale.US);
            log("exit-info: Android " + android.os.Build.VERSION.RELEASE + " (SDK " + android.os.Build.VERSION.SDK_INT + "), "
                    + android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL + ", " + list.size() + " salidas previas");
            for (android.app.ApplicationExitInfo e : list) {
                log("exit-info: pid " + e.getPid() + " a las " + f.format(new Date(e.getTimestamp()))
                        + " motivo=" + e.getReason() + " estado=" + e.getStatus() + " importancia=" + e.getImportance()
                        + " pss=" + e.getPss() / 1024 + "MB desc=" + e.getDescription());
                if (e.getReason() == android.app.ApplicationExitInfo.REASON_CRASH_NATIVE
                        || e.getReason() == android.app.ApplicationExitInfo.REASON_ANR) {
                    try (InputStream in = e.getTraceInputStream()) {
                        if (in == null) continue;
                        File out = new File(logFile.getParentFile(), "traza_" + e.getPid() + ".txt");
                        if (out.exists()) continue;
                        try (OutputStream o = new FileOutputStream(out)) {
                            byte[] b = new byte[8192]; int n; long tot = 0;
                            while ((n = in.read(b)) > 0 && tot < 2_000_000) { o.write(b, 0, n); tot += n; }
                        }
                        log("exit-info: traza guardada en " + out.getName());
                    }
                }
            }
            log("exit-info: motivos 1=EXIT_SELF 2=SIGNALED 3=LOW_MEMORY 4=CRASH 5=CRASH_NATIVE 6=ANR 7=INIT_FAILURE "
                    + "10=USER_REQUESTED 11=USER_STOPPED 13=OTHER 14=FREEZER");
        } catch (Throwable t) { log("exit-info ERROR: " + t); }
    }

    /** Durante 90 s guarda cada 5 s la pila de los hilos "main" y "UnityMain", para ver dónde se cuelga el arranque. */
    static void watchdog() {
        Map<String, String> last = new HashMap<>();
        for (int i = 0; i < 18; i++) {
            try { Thread.sleep(5000); } catch (InterruptedException e) { return; }
            for (Map.Entry<Thread, StackTraceElement[]> e : Thread.getAllStackTraces().entrySet()) {
                String name = e.getKey().getName();
                if (!name.equals("main") && !name.equals("UnityMain")) continue;
                StringBuilder sb = new StringBuilder();
                StackTraceElement[] st = e.getValue();
                for (int k = 0; k < Math.min(st.length, 14); k++) sb.append("\n      at ").append(st[k]);
                String s = sb.toString();
                if (s.equals(last.get(name))) { log("[vigilante " + (i + 1) * 5 + "s] " + name + " " + e.getKey().getState() + " (igual que antes)"); continue; }
                last.put(name, s);
                log("[vigilante " + (i + 1) * 5 + "s] " + name + " " + e.getKey().getState() + s);
            }
        }
    }

    static final String VERSION = "v26";

    /** Comprueba en la libil2cpp.so instalada si están los parches (bytes en direcciones conocidas). */
    static void checkPatches(Context ctx) {
        String[][] checks = {
            {"registro de excepción del CMS", "14F7BA8", "800240f9"},
            {"asserts del parser -> log", "143AA7C", "22000014"},
            {"sin Invoke de [CMSParseFunction]", "1E6BBC4", "e0031faa"},
            {"sin Invoke de ParseListToDictionary", "1E6C6BC", "f3031faa"},
        };
        try (RandomAccessFile f = new RandomAccessFile(new File(ctx.getApplicationInfo().nativeLibraryDir, "libil2cpp.so"), "r")) {
            for (String[] c : checks) {
                f.seek(Long.parseLong(c[1], 16)); byte[] b = new byte[4]; f.readFully(b);
                StringBuilder h = new StringBuilder(); for (byte x : b) h.append(String.format("%02x", x & 0xff));
                log("parche " + c[0] + ": " + (h.toString().equals(c[2]) ? "SÍ" : "NO (" + h + ")"));
            }
        } catch (Throwable t) { log("no pude revisar libil2cpp.so: " + t); }
    }

    /**
     * Guarda el logcat propio de la app (Android solo deja ver los logs del mismo UID) en un archivo por arranque.
     * Primero vuelca el búfer "crash" (incluye el cierre del arranque anterior) y luego sigue en vivo.
     */
    void captureLogcat() {
        if (logFile == null) return;
        final File dir = logFile.getParentFile();
        final String stamp = new SimpleDateFormat("HHmmss", Locale.US).format(new Date()) + "_" + android.os.Process.myPid();
        new Thread(() -> {
            try {
                File prevCrash = new File(dir, "logcat_" + stamp + "_crash_anterior.txt");
                Process p = new ProcessBuilder("logcat", "-d", "-b", "crash", "-v", "threadtime")
                        .redirectErrorStream(true).redirectOutput(prevCrash).start();
                p.waitFor();
                if (prevCrash.length() == 0) prevCrash.delete();
                File live = new File(dir, "logcat_" + stamp + ".txt");
                log("logcat en vivo -> " + live.getName());
                new ProcessBuilder("logcat", "-b", "main,system,crash", "-v", "threadtime")
                        .redirectErrorStream(true).redirectOutput(live).start();
            } catch (Throwable t) { log("ERROR capturando logcat: " + t); }
        }, "gpdiag-logcat").start();
    }

    void startAll(Context ctx) {
        SSLServerSocketFactory sslf = null;
        try {
            KeyStore ks = KeyStore.getInstance("PKCS12");
            try (InputStream in = ctx.getAssets().open("diag/server.p12")) {
                ks.load(in, "gpdiag".toCharArray());
            }
            KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            kmf.init(ks, "gpdiag".toCharArray());
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(kmf.getKeyManagers(), null, null);
            sslf = sc.getServerSocketFactory();
        } catch (Throwable t) { log("ERROR cargando llave TLS: " + t); }

        List<String> lines = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(ctx.getAssets().open("diag/ports.txt")))) {
            String l; while ((l = r.readLine()) != null) { l = l.trim(); if (!l.isEmpty() && !l.startsWith("#")) lines.add(l); }
        } catch (IOException e) { log("ERROR leyendo ports.txt: " + e); }
        try { ctx.getAssets().open("diag/cms_var_0.json").close(); Catapult.bisect = true; log("modo BISECCIÓN del CMS (8 variantes)"); }
        catch (IOException e) { /* sin bisección */ }
        try { Catapult.loadResponses(ctx.getAssets().open("diag/responses.tsv")); log("respuestas del gateway: " + Catapult.RESPONSES.size()); }
        catch (IOException e) { log("sin diag/responses.tsv: " + e); }
        try { Catapult.loadTags(ctx.getAssets().open("diag/tags.tsv")); log("tags Catapult: " + Catapult.TAGS.size()); }
        catch (IOException e) { log("sin diag/tags.tsv: " + e); }

        for (String l : lines) {
            String[] p = l.split("\\s+");
            int port = Integer.parseInt(p[0]);
            boolean tls = p.length > 1 && p[1].equals("tls");
            String label = p.length > 2 ? p[2] : ("p" + port);
            final SSLServerSocketFactory f = sslf;
            new Thread(() -> listen(port, tls, label, f), "gpdiag-" + label).start();
        }
    }

    void listen(int port, boolean tls, String label, SSLServerSocketFactory sslf) {
        try {
            InetAddress any = InetAddress.getByName("0.0.0.0");
            ServerSocket ss;
            if (tls) {
                SSLServerSocket s = (SSLServerSocket) sslf.createServerSocket(port, 50, any);
                try {
                    SSLParameters sp = s.getSSLParameters();
                    sp.setApplicationProtocols(new String[]{"h2", "http/1.1"});
                    s.setSSLParameters(sp);
                } catch (Throwable t) { log("[" + label + "] sin ALPN en este Android: " + t); }
                ss = s;
            } else {
                ss = new ServerSocket(port, 50, any);
            }
            log("[" + label + "] escuchando en " + port + (tls ? " (TLS)" : " (texto plano)"));
            while (true) {
                Socket c = ss.accept();
                new Thread(() -> handle(c, label), "gpdiag-conn").start();
            }
        } catch (Throwable t) {
            log("[" + label + "] ERROR al escuchar en " + port + ": " + t);
        }
    }

    void handle(Socket c, String label) {
        String who = "[" + label + " " + c.getInetAddress().getHostAddress() + ":" + c.getPort() + "]";
        try {
            c.setSoTimeout(120000);
            String alpn = "";
            if (c instanceof SSLSocket) {
                SSLSocket s = (SSLSocket) c;
                // En Android (Conscrypt) el ALPN del SSLServerSocket no se hereda: se pone en cada socket aceptado.
                try {
                    SSLParameters sp = s.getSSLParameters();
                    sp.setApplicationProtocols(new String[]{"h2", "http/1.1"});
                    s.setSSLParameters(sp);
                } catch (Throwable t) { log(who + " no se pudo poner ALPN: " + t); }
                s.startHandshake();
                try { alpn = s.getApplicationProtocol(); } catch (Throwable ignored) { }
                String sni = "";
                try {
                    ExtendedSSLSession es = (ExtendedSSLSession) s.getSession();
                    for (SNIServerName n : es.getRequestedServerNames())
                        if (n instanceof SNIHostName) sni = ((SNIHostName) n).getAsciiName();
                } catch (Throwable ignored) { }
                log(who + " TLS ok " + s.getSession().getProtocol() + " alpn=" + alpn + " sni=" + sni);
            } else {
                log(who + " conexión");
            }
            BufferedInputStream in = new BufferedInputStream(c.getInputStream());
            OutputStream out = c.getOutputStream();
            in.mark(24);
            byte[] pre = new byte[24];
            int n = readUpTo(in, pre);
            in.reset();
            if (n == 24 && new String(pre, StandardCharsets.US_ASCII).startsWith("PRI * HTTP/2.0")) {
                new H2(who, in, out).run();
            } else {
                http1(who, in, out);
            }
        } catch (Throwable t) {
            log(who + " cerrada: " + t);
        } finally {
            try { c.close(); } catch (IOException ignored) { }
        }
    }

    static int readUpTo(InputStream in, byte[] b) throws IOException {
        int off = 0;
        while (off < b.length) { int r = in.read(b, off, b.length - off); if (r < 0) break; off += r; }
        return off;
    }

    static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        int ch;
        while ((ch = in.read()) >= 0 && ch != '\n') if (ch != '\r') b.write(ch);
        if (ch < 0 && b.size() == 0) return null;
        return b.toString("ISO-8859-1");
    }

    static Context appCtx;

    /** CMS: primero files/cms.json del teléfono (para probar sin reinstalar), si no assets/diag/cms.json. */
    static byte[] loadCms() { return loadCms(true); }

    /** ETag del CMS: cambia cuando cambia el contenido, así el cliente lo vuelve a descargar. */
    static String cmsEtag() {
        byte[] b = loadCms(false);
        if (b == null) return "gprevival-0";
        java.util.zip.CRC32 c = new java.util.zip.CRC32(); c.update(b);
        return "gprevival-" + Long.toHexString(c.getValue()) + "-" + b.length;
    }

    static byte[] loadCms(boolean verbose) {
        try {
            if (Catapult.bisect) {
                InputStream bi = appCtx.getAssets().open("diag/cms_var_" + Catapult.bisectV + ".json");
                ByteArrayOutputStream bb = new ByteArrayOutputStream(); byte[] bbuf = new byte[65536]; int bn;
                try (InputStream i = bi) { while ((bn = i.read(bbuf)) > 0) bb.write(bbuf, 0, bn); }
                if (verbose) log("CMS servido: BISECCIÓN variante " + Catapult.bisectV + ", " + bb.size() + " bytes");
                return bb.toByteArray();
            }
            File ext = logFile == null ? null : new File(logFile.getParentFile(), "cms.json");
            InputStream in = (ext != null && ext.isFile()) ? new FileInputStream(ext) : appCtx.getAssets().open("diag/cms.json");
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            byte[] buf = new byte[65536]; int n;
            try (InputStream i = in) { while ((n = i.read(buf)) > 0) b.write(buf, 0, n); }
            if (verbose) log("CMS servido desde " + ((ext != null && ext.isFile()) ? ext.getName() + " (teléfono)" : "assets/diag/cms.json") + ", " + b.size() + " bytes");
            return b.toByteArray();
        } catch (Throwable t) { log("sin CMS para servir: " + t); return null; }
    }

    void http1(String who, InputStream in, OutputStream out) throws IOException {
        while (true) {
            String req = readLine(in);
            if (req == null || req.isEmpty()) return;
            String host = "", ua = ""; long len = 0;
            String h;
            StringBuilder all = new StringBuilder();
            while ((h = readLine(in)) != null && !h.isEmpty()) {
                all.append(" | ").append(h);
                String lh = h.toLowerCase(Locale.US);
                if (lh.startsWith("host:")) host = h.substring(5).trim();
                else if (lh.startsWith("content-length:")) len = Long.parseLong(h.substring(15).trim());
                else if (lh.startsWith("user-agent:")) ua = h.substring(11).trim();
            }
            long skipped = 0;
            while (skipped < len) { long s = in.skip(len - skipped); if (s <= 0) break; skipped += s; }
            log(who + " HTTP " + req + " host=" + host + " cuerpo=" + len + " ua=" + ua);
            log(who + "   encabezados" + all);
            if (req.startsWith("GET /cms/content")) {
                byte[] cms = loadCms();
                if (cms != null) {
                    out.write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + cms.length + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
                    out.write(cms);
                    out.flush();
                    continue;
                }
            }
            byte[] body = "gpdiag: sin datos todavia\n".getBytes(StandardCharsets.US_ASCII);
            out.write(("HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: " + body.length + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
            out.write(body);
            out.flush();
        }
    }

    /** HTTP/2 mínimo: solo lo necesario para leer encabezados gRPC y contestar UNIMPLEMENTED. */
    static class H2 {
        final String who; final DataInputStream in; final OutputStream out;
        final Hpack hpack = new Hpack();
        final Map<Integer, String> paths = new HashMap<>();
        final Map<Integer, Long> sizes = new HashMap<>();
        final Map<Integer, ByteArrayOutputStream> bufs = new HashMap<>();
        final Set<Integer> headersSent = new HashSet<>();
        static final String CATAPULT_PATH = "/GrpcTransport/raw";
        H2(String who, InputStream in, OutputStream out) { this.who = who; this.in = new DataInputStream(in); this.out = out; }

        /** Envía un mensaje gRPC por un stream abierto (encabezados de respuesta la primera vez). */
        void sendGrpc(int stream, byte[] msg) throws IOException {
            if (headersSent.add(stream)) {
                ByteArrayOutputStream b = new ByteArrayOutputStream();
                b.write(0x88); // :status 200
                lit(b, "content-type", "application/grpc");
                frame(0x1, 0x4, stream, b.toByteArray());
            }
            byte[] d = new byte[5 + msg.length];
            d[1] = (byte) (msg.length >>> 24); d[2] = (byte) (msg.length >>> 16); d[3] = (byte) (msg.length >>> 8); d[4] = (byte) msg.length;
            System.arraycopy(msg, 0, d, 5, msg.length);
            frame(0x0, 0, stream, d);
            log(who + " -> enviado gRPC stream=" + stream + " bytes=" + msg.length);
        }

        /** El cliente cerró su lado: trailers con grpc-status 0. */
        void closeOk(int stream) throws IOException {
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            if (headersSent.add(stream)) { b.write(0x88); lit(b, "content-type", "application/grpc"); }
            lit(b, "grpc-status", "0");
            frame(0x1, 0x4 | 0x1, stream, b.toByteArray());
            log(who + " stream " + stream + " cerrado por el cliente");
            paths.remove(stream); bufs.remove(stream);
        }

        void run() throws IOException {
            byte[] pre = new byte[24]; in.readFully(pre);
            frame(0x4, 0, 0, new byte[0]); // SETTINGS vacío
            ByteArrayOutputStream hdrBuf = null; int hdrStream = 0; int hdrFlags = 0;
            while (true) {
                int len = (in.readUnsignedByte() << 16) | (in.readUnsignedByte() << 8) | in.readUnsignedByte();
                int type = in.readUnsignedByte(); int flags = in.readUnsignedByte();
                int stream = in.readInt() & 0x7fffffff;
                byte[] p = new byte[len]; in.readFully(p);
                switch (type) {
                    case 0x0: { // DATA
                        int pad = (flags & 0x8) != 0 ? (p[0] & 0xff) + 1 : 0;
                        int off = (flags & 0x8) != 0 ? 1 : 0;
                        int dlen = len - pad;
                        sizes.merge(stream, (long) dlen, Long::sum);
                        if (len > 0) { windowUpdate(0, len); windowUpdate(stream, len); }
                        String path = paths.get(stream);
                        if (CATAPULT_PATH.equals(path)) {
                            // Transporte duplex de Catapult: se juntan los mensajes gRPC y se contestan sin cerrar el stream.
                            ByteArrayOutputStream buf = bufs.computeIfAbsent(stream, k -> new ByteArrayOutputStream());
                            buf.write(p, off, dlen);
                            byte[] all = buf.toByteArray(); int pos = 0;
                            while (all.length - pos >= 5) {
                                int mlen = ((all[pos + 1] & 0xff) << 24) | ((all[pos + 2] & 0xff) << 16) | ((all[pos + 3] & 0xff) << 8) | (all[pos + 4] & 0xff);
                                if (all.length - pos - 5 < mlen) break;
                                byte[] msg = Arrays.copyOfRange(all, pos + 5, pos + 5 + mlen);
                                pos += 5 + mlen;
                                for (byte[] r : Catapult.handle(who, path, msg)) sendGrpc(stream, r);
                            }
                            buf.reset(); buf.write(all, pos, all.length - pos);
                            if ((flags & 0x1) != 0) closeOk(stream);
                            break;
                        }
                        if (dlen > 0) {
                            StringBuilder hx = new StringBuilder();
                            for (int i = off; i < off + Math.min(dlen, 48); i++) hx.append(String.format("%02x", p[i] & 0xff));
                            log(who + " DATA stream=" + stream + " " + paths.getOrDefault(stream, "?") + " bytes=" + dlen + " hex=" + hx + (dlen > 48 ? "…" : ""));
                        }
                        // Rutas desconocidas: se responde UNIMPLEMENTED tras el primer mensaje.
                        if (paths.containsKey(stream) && (dlen > 0 || (flags & 0x1) != 0)) finish(stream);
                        break;
                    }
                    case 0x1: { // HEADERS
                        int off = 0, end = len;
                        if ((flags & 0x8) != 0) { end -= (p[0] & 0xff); off = 1; }
                        if ((flags & 0x20) != 0) off += 5;
                        hdrBuf = new ByteArrayOutputStream(); hdrBuf.write(p, off, end - off);
                        hdrStream = stream; hdrFlags = flags;
                        if ((flags & 0x4) != 0) { headers(hdrStream, hdrBuf.toByteArray(), hdrFlags); hdrBuf = null; }
                        break;
                    }
                    case 0x9: { // CONTINUATION
                        if (hdrBuf != null) hdrBuf.write(p);
                        if ((flags & 0x4) != 0 && hdrBuf != null) { headers(hdrStream, hdrBuf.toByteArray(), hdrFlags); hdrBuf = null; }
                        break;
                    }
                    case 0x4: if ((flags & 0x1) == 0) frame(0x4, 0x1, 0, new byte[0]); break; // SETTINGS -> ACK
                    case 0x6: if ((flags & 0x1) == 0) frame(0x6, 0x1, 0, p); break;           // PING -> PONG
                    case 0x7: log(who + " GOAWAY recibido"); return;
                    case 0x3: log(who + " RST_STREAM " + stream); break;
                    default: break;
                }
            }
        }

        void headers(int stream, byte[] block, int flags) throws IOException {
            List<String[]> hs;
            try { hs = hpack.decode(block); } catch (Throwable t) { log(who + " HPACK no decodificado: " + t); hs = new ArrayList<>(); }
            StringBuilder extra = new StringBuilder();
            String path = "?", auth = "";
            for (String[] h : hs) {
                if (h[0].equals(":path")) path = h[1];
                else if (h[0].equals(":authority")) auth = h[1];
                else if (!h[0].startsWith(":") && !h[0].equals("te") && !h[0].equals("content-type")
                        && !h[0].equals("user-agent") && !h[0].equals("grpc-accept-encoding") && !h[0].equals("accept-encoding"))
                    extra.append(' ').append(h[0]).append('=').append(h[1].length() > 80 ? h[1].substring(0, 80) + "…(" + h[1].length() + ")" : h[1]);
            }
            paths.put(stream, path);
            log(who + " gRPC inicia " + path + " authority=" + auth + extra);
            if ((flags & 0x1) != 0) finish(stream);
        }

        void finish(int stream) throws IOException {
            String path = paths.getOrDefault(stream, "?");
            long bytes = sizes.getOrDefault(stream, 0L);
            String[] sm = path.replaceFirst("^/", "").split("/", 2);
            log(who + " gRPC LLAMADA servicio=" + sm[0] + " metodo=" + (sm.length > 1 ? sm[1] : "?")
                    + " bytes=" + bytes + " (mensaje ≈ " + Math.max(0, bytes - 5) + ")");
            // Respuesta: HEADERS (:status 200, content-type) y trailers con grpc-status 12 en un solo bloque (Trailers-Only).
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            b.write(0x88); // :status 200 (índice estático 8)
            lit(b, "content-type", "application/grpc");
            lit(b, "grpc-status", "12");
            lit(b, "grpc-message", "gpdiag sin implementar");
            frame(0x1, 0x4 | 0x1, stream, b.toByteArray());
            paths.remove(stream); sizes.remove(stream);
        }

        static void lit(ByteArrayOutputStream b, String k, String v) {
            b.write(0x00); str(b, k); str(b, v);
        }
        static void str(ByteArrayOutputStream b, String s) {
            byte[] x = s.getBytes(StandardCharsets.US_ASCII);
            if (x.length < 127) b.write(x.length); else { b.write(127); int v = x.length - 127; while (v >= 128) { b.write((v & 0x7f) | 0x80); v >>= 7; } b.write(v); }
            b.write(x, 0, x.length);
        }

        void windowUpdate(int stream, int inc) throws IOException {
            frame(0x8, 0, stream, new byte[]{(byte) (inc >>> 24), (byte) (inc >>> 16), (byte) (inc >>> 8), (byte) inc});
        }

        synchronized void frame(int type, int flags, int stream, byte[] p) throws IOException {
            byte[] h = {(byte) (p.length >> 16), (byte) (p.length >> 8), (byte) p.length, (byte) type, (byte) flags,
                    (byte) (stream >>> 24), (byte) (stream >>> 16), (byte) (stream >>> 8), (byte) stream};
            out.write(h); out.write(p); out.flush();
        }
    }

    // ContentProvider sin datos.
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public String getType(Uri u) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
