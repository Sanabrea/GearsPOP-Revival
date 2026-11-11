# Arranque del cliente (Gears POP! 1.98)

Fuente: volcado de Il2CppDumper v6.7.46 en `analysis/il2cpp_dump/` (`dump.cs`, `stringliteral.json`, `script.json`, `il2cpp.h`, `DummyDll/`).
Metadata v24.1. Direcciones = RVA dentro de `lib/arm64-v8a/libil2cpp.so`.

## 1. Config.json → `Mediatonic.Moncton.MonctonConfig`
- `LoadConfigFile()` (0x14EEDA0) lee `Config.json` de StreamingAssets mediante el delegado `OnLoadStreamingAssetDelegate`,
  y `LoadFromJson()` (0x14EF328) decodifica el base64 y saca las claves `environment`, `cms_url`, `loginEndpoint`,
  `battleEndpoint`, `gatewayEndpoint` (se guardan como `ObscuredString`, solo antitrampas en memoria).
- **Puertos fijos** en `MonctonConfig.Config..cctor` (0x14EF6D0, desensamblado):
  `LoginPort = 12000`, `GatewayPort = 12345`, `BattleGatewayPort = 11111`. No están en Config.json.
  Son mayores que 1024, así que una app sin root puede escucharlos.
- `ConnectionManager.OnMonctonConfigLoaded()` → `BuildCatapultConfig()` arma `CatapultConnection.Config`
  (`LoginServerEndpoint/Port`, `GatewayServerEndpoint/Port`, `SslCredentials`, timeouts, `ProtocolVersion`, `ClientVersion`).

## 2. TLS
- `ConnectionManager.LoadSslCredentials()` (corrutina) lee `"/certs/ca.crt"` de StreamingAssets y crea `Grpc.Core.SslCredentials(rootCerts)`.
  Sin certificado de cliente. gRPC-core valida la cadena **y el nombre** del destino, así que el certificado del servidor
  debe tener el SAN que se ponga en Config.json (para `127.0.0.1`, un SAN IP).
- No hay `grpc.ssl_target_name_override` entre los literales (solo `grpc.primary_user_agent`).
- El CMS va por otra vía: `GamefuelContentService` usa `System.Net.WebClient` (gzip) con su propio
  `ValidateRemoteCertificate` y guarda una copia en caché (`content_data`). `CheckForStaleCMS`/`LoadCachedContent` permiten
  arrancar con la caché: posible vía para inyectar el CMS reconstruido.

## 3. Canales gRPC → `Catapult.Network.CatapultConnection`
Máquina de estados `CatapultConnection.State`: Disconnected → **LoggingIn** → **ConnectingToGateway** → **Authenticating** →
**LoadingGameServices** → Connected.
- `CreateLoginNetClient()` (0x141BBE8): `NetClient` con `WithGrpcChannel(builder, "GrpcTransport", sslCredentials)` hacia
  `loginEndpoint:12000`. `Login()` manda `LoginRequest` (o `CreateAccountRequest`) y espera `SessionTokenResponse`.
- `ConnectToGateway()` → `CreateGatewayClient()` (0x141C69C) → canal a `gatewayEndpoint:12345` → `Authenticate()`
  (`AuthenticationRequest`/`AuthenticateRequest` con el token de sesión) → `LoadGameServices()`.
- Transporte: `GrpcNetConnection` abre **una sola llamada duplex** `AsyncDuplexStreamingCall<byte[], byte[]>` por canal
  y multiplexa mensajes Catapult (`Message`, con `RequestId` Guid y `KeepAliveMessage`). La serialización la da
  `IMessageSerializer` (cabeceras en `Catapult.Protocol.Headers`). No hay un servicio gRPC por RPC: el `:path` exacto
  lo registra el servidor de diagnóstico (el nombre de servicio por defecto es `GrpcTransport`).
- Hay restos de **MagicOnion** (`IMagicOnionEmbeddedHeartbeat/Connect`, `HeartbeatClient`).

### Mensajes de Login y Gateway (`Catapult.Services.*.Protocol.Client`)
- Login, peticiones: `LoginRequest`, `CreateAccountRequest`, `AddIdentityRequest`, `RemoveIdentityRequest`,
  `RemoveAndAddIdentityRequest`, `LookupIdentityRequest`, `ForgetAccountRequest`.
- Login, respuestas: `SessionTokenResponse`, `AccountResponse`, `AccountsResponse`, `IdentityResponse`, `IdentitiesResponse`,
  `LookupIdentityResponse`, `ForgetAccountResponse`.
- Gateway: `AuthenticationRequest/Response`, `TimestampRequest/Response`, `KeepAliveMessage`, `ContentUpdateNotification`,
  `LogAnalyticsEventCommand(s)`.
- Servicios remotos sobre el gateway: `LoginRemoteService`, `AuthenticationRemoteService`, `ContentRemoteService`,
  `PlayerRemoteService` (Bounties, Clans, Features, Leaderboard, Achievements, Cards, DailyLoginReward, GearPacks…),
  `BattleRemoteService`, `BattleServerInfoRemoteService`, `BootcampRemoteService`, `StoreRemoteService`, `AnalyticsRemoteService`.

## 4. Xbox Live (XAL)
- `XalService` (wrapper de `libXal.Unity.so`): `Initialize`, `TryAddFirstUserSilentAsync`, `AddUserWithUiAsync`
  (WebView con `SetPlatformWebViewEventHandler`), `XalUser`.
- La credencial de login es un `LoginCredential { CredentialTypeId, Value }`. Literales: `device_id`/`DeviceId`, `xbox`,
  `anonymous`. `ConnectionManager.SetCorrectCredentialsToLogIn()` elige cuál usar; Xbox se suma como identidad extra
  (`HandleExtraIdentities`, `AddIdentityRequest`) y el aviso para iniciar sesión depende del CMS (`XblAuthentificationPromptDates`).
  Hipótesis a confirmar: el primer login es por **device id**, sin Xbox.

