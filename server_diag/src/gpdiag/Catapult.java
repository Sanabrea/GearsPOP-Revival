package gpdiag;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * Protocolo Catapult (protobuf-net con herencia) sobre /GrpcTransport/raw.
 * Message = { 1: Headers (repetido MessageHeader), <etiqueta del subtipo>: cuerpo }.
 * MessageHeader -> OperationHeader (51110556) = { 1: RequestId (bcl.Guid), 2: Type (1 OneWay, 2 Request, 3 Reply) }.
 * Ver analysis/protocolo/.
 */
class Catapult {
    static final int MSG_LOGIN_REQUEST = 71269765;          // Message<LoginRequest> { 1: LoginRequest }
    static final int RESULT_SESSION_TOKEN = 15174312;       // Result<SessionTokenResponse> { 1: Body, 2: Error }
    static final int HDR_OPERATION = 51110556;
    static final int MSG_AUTH_REQUEST = 80982860;         // Message<AuthenticationRequest>
    static final int RESULT_AUTH_RESPONSE = 98996885;     // Result<AuthenticationResponse>
    static final int MSG_GET_ALL_PLAYER_DATA = 89838755;  // Message<GetAllPlayerDataQuery>
    static final int RESULT_ALL_PLAYER_DATA = 63841553;   // Result<AllPlayerDataDto>
    static final int OP_REPLY = 3;

    static Map<Integer, String> TAGS = new HashMap<>();
    /** etiqueta de la petición -> {etiqueta del Result, cuerpo, nombre} */
    static Map<Integer, Object[]> RESPONSES = new HashMap<>();

