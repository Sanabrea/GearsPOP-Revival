# Client startup (Gears POP! 1.98)

Source: Il2CppDumper v6.7.46 dump in `analysis/il2cpp_dump/` (`dump.cs`, `stringliteral.json`, `script.json`, `il2cpp.h`, `DummyDll/`).
Metadata v24.1. Addresses = RVA inside `lib/arm64-v8a/libil2cpp.so`.

## 1. Config.json → `Mediatonic.Moncton.MonctonConfig`
- `LoadConfigFile()` (0x14EEDA0) reads `Config.json` from StreamingAssets through the `OnLoadStreamingAssetDelegate` delegate,
  and `LoadFromJson()` (0x14EF328) decodes the base64 and extracts the keys `environment`, `cms_url`, `loginEndpoint`,
  `battleEndpoint`, `gatewayEndpoint` (they are stored as `ObscuredString`, in-memory anti-cheat only).
- **Fixed ports** in `MonctonConfig.Config..cctor` (0x14EF6D0, disassembled):
  `LoginPort = 12000`, `GatewayPort = 12345`, `BattleGatewayPort = 11111`. They are not in Config.json.
  They are above 1024, so a non-root app can listen on them.
- `ConnectionManager.OnMonctonConfigLoaded()` → `BuildCatapultConfig()` builds `CatapultConnection.Config`
  (`LoginServerEndpoint/Port`, `GatewayServerEndpoint/Port`, `SslCredentials`, timeouts, `ProtocolVersion`, `ClientVersion`).

## 2. TLS
- `ConnectionManager.LoadSslCredentials()` (coroutine) reads `"/certs/ca.crt"` from StreamingAssets and creates `Grpc.Core.SslCredentials(rootCerts)`.
  No client certificate. gRPC-core validates the chain **and the name** of the target, so the server certificate
  must have the SAN that is set in Config.json (for `127.0.0.1`, an IP SAN).
- There is no `grpc.ssl_target_name_override` among the literals (only `grpc.primary_user_agent`).
- The CMS goes another way: `GamefuelContentService` uses `System.Net.WebClient` (gzip) with its own
  `ValidateRemoteCertificate` and keeps a cached copy (`content_data`). `CheckForStaleCMS`/`LoadCachedContent` allow
  starting with the cache: possible route to inject the rebuilt CMS.

## 3. gRPC channels → `Catapult.Network.CatapultConnection`
State machine `CatapultConnection.State`: Disconnected → **LoggingIn** → **ConnectingToGateway** → **Authenticating** →
**LoadingGameServices** → Connected.
- `CreateLoginNetClient()` (0x141BBE8): `NetClient` with `WithGrpcChannel(builder, "GrpcTransport", sslCredentials)` towards
  `loginEndpoint:12000`. `Login()` sends `LoginRequest` (or `CreateAccountRequest`) and waits for `SessionTokenResponse`.
- `ConnectToGateway()` → `CreateGatewayClient()` (0x141C69C) → channel to `gatewayEndpoint:12345` → `Authenticate()`
  (`AuthenticationRequest`/`AuthenticateRequest` with the session token) → `LoadGameServices()`.
- Transport: `GrpcNetConnection` opens **a single duplex call** `AsyncDuplexStreamingCall<byte[], byte[]>` per channel
  and multiplexes Catapult messages (`Message`, with a Guid `RequestId` and `KeepAliveMessage`). Serialization is provided by
  `IMessageSerializer` (headers in `Catapult.Protocol.Headers`). There is no gRPC service per RPC: the exact `:path`
  is logged by the diagnostic server (the default service name is `GrpcTransport`).
- There are leftovers of **MagicOnion** (`IMagicOnionEmbeddedHeartbeat/Connect`, `HeartbeatClient`).

### Login and Gateway messages (`Catapult.Services.*.Protocol.Client`)
- Login, requests: `LoginRequest`, `CreateAccountRequest`, `AddIdentityRequest`, `RemoveIdentityRequest`,
  `RemoveAndAddIdentityRequest`, `LookupIdentityRequest`, `ForgetAccountRequest`.
- Login, responses: `SessionTokenResponse`, `AccountResponse`, `AccountsResponse`, `IdentityResponse`, `IdentitiesResponse`,
  `LookupIdentityResponse`, `ForgetAccountResponse`.
- Gateway: `AuthenticationRequest/Response`, `TimestampRequest/Response`, `KeepAliveMessage`, `ContentUpdateNotification`,
  `LogAnalyticsEventCommand(s)`.
- Remote services over the gateway: `LoginRemoteService`, `AuthenticationRemoteService`, `ContentRemoteService`,
  `PlayerRemoteService` (Bounties, Clans, Features, Leaderboard, Achievements, Cards, DailyLoginReward, GearPacks…),
  `BattleRemoteService`, `BattleServerInfoRemoteService`, `BootcampRemoteService`, `StoreRemoteService`, `AnalyticsRemoteService`.

## 4. Xbox Live (XAL)
- `XalService` (wrapper of `libXal.Unity.so`): `Initialize`, `TryAddFirstUserSilentAsync`, `AddUserWithUiAsync`
  (WebView with `SetPlatformWebViewEventHandler`), `XalUser`.