## 5. Orden de arranque esperado
1. Unity → `MonctonConfig.LoadConfigFile()` → `ConnectionManager.OnMonctonConfigLoaded()`.
2. `LoadSslCredentials()` (lee `certs/ca.crt`).
3. `BeginLogin()` → `LoginFlowRoutine` → `CatapultConnection.Connect()` → login (12000) → gateway (12345) → autenticación.
4. `ContentRemoteService` entrega los detalles del CMS → `GamefuelContentService.DownloadContent(url)` →
   `CMSManager.LoadCMSData(data, isInitialLogin, callback)` → `ParseCMSData` / `OnCMSLoadCompleted`.
5. `HandleConnected()` → menú. Errores: `error_unabletologin`, mantenimiento, actualización obligatoria.

## 6. Entrega 0: APK de diagnóstico (`build/GearsPOP_diag.apk`)
Ruta elegida: **servidor embebido en el APK** (no hizo falta el plan B en la Mac).
- `assets/Config.json`: todos los endpoints a `127.0.0.1`; `cms_url` = `https://127.0.0.1:8443/cms/projects/moncton/branches/production/groups`.
- `assets/certs/ca.crt`: CA propia (`build/keys/ca.crt`). El servidor usa `build/keys/server.p12`
  (SAN: IP 127.0.0.1, localhost y los 5 hosts originales).
- Servidor: `server_diag/src/gpdiag/` (Java puro, sin dependencias, compilado a `classes2.dex`).
  Un `ContentProvider` (`gpdiag.DiagProvider`) arranca con el proceso, antes de la Activity de Unity, así que no se tocó código del juego.
  Escucha según `assets/diag/ports.txt`: 12000 login, 12345 gateway, 11111 battle, 8443 CMS (todos TLS con ALPN h2) y 8080 HTTP plano.
  Registra handshake TLS (versión, ALPN, SNI), cada llamada gRPC (`:path` → servicio/método, `:authority`, metadatos y bytes)
  y cada petición HTTP/1.1. A gRPC responde `grpc-status 12 UNIMPLEMENTED`; a HTTP, 404.
- Log: logcat con etiqueta `GPDiag` y archivo `/sdcard/Android/data/com.microsoft.gearspop/files/gpdiag.log`.
- Firma propia: `build/keys/sign.jks` (clave `gpdiag-sign`). minSdk subido a 24 (el original decía 19).
- Recompilar: `build/work/dec` es el APK decodificado con `apktool d -s`; los pasos están en la sección 7.

### Instalación en el teléfono
`adb` está en `/opt/homebrew/share/android-commandlinetools/platform-tools/adb`. Activa la depuración USB.
1. Respaldo (si existe la carpeta): `adb pull /sdcard/Android/data/com.microsoft.gearspop backup_gearspop/`.
   Puede traer modelos en caché (Kait, Carmine, Decoy, Barrier). En Android 14+ adb puede no tener acceso: entonces cópiala con un administrador de archivos o desde la PC con MTP.
2. Solo después del respaldo: `adb uninstall com.microsoft.gearspop` (la firma es distinta y Android no permite instalar encima).
3. `adb install build/GearsPOP_diag.apk`
4. `adb logcat -c && adb logcat -s GPDiag:V Unity:V CatapultNet:V grpc:V AndroidRuntime:E`
5. Abre el juego, espera ~1 minuto y luego `adb pull /sdcard/Android/data/com.microsoft.gearspop/files/gpdiag.log`.

### Resultado
**Prueba 1 (10 nov 2026, 12:26, teléfono del usuario):** el servidor arranca bien (los 5 puertos escuchan),
pero el proceso inicia 3 veces en 17 s (pids 3165, 5215, 9052) y **no llega ninguna conexión**.
O el juego se cierra antes de la red, o el usuario lo abrió varias veces. Falta el logcat para saber la causa.
**v2 del APK:** el servidor ahora guarda el logcat propio en `files/logcat_<hora>_<pid>.txt`, más el búfer de crash
del arranque anterior (`..._crash_anterior.txt`) y cualquier crash de Java en `gpdiag.log`.

**Prueba 2 (12:31, v2):** la primera prueba no fue un crash; eran reinicios de la app.
- Unity arranca, carga Firebase y AppsFlyer, borra el CMS viejo ("unique id has changed") y carga `libgrpc_csharp_ext.so`.
- El cliente **sí llega al login**: 10 conexiones a `127.0.0.1:12000`, una por segundo. TLS 1.2 ok y SNI `127.0.0.1`,
  así que la CA propia y `Config.json` funcionan.
- Se corta porque **`alpn=null`**: gRPC exige `h2` y cierra la conexión. Después aparece `ErrorMessageUI`.
  Causa: en Conscrypt el ALPN del `SSLServerSocket` no se hereda. **v3:** se pone en cada socket aceptado.
- También pide `moncton-service-status-prod.azurewebsites.net` (estado/mantenimiento, por HTTPS desde Java); falla con UnknownHost
  y no parece bloquear. Habrá que servirlo o redirigirlo más adelante.
- Braze da `invalid_api_key` (es inofensivo).

**Prueba 3 (12:39, v3):** **ALPN ok (`alpn=h2`)**. El cliente manda el preface HTTP/2, pero el servidor truena con
`ExceptionInInitializerError` / `NoClassDefFoundError: gpdiag.Hpack`: la tabla Huffman se armaba antes de inicializar los arreglos.
Del lado del cliente, gRPC registra `SSL_read returned 0 unexpectedly` / `TSI_INTERNAL_ERROR` y luego `ErrorMessageUI`.
**v4:** la tabla se arma al primer uso y se registra cada mensaje DATA (bytes y 48 bytes en hex); se responde UNIMPLEMENTED
tras el primer mensaje, porque el transporte es duplex. Probado en la Mac con `curl --http2-prior-knowledge` y con el
ejemplo C.4.1 del RFC 7541 (Huffman).