    static void loadResponses(InputStream in) {
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String l;
            while ((l = r.readLine()) != null) {
                String[] p = l.split("\t");
                if (p.length < 3 || !p[0].matches("\\d+")) continue;
                RESPONSES.put(Integer.parseInt(p[0]), new Object[]{Integer.parseInt(p[1]), android.util.Base64.decode(p[2], 0), p.length > 3 ? p[3] : ""});
            }
        } catch (Exception e) { DiagProvider.log("responses.tsv no cargado: " + e); }
    }
    static boolean bisect = false;
    static int bisectV = 0, bisectMatches = 0;
    static final int ERR_CONTENT_UPDATE_REQUIRED = 471;   // CatapultStatusCode.ContentUpdateRequired
    static final String CONTENT_URL = "http://127.0.0.1:8080/cms/content"; // HTTP plano: el WebClient de Mono no negocia TLS 1.2 con Android 16
    static final String CONTENT_VERSION = "1";

    static void loadTags(InputStream in) {
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String l;
            while ((l = r.readLine()) != null) {
                if (l.startsWith("#")) continue;
                String[] p = l.split("\t");
                if (p.length >= 2 && p[0].matches("\\d+")) TAGS.put(Integer.parseInt(p[0]), p[1]);
            }
        } catch (Exception e) { DiagProvider.log("tags.tsv no cargado: " + e); }
    }

    static String name(int tag) { String n = TAGS.get(tag); return n != null ? n : ("tipo#" + tag); }

    /** Campo protobuf crudo. */
    static class Field { int num, wt; long v; byte[] b; }

    static List<Field> parse(byte[] d) {
        List<Field> out = new ArrayList<>();
        int[] p = {0};
        while (p[0] < d.length) {
            long key = varint(d, p);
            Field f = new Field(); f.num = (int) (key >>> 3); f.wt = (int) (key & 7);
            switch (f.wt) {
                case 0: f.v = varint(d, p); break;
                case 1: f.b = Arrays.copyOfRange(d, p[0], p[0] + 8); p[0] += 8; break;
                case 2: { int len = (int) varint(d, p); f.b = Arrays.copyOfRange(d, p[0], p[0] + len); p[0] += len; break; }
                case 5: f.b = Arrays.copyOfRange(d, p[0], p[0] + 4); p[0] += 4; break;
                default: throw new IllegalStateException("tipo de cable " + f.wt);
            }
            out.add(f);
        }
        return out;
    }

    static long varint(byte[] d, int[] p) {
        long v = 0; int s = 0;
        while (true) { int c = d[p[0]++] & 0xff; v |= (long) (c & 0x7f) << s; if (c < 0x80) return v; s += 7; }
    }

    static String str(List<Field> fs, int num) {
        for (Field f : fs) if (f.num == num && f.wt == 2) return new String(f.b, StandardCharsets.UTF_8);
        return null;
    }

    static String hex(byte[] b, int max) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Math.min(b.length, max); i++) sb.append(String.format("%02x", b[i] & 0xff));
        return sb + (b.length > max ? "…" : "");
    }

    /** Escritor protobuf mínimo. */
    static class W {
        final ByteArrayOutputStream o = new ByteArrayOutputStream();
        W varint(long v) { while ((v & ~0x7fL) != 0) { o.write((int) ((v & 0x7f) | 0x80)); v >>>= 7; } o.write((int) v); return this; }
        W key(int num, int wt) { return varint(((long) num << 3) | wt); }
        W bytes(int num, byte[] b) { key(num, 2); varint(b.length); o.write(b, 0, b.length); return this; }
        W str(int num, String s) { return s == null ? this : bytes(num, s.getBytes(StandardCharsets.UTF_8)); }
        W u(int num, long v) { key(num, 0); return varint(v); }
        byte[] done() { return o.toByteArray(); }
    }

    /**
     * Procesa un mensaje Catapult del cliente. Devuelve las respuestas (mensajes Catapult sin el prefijo gRPC).
     */
    static List<byte[]> handle(String who, String path, byte[] msg) {
        List<byte[]> replies = new ArrayList<>();
        List<Field> top;
        try { top = parse(msg); } catch (Throwable t) { DiagProvider.log(who + " protobuf inválido: " + t + " hex=" + hex(msg, 256)); return replies; }

        byte[] guid = null; long opType = -1; int bodyTag = -1; byte[] body = null;
        StringBuilder hdrs = new StringBuilder();
        for (Field f : top) {
            if (f.num == 1 && f.wt == 2) {
                for (Field h : parse(f.b)) {
                    hdrs.append(' ').append(name(h.num).replace("Headers.", ""));
                    if (h.num == HDR_OPERATION) {
                        for (Field o : parse(h.b)) { if (o.num == 1) guid = o.b; if (o.num == 2) opType = o.v; }
                    }
                }
            } else if (f.wt == 2) { bodyTag = f.num; body = f.b; }
        }
        String op = opType == 1 ? "OneWay" : opType == 2 ? "Request" : opType == 3 ? "Reply" : String.valueOf(opType);
        DiagProvider.log(who + " CATAPULT " + name(bodyTag) + " op=" + op + " bytes=" + msg.length + " headers=[" + hdrs.toString().trim() + "]"
                + (guid != null ? " requestId=" + hex(guid, 40) : ""));

        if (bodyTag == MSG_LOGIN_REQUEST && body != null) {
            List<Field> lr = null;
            for (Field f : parse(body)) if (f.num == 1 && f.wt == 2) lr = parse(f.b);
            if (lr != null) {
                String tok = str(lr, 2);
                DiagProvider.log(who + "   LoginRequest IdentityType=" + str(lr, 1) + " IdentityToken=" + (tok == null ? null : tok.length() + " caracteres")
                        + " ClientVersion=" + str(lr, 3) + " ContentETag=" + str(lr, 4) + " Platform=" + str(lr, 5));
            }
            // Flujo original de Catapult: si el ETag del cliente no coincide, se responde ContentUpdateRequired (471)
            // con ContentUrl/ContentEtag; ContentUpdateStep descarga el CMS, guarda el ETag y repite el login.
            String clientEtag = lr == null ? null : str(lr, 4);
            String CONTENT_ETAG = DiagProvider.cmsEtag();
            byte[] session = new W()
                    .str(1, "gprevival-session-1")          // SessionToken
                    .str(2, "gprevival-local-1")            // AccountId
                    .str(4, CONTENT_URL)                    // ContentUrl
                    .str(5, CONTENT_VERSION)                // ContentVersion
                    .str(6, CONTENT_ETAG)                   // ContentEtag
                    .done();
            W result = new W().bytes(1, session);
            if (!CONTENT_ETAG.equals(clientEtag)) {
                result.bytes(2, new W().u(1, ERR_CONTENT_UPDATE_REQUIRED).str(2, "ContentUpdateRequired")
                        .str(3, "gprevival: descargar CMS").done());
                DiagProvider.log(who + "   -> Result<SessionTokenResponse> con Error 471 ContentUpdateRequired (ETag cliente=" + clientEtag + ")");
            } else {
                DiagProvider.log(who + "   -> Result<SessionTokenResponse> OK (ETag al día)");
                if (bisect) {
                    bisectMatches++;
                    if (bisectMatches == 2) DiagProvider.log("BISECCIÓN: el parseo de ESTE intento usa la variante " + bisectV);
                    if (bisectMatches >= 2 && bisectV < 7) { bisectV++; bisectMatches = 0; }
                }
            }
            replies.add(reply(guid, RESULT_SESSION_TOKEN, result.done()));
        } else if (bodyTag == MSG_AUTH_REQUEST) {
            // Gateway: Message<AuthenticationRequest> {1: {1 Token, 2 ContentEtag, 3 ProtocolVersion, 4 ContinueSession}}
            //  -> Result<AuthenticationResponse> {1: {1 UserId}}
            replies.add(reply(guid, RESULT_AUTH_RESPONSE, new W().bytes(1, new W().str(1, "gprevival-local-1").done()).done()));
            DiagProvider.log(who + "   -> Result<AuthenticationResponse> (UserId gprevival-local-1)");
        } else if (RESPONSES.containsKey(bodyTag)) {
            // Respuestas por defecto armadas offline (scripts/build_responses.py -> assets/diag/responses.tsv)
            Object[] r = RESPONSES.get(bodyTag);
            replies.add(reply(guid, (Integer) r[0], (byte[]) r[1]));
            DiagProvider.log(who + "   -> " + name((Integer) r[0]) + " (" + ((byte[]) r[1]).length + " bytes, " + r[2] + ")");
        } else {
            DiagProvider.log(who + "   sin respuesta todavía; cuerpo hex=" + hex(body != null ? body : msg, 256));
        }
        return replies;
    }

    /** Message con OperationHeader Reply (mismo RequestId) y el cuerpo bajo la etiqueta del subtipo. */
    static byte[] reply(byte[] guid, int bodyTag, byte[] body) {
        W op = new W();
        if (guid != null) op.bytes(1, guid);
        op.u(2, OP_REPLY);
        byte[] header = new W().bytes(HDR_OPERATION, op.done()).done();
        return new W().bytes(bodyTag, body).bytes(1, header).done();
    }
}