- The login credential is a `LoginCredential { CredentialTypeId, Value }`. Literals: `device_id`/`DeviceId`, `xbox`,
  `anonymous`. `ConnectionManager.SetCorrectCredentialsToLogIn()` chooses which one to use; Xbox is added as an extra identity
  (`HandleExtraIdentities`, `AddIdentityRequest`) and the sign-in prompt depends on the CMS (`XblAuthentificationPromptDates`).
  Hypothesis to confirm: the first login is by **device id**, without Xbox.

## 5. Expected startup order
1. Unity → `MonctonConfig.LoadConfigFile()` → `ConnectionManager.OnMonctonConfigLoaded()`.
2. `LoadSslCredentials()` (reads `certs/ca.crt`).
3. `BeginLogin()` → `LoginFlowRoutine` → `CatapultConnection.Connect()` → login (12000) → gateway (12345) → authentication.
4. `ContentRemoteService` delivers the CMS details → `GamefuelContentService.DownloadContent(url)` →
   `CMSManager.LoadCMSData(data, isInitialLogin, callback)` → `ParseCMSData` / `OnCMSLoadCompleted`.
5. `HandleConnected()` → menu. Errors: `error_unabletologin`, maintenance, mandatory update.

## 6. Delivery 0: diagnostic APK (`build/GearsPOP_diag.apk`)
Chosen route: **server embedded in the APK** (plan B on the Mac was not needed).
- `assets/Config.json`: all endpoints set to `127.0.0.1`; `cms_url` = `https://127.0.0.1:8443/cms/projects/moncton/branches/production/groups`.
- `assets/certs/ca.crt`: our own CA (`build/keys/ca.crt`). The server uses `build/keys/server.p12`
  (SAN: IP 127.0.0.1, localhost and the 5 original hosts).
- Server: `server_diag/src/gpdiag/` (pure Java, no dependencies, compiled to `classes2.dex`).
  A `ContentProvider` (`gpdiag.DiagProvider`) starts with the process, before the Unity Activity, so no game code was touched.
  Listens according to `assets/diag/ports.txt`: 12000 login, 12345 gateway, 11111 battle, 8443 CMS (all TLS with ALPN h2) and 8080 plain HTTP.
  Logs the TLS handshake (version, ALPN, SNI), every gRPC call (`:path` → service/method, `:authority`, metadata and bytes)
  and every HTTP/1.1 request. To gRPC it answers `grpc-status 12 UNIMPLEMENTED`; to HTTP, 404.
- Log: logcat with tag `GPDiag` and file `/sdcard/Android/data/com.microsoft.gearspop/files/gpdiag.log`.
- Own signature: `build/keys/sign.jks` (key `gpdiag-sign`). minSdk raised to 24 (the original said 19).
- Rebuild: `build/work/dec` is the APK decoded with `apktool d -s`; the steps are in section 7.

### Installation on the phone
`adb` is at `/opt/homebrew/share/android-commandlinetools/platform-tools/adb`. Enable USB debugging.
1. Backup (if the folder exists): `adb pull /sdcard/Android/data/com.microsoft.gearspop backup_gearspop/`.
   It may contain cached models (Kait, Carmine, Decoy, Barrier). On Android 14+ adb may not have access: in that case copy it with a file manager or from the PC via MTP.
2. Only after the backup: `adb uninstall com.microsoft.gearspop` (the signature is different and Android does not allow installing over it).
3. `adb install build/GearsPOP_diag.apk`
4. `adb logcat -c && adb logcat -s GPDiag:V Unity:V CatapultNet:V grpc:V AndroidRuntime:E`
5. Open the game, wait ~1 minute and then `adb pull /sdcard/Android/data/com.microsoft.gearspop/files/gpdiag.log`.