**Prueba 4 (12:47, v4): entrega 0 cumplida.** El juego abre, intenta el login y queda registrado qué pide:
- Conexión: `127.0.0.1:12000`, TLS 1.2, ALPN `h2`. **Ruta gRPC: `/GrpcTransport/raw`** (servicio `GrpcTransport`, método `raw`),
  llamada duplex `byte[]`. Metadatos extra: ninguno.
- Primer mensaje: 216 bytes en DATA = prefijo gRPC (`00` + longitud `0x000000d3` = 211) + mensaje Catapult de 211 bytes:
  ```
  aad8ef8f 02 9301 | 0a 9001 0a08 "DeviceId" 12 58 "KRu6MNFidMJdWWFu7MaSh…"
  ```
  Lectura provisional: 4 bytes de id de tipo (`0x8fefd8aa` LE, sería `LoginRequest`), un byte `02`, varint 147 = largo del
  cuerpo protobuf; dentro va el `LoginCredential` (campo 1 = `CredentialTypeId` "DeviceId", campo 2 = `Value` de 88 caracteres).
  Los 57 bytes restantes quedan por identificar (cabeceras: versión de cliente, plataforma, RequestId…).
- **El login es por `DeviceId`: no pide Xbox Live** ni abre XAL antes del login.
- Dónde se detiene: ante `grpc-status 12` el cliente manda `RST_STREAM`, reintenta cada ~1.2 s y termina en `ErrorMessageUI`.
- Siguiente paso (entrega 1): decodificar el formato de mensaje Catapult (`IMessageSerializer`, `Catapult.Protocol.Headers`)
  y responder un `SessionTokenResponse` para pasar al gateway (12345).

### Problema: el primer arranque se congela
El usuario reporta que el primer arranque se queda congelado y se cierra (sigue en segundo plano); al minuto carga y muestra el error de conexión.
- En el logcat de la prueba 4, los arranques 9907 (12:45:03) y 9734 (12:45:26) se callan **en el mismo punto**: después de
  `#EnvironmentSelector# Saving last environment as: Production` (y `Using memoryadresses from more that 16GB of memory`).
  No hay crash ni ANR en el log propio de la app.
- En el arranque que funciona (12325), 330 ms después de esa línea viene `UNLOADING SCENE: LoadingScene`, y luego gRPC y el login.
  Ese proceso nació a las 12:46:04 en segundo plano (Android lo relanzó) y la Activity se abrió a las 12:47:16.
- Sospechas: una llamada de Unity a Java que se bloquea en el arranque en frío (TextToSpeech de accesibilidad, AppsFlyer, Firebase,
  la lectura de StreamingAssets) o algo propio de MIUI. Falta saber si el APK original hace lo mismo.
- **v5:** el servidor incluye un vigilante que guarda en `gpdiag.log`, cada 5 s durante 90 s, la pila Java de `main` y `UnityMain`.
- **Prueba 5 (12:53, v5):** el arranque en frío (pid 12255) no alcanzó a escribir ni un registro del vigilante (5 s): el proceso
  entero murió o quedó congelado en menos de 5 s. Android relanzó el proceso en segundo plano (19794, 12:53:41), sin `UnityMain`
  durante 60 s. Al reabrir el juego (12:54:45), Unity arrancó en ese proceso ya iniciado y el login salió al instante.
  **Conclusión:** solo falla cuando el proceso y la Activity arrancan juntos. Pista: en los arranques que fallan, la última línea es
  `Using memoryadresses from more that 16GB of memory`; en el que funciona (12325) esa línea no aparece.
- **v6:** al arrancar, guarda `ApplicationExitInfo` (motivo de salida de los procesos anteriores) y, si fue crash nativo o ANR,
  el tombstone en `files/traza_<pid>.txt`.
- **Prueba 6 (13:40, v6): causa encontrada.** Teléfono Xiaomi 2311DRK48G con **Android 16 (SDK 36)**. Todos los arranques que fallan
  salen con `REASON_SIGNALED`, estado 11 = **SIGSEGV**, en primer plano, 1–2 s después de abrir, y sin tombstone. En los arranques
  más recientes falla casi siempre.
- **Mecanismo** (`libunity.so`, 0x741684): Unity 2018.4 registra cada bloque de memoria en una tabla con **5 casillas** indexadas
  por `dirección >> 32` (4 GB por casilla). En Android 16 el asignador reparte la memoria en más de 5 zonas de 4 GB. Al llegar la
  sexta, Unity escribe `Using memoryadresses from more that 16GB of memory`, usa el índice -1 (lee el contador en +0xa0 como
  puntero) y truena. Que a veces funcione depende de cómo ASLR coloque la memoria.
- **v7:** `scripts/patch_libunity_16gb.py` parchea 13 instrucciones de las 3 funciones de la tabla (consulta 0x7415b8,
  registro 0x741684, baja 0x7418dc): la clave pasa a `>> 35` (32 GB por casilla, 160 GB en total) y la tabla raíz a 1024 entradas,
  con el contador en +0x2000. El script verifica los bytes originales. Las otras 9 apariciones de `ubfx #25, #7` en la librería
  son otro código (texturas).
- **Prueba 7 (13:53, v7): corregido.** 3 arranques en frío seguidos (pids 13244, 14089, 15670): los 3 llegan al login a los
  ~2.5 s, sin ninguna salida SIGSEGV (las salidas registradas son `SwipeUpClean`, cuando el usuario cierra la app).
  La pantalla muestra "LOGGING IN… 5%" y luego el diálogo "Gears POP! encountered an error. Please check your internet connection".
  El parche de `libunity.so` queda como parte fija del cliente.

