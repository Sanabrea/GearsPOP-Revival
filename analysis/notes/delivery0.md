# Delivery 0 (diagnostic APK session)
- APK: build/GearsPOP_diag.apk (embedded server, not tested on a device).
- Client fixed ports: login 12000, gateway 12345, battle 11111 (MonctonConfig.Config..cctor 0x14EF6D0).
- Transport: one duplex byte[] gRPC call per channel (GrpcNetConnection), default service "GrpcTransport".
- CMS via WebClient with content_data cache: possible route to inject the CMS.
- Details: analysis/startup_log.md
- RESULT (v4, tested on phone): gRPC path /GrpcTransport/raw (duplex byte[]), login by DeviceId, no Xbox. First message 211 bytes: aad8ef8f 02 varint(147) + protobuf LoginCredential. Stops at UNIMPLEMENTED → retries → ErrorMessageUI.
- Startup crash on Android 16 (SIGSEGV in the Unity 2018 memory table, "16GB" warning): fixed with scripts/patch_libunity_16gb.py (13 instructions in libunity.so). Always starts (v7).
- DELIVERY 1 (v11): Catapult protocol = protobuf-net with inheritance over /GrpcTransport/raw (see analysis/protocol/). Login answered; the server requests the CMS with error 471 ContentUpdateRequired and the game does GET http://127.0.0.1:8080/cms/content (gzip). Mono's WebClient TLS fails on Android 16, which is why the CMS goes over plain HTTP. The CMS format is still missing (Delivery 2).
- DELIVERY 2 (CMS) done on Android 14 ARM64 emulator (AVD gpop): the game reaches "RETRIEVING PLAYER DATA 15%" and waits for the response to the AuthenticationRequest (type#80982860) on the gateway. Key patches in scripts/patch_libil2cpp_cmslog.py (Play license, parser reflection), CMS in data/cms/cms.json (scripts/build_cms.py). Next: Delivery 3, answer the gateway.
- DELIVERY 3 (in progress): authentication OK; default responses for 89 requests (scripts/build_responses.py, request_pairs.json). Bar at 100%; stops due to content (tutorial, BattleServerInformation, arenas, vanity, bounties, remote asset bundles ui/fonts/arena*).

## 2026-11-10: Delivery 3 reaches the main menu (emulator)
- Tutorial turned off via killswitch, battle URL, bounties, currencies, minimal avatar, chests, misc_settings and unranked: details in analysis/startup_log.md.
- Menu visible without text/graphics: the remote asset bundles (fonts, ui, avatar, arenas) are missing. That is the next big blocker.