### Result
**Test 1 (Nov 10 2026, 12:26, user's phone):** the server starts fine (all 5 ports listen),
but the process starts 3 times in 17 s (pids 3165, 5215, 9052) and **no connection arrives**.
Either the game closes before networking, or the user opened it several times. The logcat is needed to know the cause.
**APK v2:** the server now saves its own logcat in `files/logcat_<hora>_<pid>.txt`, plus the crash buffer
of the previous startup (`..._crash_anterior.txt`) and any Java crash in `gpdiag.log`.

**Test 2 (12:31, v2):** the first test was not a crash; they were app restarts.
- Unity starts, loads Firebase and AppsFlyer, deletes the old CMS ("unique id has changed") and loads `libgrpc_csharp_ext.so`.
- The client **does reach the login**: 10 connections to `127.0.0.1:12000`, one per second. TLS 1.2 ok and SNI `127.0.0.1`,
  so our own CA and `Config.json` work.
- It is cut off because **`alpn=null`**: gRPC requires `h2` and closes the connection. Then `ErrorMessageUI` appears.
  Cause: in Conscrypt the ALPN of the `SSLServerSocket` is not inherited. **v3:** it is set on each accepted socket.
- It also requests `moncton-service-status-prod.azurewebsites.net` (status/maintenance, over HTTPS from Java); it fails with UnknownHost
  and does not seem to block. It will have to be served or redirected later.
- Braze gives `invalid_api_key` (it is harmless).

**Test 3 (12:39, v3):** **ALPN ok (`alpn=h2`)**. The client sends the HTTP/2 preface, but the server blows up with
`ExceptionInInitializerError` / `NoClassDefFoundError: gpdiag.Hpack`: the Huffman table was built before the arrays were initialized.
On the client side, gRPC logs `SSL_read returned 0 unexpectedly` / `TSI_INTERNAL_ERROR` and then `ErrorMessageUI`.
**v4:** the table is built on first use and every DATA message is logged (bytes and 48 bytes in hex); UNIMPLEMENTED is answered
after the first message, because the transport is duplex. Tested on the Mac with `curl --http2-prior-knowledge` and with
example C.4.1 of RFC 7541 (Huffman).

**Test 4 (12:47, v4): Delivery 0 accomplished.** The game opens, tries to log in and what it requests gets logged:
- Connection: `127.0.0.1:12000`, TLS 1.2, ALPN `h2`. **gRPC path: `/GrpcTransport/raw`** (service `GrpcTransport`, method `raw`),
  duplex `byte[]` call. Extra metadata: none.
- First message: 216 bytes in DATA = gRPC prefix (`00` + length `0x000000d3` = 211) + 211-byte Catapult message:
  ```
  aad8ef8f 02 9301 | 0a 9001 0a08 "DeviceId" 12 58 "KRu6MNFidMJdWWFu7MaSh…"
  ```
  Provisional reading: 4 bytes of type id (`0x8fefd8aa` LE, would be `LoginRequest`), one byte `02`, varint 147 = length of the
  protobuf body; inside is the `LoginCredential` (field 1 = `CredentialTypeId` "DeviceId", field 2 = 88-character `Value`).
  The remaining 57 bytes are still to be identified (headers: client version, platform, RequestId…).
- **Login is by `DeviceId`: it does not ask for Xbox Live** nor open XAL before the login.
- Where it stops: on `grpc-status 12` the client sends `RST_STREAM`, retries every ~1.2 s and ends in `ErrorMessageUI`.
- Next step (Delivery 1): decode the Catapult message format (`IMessageSerializer`, `Catapult.Protocol.Headers`)
  and answer a `SessionTokenResponse` to move on to the gateway (12345).

### Problem: the first startup freezes
The user reports that the first startup freezes and closes (it stays in the background); after a minute it loads and shows the connection error.
- In the logcat of test 4, startups 9907 (12:45:03) and 9734 (12:45:26) go silent **at the same point**: after
  `#EnvironmentSelector# Saving last environment as: Production` (and `Using memoryadresses from more that 16GB of memory`).
  There is no crash or ANR in the app's own log.
- In the startup that works (12325), 330 ms after that line comes `UNLOADING SCENE: LoadingScene`, and then gRPC and the login.
  That process was born at 12:46:04 in the background (Android relaunched it) and the Activity opened at 12:47:16.
- Suspicions: a Unity-to-Java call that blocks on cold start (accessibility TextToSpeech, AppsFlyer, Firebase,
  reading StreamingAssets) or something specific to MIUI. Still need to know whether the original APK does the same.
- **v5:** the server includes a watchdog that saves to `gpdiag.log`, every 5 s for 90 s, the Java stack of `main` and `UnityMain`.
- **Test 5 (12:53, v5):** the cold start (pid 12255) did not manage to write even one watchdog entry (5 s): the whole process
  died or froze in less than 5 s. Android relaunched the process in the background (19794, 12:53:41), without `UnityMain`
  for 60 s. When reopening the game (12:54:45), Unity started in that already-started process and the login went out instantly.
  **Conclusion:** it only fails when the process and the Activity start together. Clue: in the failing startups, the last line is
  `Using memoryadresses from more that 16GB of memory`; in the one that works (12325) that line does not appear.
- **v6:** on startup, it saves `ApplicationExitInfo` (exit reason of previous processes) and, if it was a native crash or ANR,
  the tombstone in `files/traza_<pid>.txt`.
- **Test 6 (13:40, v6): cause found.** Xiaomi 2311DRK48G phone with **Android 16 (SDK 36)**. All failing startups
  exit with `REASON_SIGNALED`, status 11 = **SIGSEGV**, in the foreground, 1–2 s after opening, and without a tombstone. In the most
  recent startups it fails almost always.
- **Mechanism** (`libunity.so`, 0x741684): Unity 2018.4 registers each memory block in a table with **5 slots** indexed
  by `address >> 32` (4 GB per slot). On Android 16 the allocator spreads memory across more than 5 zones of 4 GB. When the
  sixth arrives, Unity writes `Using memoryadresses from more that 16GB of memory`, uses index -1 (reads the counter at +0xa0 as a
  pointer) and crashes. Whether it sometimes works depends on how ASLR places the memory.
- **v7:** `scripts/patch_libunity_16gb.py` patches 13 instructions of the 3 table functions (lookup 0x7415b8,
  register 0x741684, remove 0x7418dc): the key becomes `>> 35` (32 GB per slot, 160 GB in total) and the root table 1024 entries,
  with the counter at +0x2000. The script verifies the original bytes. The other 9 occurrences of `ubfx #25, #7` in the library
  are other code (textures).
- **Test 7 (13:53, v7): fixed.** 3 cold starts in a row (pids 13244, 14089, 15670): all 3 reach the login at
  ~2.5 s, with no SIGSEGV exit (the recorded exits are `SwipeUpClean`, when the user closes the app).
  The screen shows "LOGGING IN… 5%" and then the dialog "Gears POP! encountered an error. Please check your internet connection".
  The `libunity.so` patch remains a permanent part of the client.

## 7. How to rebuild the APK
```
javac --release 8 -cp $SDK/platforms/android-34/android.jar -d build/server_diag/classes server_diag/src/gpdiag/*.java
d8 --min-api 24 --lib $SDK/platforms/android-34/android.jar --output build/server_diag/dex build/server_diag/classes/gpdiag/*.class
python3 -I scripts/patch_libunity_16gb.py <original libunity.so> build/work/dec/lib/arm64-v8a/libunity.so
apktool b -o build/work/unsigned.apk build/work/dec
cp build/server_diag/dex/classes.dex build/work/classes2.dex && (cd build/work && zip -q unsigned.apk classes2.dex)
zipalign -f -p 4 build/work/unsigned.apk build/work/aligned.apk
apksigner sign --ks build/keys/sign.jks --ks-pass pass:gpdiag-sign --out build/GearsPOP_diag.apk build/work/aligned.apk
```
`SDK=/opt/homebrew/share/android-commandlinetools`, JDK `/opt/homebrew/opt/openjdk@17`, build-tools 34.0.0.

## 8. Risks to watch during testing
- The `Config.json` parser could reject compact JSON or the URL with a port (the original came indented).
- XAL or Firebase may complain about the different signature; it should only affect Xbox login and analytics.
- If the phone has Android 9 or lower, there is no ALPN on the server: gRPC-core would cut the handshake (it stays in the log).
- `GamefuelContentService.ValidateRemoteCertificate` could pin a different CA for the CMS.

## Delivery 1: answering the login
- Catapult format decoded: see `analysis/protocol/README.md` and `analysis/protocol/message_tags.tsv` (365 tags).
- The server (`server_diag/src/gpdiag/Catapult.java`) keeps the duplex stream `/GrpcTransport/raw` open, decodes each message
  (type, op, RequestId, headers) and answers `Message<LoginRequest>` with `Result<SessionTokenResponse>`
  (SessionToken `gprevival-session-1`, AccountId `gprevival-local-1`, ContentUrl `https://127.0.0.1:8443/cms/content`).
  The other messages are logged with their name and the body in hex, with no response yet.
- Tested on the Mac: curl with a hand-built `Message<LoginRequest>` → correct decoded response (Reply with the same RequestId).
- **Test 8 (14:07, v8): login works.** The client accepts `Result<SessionTokenResponse>`, closes the login and **connects to the gateway**
  (12345). The real request carries headers `CorrelationHeader` + `OperationHeader`, ClientVersion `1.98` and Platform `android`.
  On the gateway, the client opens `/GrpcTransport/raw` and closes it after ~30 ms without sending messages (empty DATA with END_STREAM + RST).
  Right before it logs `File …/files/content_data does not exist!` (the CMS cache). Hypothesis: what decides the disconnection are the
  content fields of the response (ContentUrl/Version/Etag). There was no download attempt on 8443.
- **v9:** the server alternates the login response on each attempt: A = own content, B = no content fields,
  C = ContentUrl equal to `cms_url`. Which one was used is logged in `gpdiag.log`.

- **Test 9 (14:14, v9):** all 3 variants (A, B and C) end the same way. What cuts it off is not the content fields.
- **Cause (pseudo-decompiled with `scripts/il2cpp_calls.py`, `il2cpp_xrefs.py`, `il2cpp_metarefs.py`):**
  `ConnectionManager.OnNextState` calls `ParseCMSData` when going from LoggingIn to ConnectingToGateway. `ParseCMSData` **only reads the cache**
  (`GamefuelContentService.LoadCachedContent`, file `files/content_data`, saved with `EncryptedTextSerializer`). If it is not there,
  `OnCmsLoadFailed` → `DisconnectDueToRequiredContentUpdate` + `RestartGame`. That is the gateway disconnection at 30 ms.
- **Who downloads the CMS:** `Catapult.Network.Requests.ErrorHandling.ContentUpdateStep`. It is triggered when a response carries
  `Error.ErrorCode == 471` (`CatapultStatusCode.ContentUpdateRequired`). It reads `Result<SessionTokenResponse>.Body.ContentUrl`, calls
  `IGamefuelContentService.DownloadContent(url)` (WebClient with gzip), saves a `ContentDetail` with the `ContentEtag` and repeats the login
  with `LoginRequest.ContentETag`.
- `CatapultStatusCode`: 200 Ok, 400 BadRequest, 401 Unauthorized, 403 Unauthenticated, 404 NotFound, 440 SessionExpired,
  470 ForceClientUpgrade, **471 ContentUpdateRequired**, 480 StateSyncRequired, 490 AccountNotFound, 500/502/503/504, 505 MaintenanceModeEnabled.
- **v10:** if the client's ETag is not `gprevival-1`, the login responds with the full body plus `Error {1: 471}`. If it matches,
  it responds OK. The HTTP server logs all headers of the CMS download, which for now answers 404:
  a real CMS still needs to be served (Delivery 2).
- **Test 10 (14:23, v10):** the 471 works: after each response, the client **tries to download the CMS** from `ContentUrl`
  (connection to 8443). TLS fails with `UNSUPPORTED_PROTOCOL`: Mono's WebClient (Unity 2018) offers a TLS version that
  Conscrypt on Android 16 no longer accepts as a server. Progress drops from 13% to 5% because the game stays at the login waiting for the content.
- **v11:** `ContentUrl = http://127.0.0.1:8080/cms/content` (plain HTTP). For now it answers 404; the full request is logged.
- **Test 11 (14:31, v11): Delivery 1 accomplished.** After each 471, the client does `GET /cms/content HTTP/1.1` to `127.0.0.1:8080`
  with `accept-encoding: gzip` (no User-Agent), receives 404 and repeats the login every ~1.3 s. It does not log the error in logcat.
  **Next blocker (Delivery 2):** serve a CMS that `CMSManager.LoadCMSData(string)` accepts. Its format must be extracted
  from the `CMSData`/`CMSDataGroup` classes of the dump and filled with `data/`.

## Delivery 2: the CMS
- Flow: `GamefuelContentDownloader` (WebClient, gzip) → text → `SaveContentFile` (encrypted cache with `EncryptedTextSerializer`)
  → `ParseCMSData` → `CMSManager.LoadCMSData(string)` → `CMSDataExtensions.CreateCMSData` → **MiniJSON** →
  `new CMSData(Dictionary<string, object>, …)`. If the text ends in `</body></html>`, it is flagged as error 503.
- Format (confirmed with `analysis/asset_cms_data_1.98.json`): `{ "<group>": [ { "id": "...", <fields> }, ... ], "_meta": { "<group>": {"total": n},
  "_content_version": "...", "_segments": [] } }`.
- Schema: `scripts/cms_schema.py` → `analysis/protocol/cms_schema.json` (309 classes, **143 groups**, 3,247 fields). Each group is a
  `[CMSGroup]` class; each property carries `[CMSField("key")]`, `[CMSReference]` (id from another group) or `[CMSDefault]`. The keys are read
  from the C strings loaded by the attribute generators. Simple list in `analysis/protocol/cms_groups.tsv`.
- Standalone items required by `CMSData.ParseDataGroups`: `analysis/protocol/cms_singletons.json` (ids `singleton`, `battlefield_ui`,
  `current_maps`, `standard_settings`, `misc_balance`, `exclusivity_matrix`, `settings`, `gameplay_tips`, `daily_deals_default`).
- `scripts/build_cms.py` → `data/cms/cms.json`. **Step 1:** all groups empty + those items with only `id` (9 KB).
- **v12:** the server answers `GET /cms/content` with the CMS. If `files/cms.json` exists on the phone, it uses that one (useful for iterating
  without reinstalling); otherwise, it uses `assets/diag/cms.json`.
- **Test 12 (15:07, v12): the CMS is downloaded.** The client downloads the 9 KB CMS, saves it (`files/content_data`, encrypted base64),
  repeats the login with `ContentETag=gprevival-1` (OK) and **sends its first message to the gateway**: `tipo#80982860` (most likely
  `Message<AuthenticationRequest>`), with the body `{1: {1: "gprevival-session-1", 2: "gprevival-local-1", 3: "12.28.0.0", 4: 0}}`.
  After 36 ms it cuts the gateway: it is the same `OnCmsLoadFailed` pattern. The CMS parser fails and the exception is swallowed without a log
  (`ParsingUtils` uses `IAsserts` with "Key not found: <key>").
- **v13:** `scripts/patch_libil2cpp_cmslog.py` patches the `catch` of `ParseCMSData` (0x14f7ba8) so that it calls
  `Debug.LogException(e)` instead of `ClearDetailsStore`. The CMS error now shows up in logcat (Unity tag).
  The content ETag is a CRC32 of the served CMS (`DiagProvider.cmsEtag`): if `files/cms.json` changes, the client downloads it again.
- **Test 13 (15:16, v13): the logging patch works.** CMS error: `KeyNotFoundException` in
  `Parsing.Parse[TDataCollection](def, data, referenceCache, fieldId)` ← `ParseListToDictionary` ← `ParseDictionary` ← `CMSData…`.
  An item lacks a required field (the standalone items only had `id`). logcat truncates the stack.
- **CMS v2** (`scripts/build_cms.py`): complete items. Simple → 0/false/""; `Fix` → 0; `DateTime` → ISO; arrays → [];
  enums → their first value (taken from `dump.cs`); nested objects → recursive; references → `gp_default` item of the target group;
  `[CMSDefault]` is omitted. Includes the fields of base classes. 54 items, 21 KB. Tested by copying it to `files/cms.json`.
- **Test 14 (15:26, CMS v2):** it downloads (21 KB) and the login passes with the new ETag. Same `KeyNotFoundException`.
  Cause: 8 groups were missing (`status_effects`, `ultimates`, `target_filters`, `armaments`, `area_of_effects`, `behaviour_states`,
  `status_effect_areas`, `render_texture_scenarios`). Their classes have namesakes in other namespaces that overwrote them in
  `cms_schema.py`, and references to those types came out as objects instead of IDs.
- **CMS v3:** schema fixed (317 classes, **151 groups**, 3,388 fields), 21 KB.
- **Test 15 (15:34, CMS v3):** same `KeyNotFoundException`. Findings:
  - 90 CMS attributes are on **fields** (`public X y;`), not on properties; the schema ignored them. Fixed: 324 classes, 3,435 fields.
  - `Parsing.Parse<T>` (0x1e6adb8) walks fields and properties via reflection. If a key without `[CMSDefault]` is missing, it calls
    `IAsserts.IsTrue(false, "Collection '{0}' missing field '{1}', use CMSDefault attribute")` and then does `data[key]` (→ KeyNotFound).
    In the release build `ParsingUtilsAssert` is empty (`ret`).
- **v14:** `patch_libil2cpp_cmslog.py` also redirects `ParsingUtilsAssert.IsTrue(bool, string)` and `Fail(string)` to
  `ParsingUtilsLogger.Error` → `Debug.LogError` (the IsTrue logic goes in the body of `ParsingUtilsLogger.DebugFormat`, 0x143ab04).
  The logcat will say exactly which collection and which field are missing. Includes CMS v4 (21.6 KB).
- **Test 16 (15:41, v14 + CMS v4):** no more missing fields. New error: `ArgumentException: failed to convert parameters`
  (`MonoMethod.Invoke` = a property setter, inside `Parsing.Parse`). `Parsing.ParseByType` handles enum, string, bool,
  int, uint, long, float, Fix, string[] and DateTime; the rest, with a static `Parse`. `ParseInt` only accepts `long`; `ParseFloat`,
  string/Fix/number; **`ParseFixed` only text** ("1.5": `IndexOf('.')`, `Substring`, `Int32.Parse`).
- **CMS v5:** `Fix` → `"0"`, `float` → `0.0`.
- **Test 17 (15:47, CMS v5):** still `failed to convert parameters`. `Parse<T>` uses `MethodBase.Invoke` in two places:
  the `[CMSParseFunction]` functions and, in `Dictionary<…>` fields, `ParseListToDictionary(dict, List, cache, keyId)`.
  That second case expects a **list** of items with `id`; I was sending `{}`.
- **CMS v6:** `Dictionary<…>` → `[]`.
- **Test 18 (15:50, CMS v6):** the type error disappeared. New: `NullReferenceException` in `DailyDeal.ParseReferencelessMap(object)`.
  The `[CMSParseFunction]` functions convert on their own: maps expect a JSON dictionary.
- **CMS v7:** fields with `[CMSParseFunction]`: `Dictionary` → `{}`, `List`/array → `[]`, `ParseStringAsInt` → `"0"`. The other `Dictionary` stay as `[]`.
- **Tests 19 and 20 (15:53, 15:57):** careful, the client parses the **previous cache**: the first time it downloads a new CMS, it saves it
  in the background and `ParseCMSData` reads the old file; on retries it reads the new one. With that, everything adds up:
  `levels = []` → `NullReferenceException` in `DailyDeal.ParseReferencelessMap` (expects a `level → list` dictionary);
  `levels = {}` or `{"1": []}` → `daily_deals` passes and the `failed to convert parameters` of another group appears.
- Cause of the `failed to convert parameters`: **`GameString` is a group** (`game_strings`, with the field `text`). Its 73 fields are
  `[CMSReference]` (they go as id), and the generator was setting them as text `""`.
- **CMS v9:** `GameString` → reference to `game_strings/gp_default`; `levels` → `{"1": []}`.
- **Test 21 (16:02, CMS v9):** still `failed to convert parameters` on all retries. From the code of `Parse<T>`:
  the custom function (`Invoke`) leaves the result in x19; afterwards it is assigned with `FieldInfo.SetValue` or with the property setter
  (another `MonoMethod.Invoke`). Among the items only `DailyDeal.levels` is of a generic type.
- **v15 (bisection):** `scripts/cms_bisect.py` generates 8 variants (`assets/diag/cms_var_N.json`). v0 and v7 are the full CMS;
  in v1..v6 the groups with data whose index (in `analysis/protocol/bisect_groups.txt`, 37 groups) has bit (v-1) set are emptied.
  The server serves each variant over 3 logins (471 + download, OK, OK) and logs
  "BISECTION: THIS attempt's parse uses variant N". If the error disappears in the variants with bit b, the culprit has bit b.
- **Test 22 (16:08, v15):** the bisection did not help: emptying groups breaks the `gp_default` references and `KeyNotFoundException` comes out
  first. The full variants (v0 and v7) give `failed to convert parameters`. This confirms that references are resolved during parsing.
- Analysis of `Parse<T>` at 0x1e6bbc4: the custom function is looked up with `GetMethod(FunctionName)` on type `T` and invoked with `obj = def`,
  `params = [data[key]]`. Only concrete suspect: `DailyDeal.levels`.
- **v16** (no bisection mode) + `data/cms/cms_without_daily_deals.json`: the CMS is tested with `daily_deals` empty.
- **Test 23 (16:15, v16 + CMS without daily_deals): `ParseDictionary` passes completely.** The only error is the expected one
  (`KeyNotFound` in `CMSData.ParseDataGroups`, due to the missing `daily_deals_default` item). The culprit was `DailyDeal.levels`:
  with any dictionary (even `{}`), assigning the result of `ParseReferencelessMap` gives `failed to convert parameters`;
  with a list, the function fails with `NullReferenceException`. It looks like a quirk of the game's IL2CPP on this path.
- **v17:** patch to `DailyDeal.ParseReferencelessMap` (0x161c584: `mov x0, xzr; ret`). By returning null, `Parse` skips the assignment.
  Daily deals are left empty. Back to the full CMS v9.
- **Test 24 (16:18, v17):** still `failed to convert parameters` even though the function returns null. The error comes from the function's own
  `MethodBase.Invoke` (when converting the argument), not from the assignment.
- **v18:** that call is nulled out in `Parsing.Parse<T>` (0x1e6bbc4 `bl MethodBase.Invoke` → `mov x0, xzr`). The 9 `[CMSParseFunction]` fields
  are left unassigned (daily deals, Horde levels and scores, first-win overrides, version of two assets).
  The `DailyDeal` patch was removed.
- **Test 25 (16:21, v18):** the error remains, but now it can only come from the other `Invoke` in `Parse`: `ParseListToDictionary` (0x1e6c6bc).
  For `levels`, `Parse` executes **both branches**: the custom function (needs a dictionary) and then the dictionary branch
  (needs a list). With the function nulled out, a list is enough.
- **CMS v10:** `[CMSParseFunction]` fields of type `Dictionary`/`List`/array → `[]`.
- **Test 26 (16:24, v18 + CMS v10):** same error remains. The dictionary branch calls `ParseListToDictionary<TKey, TValue>` with
  `MakeGenericMethod`; with `TValue = SlotContent[]` that generic instance is not compiled into the game's IL2CPP.
- **v19:** that call is also removed (0x1e6c6bc → nop): the empty dictionary of the exact type is assigned. **Limitation:** the CMS
  `Dictionary<…>` fields stay empty (today only `DailyDeal.levels`).

### Delivery 2 accomplished (Nov 10 2026, 16:57, on the emulator)
With the **Android 14 ARM64 emulator** (AVD `gpop`, image `system-images;android-34;google_apis;arm64-v8a`) each test takes 1–2 minutes.
Final findings and fixes:
- **`SoftLaunchAccessGate.IsUserAllowedToLogin`** (0x14b8720): Google Play license check (Java class + RSA signature). Without the Play Store
  it does not even allow attempting the login ("Sending error as not allow to log in"). Patch: always true.
- **Diagnostic patch in `MonoMethod.Invoke`** (0x1be1ed8): the `ArgumentException` "failed to convert parameters" carries the name of the
  method. That is how the real culprit came out: **`set_TimeBetweenToasts`** (`HordeBattleUiSettings.time_between_score_toasts`, `Fix` with `[CMSDefault]`).
  If a `Fix` with `[CMSDefault]` is omitted, the parser assigns the attribute's default value (float) without converting it. `Fix` values always go explicit.
- Misreading: `CMSData.ParseDataGroups` runs **before** `ParseDictionary`; the "without daily_deals" test was misleading.
  Even so, `daily_deals` was left empty and `ParseCMSGroupItem<DailyDeal>` (0x16aed40) was nulled out.
- `StreamingAssetManager.Startup` needs `asset_bundle_manifest/manifest` (remote bundles on `assets.gamefuel.info`, which no longer exist).
  It is turned off with the killswitch: `killswitches = [{"id": "streaming_assets", "killswitch_enabled": true}]` (true = feature off).
- **Result:** the CMS parses completely. The screen shows **"RETRIEVING PLAYER DATA… 15%"** (`build/emulador_cms_ok.png`) and the client
  retries on the gateway `tipo#80982860` (≈ `AuthenticationRequest`: `{1: {1: SessionToken, 2: ContentETag, 3: "12.28.0.0", 4: 0}}`), which
  is not answered yet. **Next (Delivery 3):** answer the authentication and the gateway services.
- `libil2cpp.so` patches: see `scripts/patch_libil2cpp_cmslog.py` (25 instructions). Several are for diagnostics; 3 and 4
  (reflection of `[CMSParseFunction]` and `Dictionary`) were kept as a safety net and leave those fields null.
- Tools: `scripts/build_apk.sh` (builds and signs the APK), `scripts/build_cms.py`, `scripts/cms_schema.py`.

## Delivery 3: the gateway (progress, Nov 10 2026, emulator)
- `Message<AuthenticationRequest>` (80982860) {1: Token, 2: ContentEtag, 3: ProtocolVersion ("12.28.0.0"), 4: ContinueSession}
  → `Result<AuthenticationResponse>` (98996885) {1: {1: UserId}}. **Accepted.**
- Complete tags: `scripts/proto_tags.py` fixed (only the `adrp xN; ldr xN,[xN,#off]` pattern) → 737 in `message_tags.tsv`,
  including the `Message<T>`.
- Request→response pairs: the 97 `RemoteServiceBase.SendRequest<Req, Resp>` from `script.json` → `analysis/protocol/request_pairs.json`.
- `scripts/dto_schema.py` (schema of any DTO from its `Write(T)`) + `scripts/build_responses.py`: recursive default responses
  (strings "", ids pointing to the CMS = `gp_default`, sub-messages filled, lists with one element) → `assets/diag/responses.tsv`
  (89 responses). The server answers any request that is in that table.
- `build_cms.py` forces `gp_default` items in `vanity_items`, `vanity_item_colors`, `ultimates` and `cards` (the player data references them).
- **Status:** login → CMS → authentication → `GetAllPlayerData` (692 bytes) → `StoreQuery` → `GetServerInformationQuery` (on the battle
  port 11111) → the bar reaches **100%** with no error dialog (`build/emulador_entrega3.png`). It stays there. Remaining errors,
  all content-related:
  - `TutorialManager.HasCompleteTutorialBattleRemote` → cuts off `GameController.WaitForTutorialManagerThenPreloadScenes` (menu preload).
  - `BattleServerInformation.TryParse` (the `GetServerInformationQuery` response is empty).
  - `AvatarFactory.SetVanityItems` (KeyNotFound: vanity types not defined in the CMS), `BountiesService.UpdateCachedData` (dictionary missing).
  - CMS: "No core arenas exist!", Unranked settings, and `AssetBundleDef` of `ui`/`fonts`/`avatar`/`arena01..09`/`thumpers`
    (remote bundles from `assets.gamefuel.info`, which are not in the APK).

### Delivery 3, second part: up to the main menu (emulator, 2026-11-10)
Each fix uncovered the next error. In order:
1. **Tutorial**: killswitch `tutorial` = true → `TutorialManager` considers it completed (`build_cms.py`).
2. **Battle info**: `ServerInformationQueryResponse` = {1: Region "local", 2: Url "https://127.0.0.1:11111"} (`EXTRA` in `build_responses.py`; the schema does not detect the Url getter). The client now opens a connection to the battle port and requests `GetServerInformationQuery`.
3. **Bounties**: `BountiesDto.Bounties` (field 1, `Dictionary<uint, BountyDto>`) cannot be null → one default entry (`ONE_ENTRY_MAPS`).
4. **Currencies**: CMS `currencies` = `hard_currency` (HardCurrency) and `soft_currency` (SoftCurrency); the profile carries `CurrenciesDto` with those ids (`OVERRIDE`). `CurrencyDto` = {1: Id, 2: ContentId, 3: Quantity}.
5. **Avatar**: `AvatarFactory.SetVanityItems` looks for an active item per type (`head`, `torso`, `legs`, `skincolor`, `haircolor`, `emblem`) plus `emblem_default`. The CMS creates those types and `gp_<type>` items, and `ActiveVanityItemsDto` activates them.
6. **Chests**: `gear_pack_settings['singleton']` and the `GearPacks` list empty (a `gp_default` does not exist as a gear pack).
7. **misc_settings**: 18 keys read with `Dictionary<string, MiscSetting>.get_Item` (extracted with `il2cpp_metarefs.py`), with reasonable values.
8. **Unranked**: `unranked_settings['default']` and `unranked_event_visuals['blocked']` (`UnrankedEventsService.Init`).

Result: main menu with tabs, buttons, battle button and 4 chest slots (`build/emulador_menu.png`). No text or images: the remote bundles (`fonts`, `ui`, `avatar`, `arena01..09`, `thumpers`, `startup`) are not in the APK and their server (`assets.gamefuel.info`) no longer exists.
Minor NullReferences remain: `GearPackSlotViewModel.SetUpBonusGlow` (first-win event without visuals) and `CrewsViewModel.UpdateUnlockedFeatures`.

### Fonts (2026-11-10)
- The APK does not ship any TextMeshPro font: only `SairaCondensed-* SDF Material (Instance)` materials and the style sheet. `TMP Settings` has no default font.
- This TMP version does not have `TMP_FontAsset.CreateFontAsset`, and `Font.CreateDynamicFontFromOSFont` was stripped from the binary: a system font cannot be created at runtime.
- Fonts are assigned by `FontFactory` (StreamingAssetsFactory) from the `fonts` bundle, by CMS ids (`StreamingAssetFontDataID`, `StreamingAssetFontMaterialID`). That is why texts come out empty with the warning "Please assign a Font Asset".
- Possible route: build our own `fonts` bundle with free fonts (Saira Condensed is OFL, from Google Fonts) using Unity 2018.4.12f1 and the same TMP version, serve it from the embedded server and declare it in the CMS.

### Battle test (2026-11-10)
- Tapping the orange button does nothing and leaves no warning: `MainMenuV2ViewModel.TryEnterBattle` is never reached, which requires a focused `GameModeCard` (mode carousel). Taps do arrive (the ☰ menu opens options, though invisible).
- Arenas: `ArenaData` uses `scene_name`/`is_in_core_bundle`. The APK only ships `ArenaBase`, `ArenaBaseHorde`, `ArenaTemplate` and `BattleHudTestArena`; the real arenas (`arena01..09`) were remote bundles.
- Units: the APK only has visual data, materials and loose effects (e.g. `YoungMarcusFenixLancer_VisualData`). Unit animations and audio are loaded by name (`animation/…`, `audio/…`) and no file in the APK contains them. List of 278 names in `analysis/asset_bundle_names.txt`.
- Conclusion: without the original bundles there are no visible battles. Fonts alone do not make it playable.

### Searching for the bundles on the Internet (2026-11-10)
- Original path (from `asset_cms_data_1.98.json`): `https://assets.gamefuel.info/moncton-assets/28/AssetBundles/android/<bundle>` (for example `asset_bundles_startup`, about 6 MB).
- Wayback Machine (CDX): of `assets.gamefuel.info` only the root is archived (2023). There is no URL with `moncton` in the whole `gamefuel.info` domain.
- Web searches: no copies of the bundles turn up, nor any private-server or preservation projects for Gears POP. There are only APK mirrors (which we already have) and audio extractions on The Sounds Resource.