## 7. Cómo reconstruir el APK
```
javac --release 8 -cp $SDK/platforms/android-34/android.jar -d build/server_diag/classes server_diag/src/gpdiag/*.java
d8 --min-api 24 --lib $SDK/platforms/android-34/android.jar --output build/server_diag/dex build/server_diag/classes/gpdiag/*.class
python3 -I scripts/patch_libunity_16gb.py <libunity.so original> build/work/dec/lib/arm64-v8a/libunity.so
apktool b -o build/work/unsigned.apk build/work/dec
cp build/server_diag/dex/classes.dex build/work/classes2.dex && (cd build/work && zip -q unsigned.apk classes2.dex)
zipalign -f -p 4 build/work/unsigned.apk build/work/aligned.apk
apksigner sign --ks build/keys/sign.jks --ks-pass pass:gpdiag-sign --out build/GearsPOP_diag.apk build/work/aligned.apk
```
`SDK=/opt/homebrew/share/android-commandlinetools`, JDK `/opt/homebrew/opt/openjdk@17`, build-tools 34.0.0.

## 8. Riesgos a vigilar en la prueba
- El parser de `Config.json` podría rechazar el JSON compacto o la URL con puerto (el original venía con sangría).
- XAL o Firebase pueden quejarse de la firma distinta; solo deberían afectar el login con Xbox y la analítica.
- Si el teléfono tiene Android 9 o menos, no hay ALPN en el servidor: gRPC-core cortaría el handshake (queda en el log).
- `GamefuelContentService.ValidateRemoteCertificate` podría fijar otra CA para el CMS.

## Entrega 1: responder el login
- Formato Catapult decodificado: ver `analysis/protocolo/README.md` y `analysis/protocolo/message_tags.tsv` (365 etiquetas).
- El servidor (`server_diag/src/gpdiag/Catapult.java`) mantiene abierto el stream duplex `/GrpcTransport/raw`, decodifica cada mensaje
  (tipo, op, RequestId, headers) y responde `Message<LoginRequest>` con `Result<SessionTokenResponse>`
  (SessionToken `gprevival-session-1`, AccountId `gprevival-local-1`, ContentUrl `https://127.0.0.1:8443/cms/content`).
  Los demás mensajes se registran con su nombre y el cuerpo en hex, sin respuesta todavía.
- Probado en la Mac: curl con un `Message<LoginRequest>` armado a mano → respuesta decodificada correcta (Reply con el mismo RequestId).
- **Prueba 8 (14:07, v8): el login funciona.** El cliente acepta `Result<SessionTokenResponse>`, cierra el login y **se conecta al gateway**
  (12345). La petición real trae headers `CorrelationHeader` + `OperationHeader`, ClientVersion `1.98` y Platform `android`.
  En el gateway, el cliente abre `/GrpcTransport/raw` y lo cierra a los ~30 ms sin mandar mensajes (DATA vacío con END_STREAM + RST).
  Justo antes registra `File …/files/content_data does not exist!` (la caché del CMS). Hipótesis: lo que decide la desconexión son los
  campos de contenido de la respuesta (ContentUrl/Version/Etag). No hubo ningún intento de descarga en 8443.
- **v9:** el servidor alterna la respuesta del login en cada intento: A = contenido propio, B = sin campos de contenido,
  C = ContentUrl igual a `cms_url`. Queda registrado en `gpdiag.log` cuál se usó.

- **Prueba 9 (14:14, v9):** las 3 variantes (A, B y C) terminan igual. Lo que corta no son los campos de contenido.
- **Causa (pseudo-descompilado con `scripts/il2cpp_calls.py`, `il2cpp_xrefs.py`, `il2cpp_metarefs.py`):**
  `ConnectionManager.OnNextState` llama a `ParseCMSData` al pasar de LoggingIn a ConnectingToGateway. `ParseCMSData` **solo lee la caché**
  (`GamefuelContentService.LoadCachedContent`, archivo `files/content_data`, guardado con `EncryptedTextSerializer`). Si no está,
  `OnCmsLoadFailed` → `DisconnectDueToRequiredContentUpdate` + `RestartGame`. Esa es la desconexión del gateway a los 30 ms.
- **Quién descarga el CMS:** `Catapult.Network.Requests.ErrorHandling.ContentUpdateStep`. Se activa cuando una respuesta trae
  `Error.ErrorCode == 471` (`CatapultStatusCode.ContentUpdateRequired`). Lee `Result<SessionTokenResponse>.Body.ContentUrl`, llama a
  `IGamefuelContentService.DownloadContent(url)` (WebClient con gzip), guarda un `ContentDetail` con el `ContentEtag` y repite el login
  con `LoginRequest.ContentETag`.
- `CatapultStatusCode`: 200 Ok, 400 BadRequest, 401 Unauthorized, 403 Unauthenticated, 404 NotFound, 440 SessionExpired,
  470 ForceClientUpgrade, **471 ContentUpdateRequired**, 480 StateSyncRequired, 490 AccountNotFound, 500/502/503/504, 505 MaintenanceModeEnabled.
- **v10:** si el ETag del cliente no es `gprevival-1`, el login responde con el cuerpo completo más `Error {1: 471}`. Si coincide,
  responde OK. El servidor HTTP registra todos los encabezados de la descarga del CMS, que por ahora contesta 404:
  falta servir un CMS de verdad (entrega 2).
- **Prueba 10 (14:23, v10):** el 471 funciona: después de cada respuesta, el cliente **intenta descargar el CMS** de `ContentUrl`
  (conexión a 8443). Falla el TLS con `UNSUPPORTED_PROTOCOL`: el WebClient de Mono (Unity 2018) ofrece una versión de TLS que
  Conscrypt en Android 16 ya no acepta como servidor. El progreso baja de 13% a 5% porque el juego se queda en el login esperando el contenido.
- **v11:** `ContentUrl = http://127.0.0.1:8080/cms/content` (HTTP plano). Por ahora contesta 404; queda registrada la petición completa.
- **Prueba 11 (14:31, v11): entrega 1 cumplida.** Después de cada 471, el cliente hace `GET /cms/content HTTP/1.1` a `127.0.0.1:8080`
  con `accept-encoding: gzip` (sin User-Agent), recibe 404 y repite el login cada ~1.3 s. No registra el error en logcat.
  **Siguiente bloqueo (entrega 2):** servir un CMS que `CMSManager.LoadCMSData(string)` acepte. Hay que sacar su formato
  de las clases `CMSData`/`CMSDataGroup` del volcado y llenarlo con `data/`.

## Entrega 2: el CMS
- Flujo: `GamefuelContentDownloader` (WebClient, gzip) → texto → `SaveContentFile` (caché cifrada con `EncryptedTextSerializer`)
  → `ParseCMSData` → `CMSManager.LoadCMSData(string)` → `CMSDataExtensions.CreateCMSData` → **MiniJSON** →
  `new CMSData(Dictionary<string, object>, …)`. Si el texto termina en `</body></html>`, se marca como error 503.
- Formato (confirmado con `analysis/asset_cms_data_1.98.json`): `{ "<grupo>": [ { "id": "...", <campos> }, ... ], "_meta": { "<grupo>": {"total": n},
  "_content_version": "...", "_segments": [] } }`.
- Esquema: `scripts/cms_schema.py` → `analysis/protocolo/cms_schema.json` (309 clases, **143 grupos**, 3,247 campos). Cada grupo es una
  clase `[CMSGroup]`; cada propiedad lleva `[CMSField("clave")]`, `[CMSReference]` (id de otro grupo) o `[CMSDefault]`. Las claves se leen
  de las cadenas C que cargan los generadores de atributos. Lista simple en `analysis/protocolo/cms_groups.tsv`.
- Items sueltos que exige `CMSData.ParseDataGroups`: `analysis/protocolo/cms_singletons.json` (ids `singleton`, `battlefield_ui`,
  `current_maps`, `standard_settings`, `misc_balance`, `exclusivity_matrix`, `settings`, `gameplay_tips`, `daily_deals_default`).
- `scripts/build_cms.py` → `data/cms/cms.json`. **Paso 1:** todos los grupos vacíos + esos items solo con `id` (9 KB).
- **v12:** el servidor responde `GET /cms/content` con el CMS. Si existe `files/cms.json` en el teléfono, usa ese (sirve para iterar
  sin reinstalar); si no, usa `assets/diag/cms.json`.
- **Prueba 12 (15:07, v12): el CMS se descarga.** El cliente baja el CMS de 9 KB, lo guarda (`files/content_data`, base64 cifrado),
  repite el login con `ContentETag=gprevival-1` (OK) y **manda su primer mensaje al gateway**: `tipo#80982860` (seguramente
  `Message<AuthenticationRequest>`), con el cuerpo `{1: {1: "gprevival-session-1", 2: "gprevival-local-1", 3: "12.28.0.0", 4: 0}}`.
  A los 36 ms corta el gateway: es el mismo patrón de `OnCmsLoadFailed`. El parser del CMS falla y la excepción se traga sin log
  (`ParsingUtils` usa `IAsserts` con "Key not found: <clave>").
- **v13:** `scripts/patch_libil2cpp_cmslog.py` parchea el `catch` de `ParseCMSData` (0x14f7ba8) para que llame a
  `Debug.LogException(e)` en vez de `ClearDetailsStore`. El error del CMS sale ahora en logcat (etiqueta Unity).
  El ETag del contenido es un CRC32 del CMS servido (`DiagProvider.cmsEtag`): si cambia `files/cms.json`, el cliente lo vuelve a descargar.
- **Prueba 13 (15:16, v13): el parche de registro funciona.** Error del CMS: `KeyNotFoundException` en
  `Parsing.Parse[TDataCollection](def, data, referenceCache, fieldId)` ← `ParseListToDictionary` ← `ParseDictionary` ← `CMSData…`.
  Un item no trae un campo obligatorio (los items sueltos solo tenían `id`). logcat corta la pila.
- **CMS v2** (`scripts/build_cms.py`): items completos. Simples → 0/false/""; `Fix` → 0; `DateTime` → ISO; arreglos → [];
  enums → su primer valor (sacado de `dump.cs`); objetos anidados → recursivo; referencias → item `gp_default` del grupo destino;
  `[CMSDefault]` se omite. Incluye los campos de las clases base. 54 items, 21 KB. Se prueba copiándolo a `files/cms.json`.
- **Prueba 14 (15:26, CMS v2):** se descarga (21 KB) y el login pasa con el ETag nuevo. Mismo `KeyNotFoundException`.
  Causa: faltaban 8 grupos (`status_effects`, `ultimates`, `target_filters`, `armaments`, `area_of_effects`, `behaviour_states`,
  `status_effect_areas`, `render_texture_scenarios`). Sus clases tienen homónimas en otros namespaces que las pisaban en
  `cms_schema.py`, y las referencias a esos tipos salían como objetos en vez de IDs.
- **CMS v3:** esquema corregido (317 clases, **151 grupos**, 3,388 campos), 21 KB.
- **Prueba 15 (15:34, CMS v3):** mismo `KeyNotFoundException`. Hallazgos:
  - 90 atributos CMS van en **campos** (`public X y;`), no en propiedades; el esquema los ignoraba. Corregido: 324 clases, 3,435 campos.
  - `Parsing.Parse<T>` (0x1e6adb8) recorre campos y propiedades por reflexión. Si falta una clave sin `[CMSDefault]`, llama a
    `IAsserts.IsTrue(false, "Collection '{0}' missing field '{1}', use CMSDefault attribute")` y luego hace `data[clave]` (→ KeyNotFound).
    En la versión final `ParsingUtilsAssert` está vacío (`ret`).
- **v14:** `patch_libil2cpp_cmslog.py` también redirige `ParsingUtilsAssert.IsTrue(bool, string)` y `Fail(string)` a
  `ParsingUtilsLogger.Error` → `Debug.LogError` (la lógica de IsTrue va en el cuerpo de `ParsingUtilsLogger.DebugFormat`, 0x143ab04).
  El logcat dirá exactamente qué colección y qué campo faltan. Incluye el CMS v4 (21.6 KB).
- **Prueba 16 (15:41, v14 + CMS v4):** ya no faltan campos. Error nuevo: `ArgumentException: failed to convert parameters`
  (`MonoMethod.Invoke` = setter de una propiedad, dentro de `Parsing.Parse`). `Parsing.ParseByType` maneja enum, string, bool,
  int, uint, long, float, Fix, string[] y DateTime; el resto, con un `Parse` estático. `ParseInt` solo acepta `long`; `ParseFloat`,
  string/Fix/número; **`ParseFixed` solo texto** ("1.5": `IndexOf('.')`, `Substring`, `Int32.Parse`).
- **CMS v5:** `Fix` → `"0"`, `float` → `0.0`.
- **Prueba 17 (15:47, CMS v5):** sigue `failed to convert parameters`. `Parse<T>` usa `MethodBase.Invoke` en dos lugares:
  las funciones `[CMSParseFunction]` y, en los campos `Dictionary<…>`, `ParseListToDictionary(dict, List, cache, keyId)`.
  Ese segundo caso espera una **lista** de items con `id`; yo mandaba `{}`.
- **CMS v6:** `Dictionary<…>` → `[]`.
- **Prueba 18 (15:50, CMS v6):** el error de tipos desapareció. Nuevo: `NullReferenceException` en `DailyDeal.ParseReferencelessMap(object)`.
  Las `[CMSParseFunction]` convierten por su cuenta: los mapas esperan un diccionario JSON.
- **CMS v7:** campos con `[CMSParseFunction]`: `Dictionary` → `{}`, `List`/arreglo → `[]`, `ParseStringAsInt` → `"0"`. Los demás `Dictionary` siguen como `[]`.
- **Pruebas 19 y 20 (15:53, 15:57):** ojo, el cliente parsea la **caché anterior**: la primera vez que baja un CMS nuevo, lo guarda
  en segundo plano y `ParseCMSData` lee el archivo viejo; en los reintentos ya lee el nuevo. Con eso todo cuadra:
  `levels = []` → `NullReferenceException` en `DailyDeal.ParseReferencelessMap` (espera un diccionario `nivel → lista`);
  `levels = {}` o `{"1": []}` → `daily_deals` pasa y aparece el `failed to convert parameters` de otro grupo.
- Causa del `failed to convert parameters`: **`GameString` es un grupo** (`game_strings`, con el campo `text`). Sus 73 campos son
  `[CMSReference]` (van como id), y el generador los ponía como texto `""`.
- **CMS v9:** `GameString` → referencia a `game_strings/gp_default`; `levels` → `{"1": []}`.
- **Prueba 21 (16:02, CMS v9):** sigue `failed to convert parameters` en todos los reintentos. Por el código de `Parse<T>`:
  la función propia (`Invoke`) deja el resultado en x19; después se asigna con `FieldInfo.SetValue` o con el setter de la propiedad
  (otro `MonoMethod.Invoke`). En los items solo `DailyDeal.levels` es de tipo genérico.
- **v15 (bisección):** `scripts/cms_bisect.py` genera 8 variantes (`assets/diag/cms_var_N.json`). v0 y v7 son el CMS completo;
  en v1..v6 se vacían los grupos con datos cuyo índice (en `analysis/protocolo/bisect_grupos.txt`, 37 grupos) tiene el bit (v-1) encendido.
  El servidor sirve cada variante en 3 logins (471 + descarga, OK, OK) y registra
  "BISECCIÓN: el parseo de ESTE intento usa la variante N". Si el error desaparece en las variantes con bit b, el culpable tiene el bit b.
- **Prueba 22 (16:08, v15):** la bisección no sirvió: al vaciar grupos se rompen las referencias `gp_default` y sale `KeyNotFoundException`
  antes. Las variantes completas (v0 y v7) dan `failed to convert parameters`. Esto confirma que las referencias se resuelven durante el parseo.
- Análisis de `Parse<T>` en 0x1e6bbc4: la función propia se busca con `GetMethod(FunctionName)` en el tipo `T` y se invoca con `obj = def`,
  `params = [data[clave]]`. Único sospechoso concreto: `DailyDeal.levels`.
- **v16** (sin modo bisección) + `data/cms/cms_sin_daily_deals.json`: se prueba el CMS con `daily_deals` vacío.
- **Prueba 23 (16:15, v16 + CMS sin daily_deals): `ParseDictionary` pasa completo.** El único error es el esperado
  (`KeyNotFound` en `CMSData.ParseDataGroups`, por falta del item `daily_deals_default`). El culpable era `DailyDeal.levels`:
  con cualquier diccionario (incluso `{}`), asignar el resultado de `ParseReferencelessMap` da `failed to convert parameters`;
  con una lista, la función falla con `NullReferenceException`. Parece una rareza del IL2CPP del juego en esta ruta.
- **v17:** parche a `DailyDeal.ParseReferencelessMap` (0x161c584: `mov x0, xzr; ret`). Al devolver null, `Parse` se salta la asignación.
  Las ofertas diarias quedan vacías. Se vuelve al CMS v9 completo.
- **Prueba 24 (16:18, v17):** sigue `failed to convert parameters` aunque la función devuelva null. El error es del propio `MethodBase.Invoke`
  de la función (al convertir el argumento), no de la asignación.
- **v18:** se anula esa llamada en `Parsing.Parse<T>` (0x1e6bbc4 `bl MethodBase.Invoke` → `mov x0, xzr`). Los 9 campos `[CMSParseFunction]`
  quedan sin asignar (ofertas diarias, niveles y puntajes de Horda, overrides de primer triunfo, versión de dos assets).
  Se quitó el parche de `DailyDeal`.
- **Prueba 25 (16:21, v18):** el error sigue, pero ahora solo puede venir del otro `Invoke` de `Parse`: `ParseListToDictionary` (0x1e6c6bc).
  Para `levels`, `Parse` ejecuta **las dos ramas**: la función propia (necesita un diccionario) y luego la rama de diccionarios
  (necesita una lista). Con la función anulada, basta una lista.
- **CMS v10:** campos `[CMSParseFunction]` de tipo `Dictionary`/`List`/arreglo → `[]`.
- **Prueba 26 (16:24, v18 + CMS v10):** sigue el mismo error. La rama de diccionarios llama a `ParseListToDictionary<TKey, TValor>` con
  `MakeGenericMethod`; con `TValor = SlotContent[]` esa instancia genérica no está compilada en el IL2CPP del juego.
- **v19:** también se quita esa llamada (0x1e6c6bc → nop): se asigna el diccionario vacío del tipo exacto. **Limitación:** los campos
  `Dictionary<…>` del CMS quedan vacíos (hoy solo `DailyDeal.levels`).

### Entrega 2 cumplida (10 nov 2026, 16:57, en el emulador)
Con el **emulador Android 14 ARM64** (AVD `gpop`, imagen `system-images;android-34;google_apis;arm64-v8a`) cada prueba toma 1–2 minutos.
Hallazgos y arreglos finales:
- **`SoftLaunchAccessGate.IsUserAllowedToLogin`** (0x14b8720): control de licencia de Google Play (clase Java + firma RSA). Sin Play Store
  no deja ni intentar el login ("Sending error as not allow to log in"). Parche: siempre true.
- **Parche de diagnóstico en `MonoMethod.Invoke`** (0x1be1ed8): la `ArgumentException` "failed to convert parameters" lleva el nombre del
  método. Así salió el culpable real: **`set_TimeBetweenToasts`** (`HordeBattleUiSettings.time_between_score_toasts`, `Fix` con `[CMSDefault]`).
  Si se omite un `Fix` con `[CMSDefault]`, el parser asigna el valor por defecto del atributo (float) sin convertirlo. Los `Fix` van siempre explícitos.
- Error de lectura: `CMSData.ParseDataGroups` corre **antes** que `ParseDictionary`; la prueba "sin daily_deals" engañaba.
  Aun así se dejó `daily_deals` vacío y se anuló `ParseCMSGroupItem<DailyDeal>` (0x16aed40).
- `StreamingAssetManager.Startup` necesita `asset_bundle_manifest/manifest` (paquetes remotos en `assets.gamefuel.info`, que ya no existen).
  Se apaga con el killswitch: `killswitches = [{"id": "streaming_assets", "killswitch_enabled": true}]` (true = función apagada).
- **Resultado:** el CMS se parsea completo. La pantalla muestra **"RETRIEVING PLAYER DATA… 15%"** (`build/emulador_cms_ok.png`) y el cliente
  reintenta en el gateway `tipo#80982860` (≈ `AuthenticationRequest`: `{1: {1: SessionToken, 2: ContentETag, 3: "12.28.0.0", 4: 0}}`), que
  todavía no se responde. **Siguiente (entrega 3):** responder la autenticación y los servicios del gateway.
- Parches de `libil2cpp.so`: ver `scripts/patch_libil2cpp_cmslog.py` (25 instrucciones). Varios son de diagnóstico; el 3 y el 4
  (reflexión de `[CMSParseFunction]` y `Dictionary`) quedaron como red de seguridad y dejan esos campos en null.
- Herramientas: `scripts/build_apk.sh` (arma y firma el APK), `scripts/build_cms.py`, `scripts/cms_schema.py`.

## Entrega 3: el gateway (avance, 10 nov 2026, emulador)
- `Message<AuthenticationRequest>` (80982860) {1: Token, 2: ContentEtag, 3: ProtocolVersion ("12.28.0.0"), 4: ContinueSession}
  → `Result<AuthenticationResponse>` (98996885) {1: {1: UserId}}. **Aceptado.**
- Etiquetas completas: `scripts/proto_tags.py` corregido (solo el patrón `adrp xN; ldr xN,[xN,#off]`) → 737 en `message_tags.tsv`,
  incluidos los `Message<T>`.
- Pares petición→respuesta: los 97 `RemoteServiceBase.SendRequest<Req, Resp>` de `script.json` → `analysis/protocolo/request_pairs.json`.
- `scripts/dto_schema.py` (esquema de cualquier DTO desde su `Write(T)`) + `scripts/build_responses.py`: respuestas por defecto
  recursivas (textos "", ids que apuntan al CMS = `gp_default`, sub-mensajes llenos, listas con un elemento) → `assets/diag/responses.tsv`
  (89 respuestas). El servidor responde cualquier petición que esté en esa tabla.
- `build_cms.py` fuerza items `gp_default` en `vanity_items`, `vanity_item_colors`, `ultimates` y `cards` (los referencian los datos del jugador).
- **Estado:** login → CMS → autenticación → `GetAllPlayerData` (692 bytes) → `StoreQuery` → `GetServerInformationQuery` (en el puerto
  de batalla 11111) → la barra llega a **100%** sin diálogo de error (`build/emulador_entrega3.png`). Ahí se queda. Errores que quedan,
  todos de contenido:
  - `TutorialManager.HasCompleteTutorialBattleRemote` → corta `GameController.WaitForTutorialManagerThenPreloadScenes` (precarga del menú).
  - `BattleServerInformation.TryParse` (la respuesta de `GetServerInformationQuery` va vacía).
  - `AvatarFactory.SetVanityItems` (KeyNotFound: tipos de vanidad sin definir en el CMS), `BountiesService.UpdateCachedData` (falta el diccionario).
  - CMS: "No core arenas exist!", ajustes de Unranked, y `AssetBundleDef` de `ui`/`fonts`/`avatar`/`arena01..09`/`thumpers`
    (paquetes remotos de `assets.gamefuel.info`, que no están en el APK).

### Entrega 3, segunda parte: hasta el menú principal (emulador, 2026-11-10)
Cada corrección destapó el siguiente error. En orden:
1. **Tutorial**: killswitch `tutorial` = true → `TutorialManager` lo da por completado (`build_cms.py`).
2. **Info de batalla**: `ServerInformationQueryResponse` = {1: Region "local", 2: Url "https://127.0.0.1:11111"} (`EXTRA` en `build_responses.py`; el esquema no detecta el getter de Url). El cliente ya abre conexión al puerto de batalla y pide `GetServerInformationQuery`.
3. **Bounties**: `BountiesDto.Bounties` (campo 1, `Dictionary<uint, BountyDto>`) no puede ir null → una entrada por defecto (`ONE_ENTRY_MAPS`).
4. **Monedas**: CMS `currencies` = `hard_currency` (HardCurrency) y `soft_currency` (SoftCurrency); el perfil lleva `CurrenciesDto` con esos ids (`OVERRIDE`). `CurrencyDto` = {1: Id, 2: ContentId, 3: Quantity}.
5. **Avatar**: `AvatarFactory.SetVanityItems` busca un item activo por tipo (`head`, `torso`, `legs`, `skincolor`, `haircolor`, `emblem`) más `emblem_default`. El CMS crea esos tipos e items `gp_<tipo>`, y `ActiveVanityItemsDto` los activa.
6. **Cofres**: `gear_pack_settings['singleton']` y la lista `GearPacks` vacía (un `gp_default` no existe como gear pack).
7. **misc_settings**: 18 claves leídas con `Dictionary<string, MiscSetting>.get_Item` (sacadas con `il2cpp_metarefs.py`), con valores razonables.
8. **Unranked**: `unranked_settings['default']` y `unranked_event_visuals['blocked']` (`UnrankedEventsService.Init`).

Resultado: menú principal con pestañas, botones, botón de batalla y 4 ranuras de cofres (`build/emulador_menu.png`). Sin textos ni imágenes: los paquetes remotos (`fonts`, `ui`, `avatar`, `arena01..09`, `thumpers`, `startup`) no están en el APK y su servidor (`assets.gamefuel.info`) ya no existe.
Quedan NullReference menores: `GearPackSlotViewModel.SetUpBonusGlow` (evento de primera victoria sin visuales) y `CrewsViewModel.UpdateUnlockedFeatures`.

### Fuentes (2026-11-10)
- El APK no trae ninguna fuente TextMeshPro: solo materiales `SairaCondensed-* SDF Material (Instance)` y la hoja de estilos. `TMP Settings` no tiene fuente por defecto.
- La versión de TMP no tiene `TMP_FontAsset.CreateFontAsset`, y `Font.CreateDynamicFontFromOSFont` quedó fuera del binario: no se puede crear una fuente del sistema en tiempo de ejecución.
- Las fuentes las asigna `FontFactory` (StreamingAssetsFactory) desde el paquete `fonts`, por ids del CMS (`StreamingAssetFontDataID`, `StreamingAssetFontMaterialID`). Por eso los textos salen vacíos con el aviso "Please assign a Font Asset".
- Ruta posible: armar un paquete `fonts` propio con fuentes libres (Saira Condensed es OFL, de Google Fonts) usando Unity 2018.4.12f1 y la misma versión de TMP, servirlo desde el servidor embebido y declararlo en el CMS.

### Prueba de batalla (2026-11-10)
- Tocar el botón naranja no hace nada y no deja ningún aviso: no se llega a `MainMenuV2ViewModel.TryEnterBattle`, que pide una `GameModeCard` enfocada (carrusel de modos). Los toques sí llegan (el menú ☰ abre opciones, aunque invisibles).
- Arenas: `ArenaData` usa `scene_name`/`is_in_core_bundle`. El APK solo trae `ArenaBase`, `ArenaBaseHorde`, `ArenaTemplate` y `BattleHudTestArena`; las arenas reales (`arena01..09`) eran paquetes remotos.
- Unidades: en el APK solo hay datos visuales, materiales y efectos sueltos (p. ej. `YoungMarcusFenixLancer_VisualData`). Las animaciones y el audio de las unidades se cargan por nombre (`animation/…`, `audio/…`) y ningún archivo del APK los contiene. Lista de 278 nombres en `analysis/asset_bundle_names.txt`.
- Conclusión: sin los paquetes originales no hay batallas visibles. Las fuentes solas no lo hacen jugable.

### Búsqueda de los paquetes en Internet (2026-11-10)
- Ruta original (de `asset_cms_data_1.98.json`): `https://assets.gamefuel.info/moncton-assets/28/AssetBundles/android/<paquete>` (por ejemplo `asset_bundles_startup`, unos 6 MB).
- Wayback Machine (CDX): de `assets.gamefuel.info` solo está la raíz (2023). No hay ninguna URL con `moncton` en todo el dominio `gamefuel.info`.
- Búsquedas web: no aparecen copias de los paquetes, ni proyectos de servidor privado o de preservación de Gears POP. Solo hay espejos del APK (que ya tenemos) y extracciones de audio en The Sounds Resource.
