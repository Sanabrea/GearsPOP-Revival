# Continuing the project

This guide is for whoever picks the project up next. It covers:
- how to set up the machine;
- how to rebuild and test;
- what is done;
- **what stopped the project**;
- what is still pending.

The detailed day-by-day log, with every crash, its cause and its fix, is in [analysis/startup_log.md](analysis/startup_log.md).

> Personal / preservation use only. The game, its art and its code belong to Microsoft / Mediatonic.
> Do not distribute the APKs, the modified client or its assets. This repository is private on purpose.

---

## 1. Where things stand (November 10, 2026)

| Milestone | Result |
|---|---|
| Delivery 0: diagnostic APK | Done. The client boots on Android 14 and 16 (memory-table patch in `libunity.so`) and talks to a server embedded in the APK. |
| Delivery 1: login | Done. The Catapult protocol is decoded. The fake login works with a device id, without Xbox Live. |
| Delivery 2: CMS | Done. The schema (151 groups) was extracted from the binary, a minimal CMS is generated, and the parser is patched. |
| Delivery 3: gateway | Done in the emulator. The client reaches the **main menu** (`build/emulador_menu.png`) without major exceptions. |
| Battles | **Blocked.** See section 2. |
| Delivery 4: LAN lobby | Not started. It was deliberately left for last. |

---

## 2. What stopped the project (blockers)

### 2.1 The remote asset bundles are lost (main blocker)

The APK contains only code plus a small startup bundle. Everything visual and audible was downloaded at runtime from:

```
https://assets.gamefuel.info/moncton-assets/28/AssetBundles/android/<bundle>
```

That host no longer resolves. The bundle list and manifest are in `analysis/asset_cms_data_1.98.json`. The 278 animation and audio asset names the client asks for are in `analysis/asset_bundle_names.txt`.

**Missing:**
- `fonts`: all TextMeshPro fonts, so the client shows no text at all.
- `ui`: the menu carousels and cards.
- `avatar`
- `arena*`: the arena scenes.
- Unit animations (`animation/…`) and audio (`audio/…`).

**Why there is no workaround inside the APK:**
- **Fonts.** TMP fonts come only through `FontFactory`, using the CMS ids `StreamingAssetFontDataID` and `StreamingAssetFontMaterialID`. The APK has no `TMP_FontAsset`. This TMP build has no `CreateFontAsset`, and `Font.CreateDynamicFontFromOSFont` was stripped, so falling back to a system font is impossible.
- **Battle button.** It does nothing. `MainMenuV2ViewModel.TryEnterBattle` needs a focused `GameModeCard`, and that card lives in the missing `ui` bundle.
- **Arenas.** Only `ArenaBase`, `ArenaBaseHorde`, `ArenaTemplate` and `BattleHudTestArena` are built into the APK (`ArenaData.is_in_core_bundle`). Even if a battle were forced to start, the units have no animations or sounds.

**Searches already done, all negative:**
- **Wayback Machine CDX** for `assets.gamefuel.info`: only the site root was archived. Nothing exists under `moncton-assets`.
- **Web searches** for copies of the bundles or for other revival projects: found only APK mirrors.
- **The Sounds Resource:** has some ripped audio, not the bundles themselves.
- No modified APKs were downloaded, by project rule.
- The Windows package (`Microsoft.MonctonBaseGame`, EAppxBundle) is DRM-encrypted and was **not** decrypted, also by project rule.

**Ways forward, from most to least realistic:**
1. **Find a device or backup that still has the cache.** Possible locations:
   - An old Android phone or tablet that ran the game: `Android/data/com.microsoft.gearspop/`.
   - An iPhone backup.
   - A Windows install, under `%LOCALAPPDATA%\Packages\Microsoft.MonctonBaseGame_8wekyb3d8bbwe`.

   If found, serve the files from the embedded server and point `asset_bundles` in the CMS at it. With everything else already built, this should take days of work.
2. **Ask Gears of War and preservation communities** (Reddit, Discord) for that cache, using the exact bundle list above.
3. **Build replacement bundles** with the **Unity 2018.4.12f1 Editor** and the same TextMeshPro version. Start with a `fonts` bundle using an OFL font such as Saira Condensed, which would bring text back. Then do `ui`. This is a large job: it needs a Unity account and a multi-GB download, and recreating the UI and units is close to rebuilding the game's art.
4. Patch the client to call `StartBattleOffline` straight into `ArenaBase`. This would show the battle logic running, but without animations or sound.

### 2.2 The game data (CMS) is lost

The real CMS content is not archived anywhere. `scripts/build_cms.py` generates a **minimal** CMS that is just enough to reach the menu. Real values for the pins come from:
- the fan wikis;
- Pocket Gamer;
- TrueAchievements;
- videos;
- the user's own screenshots.

The consolidated table is `data/gears_pop_pins_consolidated_v3.csv` and the roster decision is `data/active_roster.csv`.

**Still missing:**
- Combat stats for **21 post-launch pins**: RAAM, Sid, Alex Brand, Bruce, Mina Jinn, Hoffman, Winter Kait, Jack, Fahz, Sam, Bernadette, Del Walker, Tai Kaliso, Scion, Juvies, Ticker, Onyx Guards, Spotters, Drop Pod, Power Generator and Shock Sentry. These are hidden for now.
- **Kait and Sentinel:** only Pocket Gamer stats are available. **Stun Tracker:** some values are estimated.
- Ability, projectile and AI (`bot_match_ai`) parameters.
- **Possibly missing models:** Kait, Carmine, Decoy and Shock Barrier.

### 2.3 Smaller open issues

- Two minor exceptions remain in the menu: `GearPackSlotViewModel.SetUpBonusGlow` and `CrewsViewModel.UpdateUnlockedFeatures`. Both are NullReferenceExceptions and neither blocks anything.
- The latest APK was tested only in the emulator; the last test on a physical phone was before Delivery 3.
- The battle server (port 11111, TLS) is listening, but no battle has ever started, so it is untested.
- `scripts/dto_schema.py` sometimes misses getters. For example, it missed `Url`, field 2 of `ServerInformationQueryResponse`. When that happens, add the field by hand in `EXTRA` in `scripts/build_responses.py`.

---

## 3. Machine setup (macOS, Apple Silicon)

The original setup was:
- **Homebrew:** `openjdk@17`, `apktool`, and `android-commandlinetools`, installed at `/opt/homebrew/share/android-commandlinetools`.
- **SDK packages:**
  ```bash
  sdkmanager "platform-tools" "build-tools;34.0.0" "platforms;android-34" "emulator" "system-images;android-34;google_apis;arm64-v8a"
  ```
- **Emulator:** create the AVD, then start it.
  ```bash
  avdmanager create avd -n gpop -k "system-images;android-34;google_apis;arm64-v8a"
  ```
  ```bash
  emulator -avd gpop
  ```
- **Il2CppDumper 6.7.46**, kept in `~/Tools`, running on .NET. Only needed to regenerate `analysis/il2cpp_dump/`, which is already committed.
- **Python 3:** run every script with `python3 -I`, and pass paths as arguments.

The emulator screen is 1080×2400.

### Signing and TLS keys (not in the repo)

The repo does not contain `build/keys/`. Create it again like this:

1. Make the local CA. The client trusts `assets/certs/ca.crt` inside the APK.
   ```bash
   openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=GearsPOP Revival Local CA" -keyout build/keys/ca.key -out build/keys/ca.crt
   ```
2. Issue the server certificate, signed by that CA. Its SANs are in `scripts/keys/san.ext`.
   ```bash
   openssl req -newkey rsa:2048 -nodes -subj "/CN=localhost" -keyout build/keys/server.key -out build/keys/server.csr
   ```
   ```bash
   openssl x509 -req -in build/keys/server.csr -CA build/keys/ca.crt -CAkey build/keys/ca.key -CAcreateserial -days 3650 -extfile scripts/keys/san.ext -out build/keys/server.crt
   ```
3. Package the server key for the embedded server. Its password is `gpdiag`, and `DiagProvider` loads it from `assets/diag/server.p12`.
   ```bash
   openssl pkcs12 -export -inkey build/keys/server.key -in build/keys/server.crt -passout pass:gpdiag -out build/keys/server.p12
   ```
4. Create the APK signing keystore. Its password is `gpdiag-sign`, as used in `scripts/build_apk.sh`.
   ```bash
   keytool -genkeypair -keystore build/keys/sign.jks -storepass gpdiag-sign -keypass gpdiag-sign -alias gpdiag -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=gpdiag"
   ```
5. Copy the new files into the APK tree:
   - `ca.crt` goes to `build/work/dec/assets/certs/ca.crt`.
   - `server.p12` goes to `build/work/dec/assets/diag/server.p12`.

The committed APK tree already contains the current CA and `server.p12`, so steps 1–3 are only needed if you want fresh keys. A new `sign.jks` means you must uninstall the old app before installing the new APK.

---

## 4. Build and test loop

`build/work/dec/` is the apktool tree of version 1.98, **already patched**. It contains:
- `lib/arm64-v8a/libunity.so`, with the Android 16 memory-table fix;
- `libil2cpp.so`, with the CMS parser and logging patches;
- `assets/diag/`, holding the CMS, the gateway responses and the message tags.

The unpatched originals are in `apk/`.

1. **Regenerate the CMS** with `scripts/build_cms.py`, then copy the output into the APK tree:
   ```bash
   python3 -I scripts/build_cms.py analysis/protocol/cms_schema.json analysis/protocol/cms_singletons.json analysis/il2cpp_dump/dump.cs data/cms/cms.json
   ```
   ```bash
   cp data/cms/cms.json build/work/dec/assets/diag/cms.json
   ```
2. **Regenerate the gateway responses** with `scripts/build_responses.py`, then copy them into `analysis/protocol/`:
   ```bash
   python3 -I scripts/build_responses.py analysis/il2cpp_dump build/work/dec/lib/arm64-v8a/libil2cpp.so analysis/protocol/message_tags.tsv build/work/dec/assets/diag/responses.tsv
   ```
   ```bash
   cp build/work/dec/assets/diag/responses.tsv analysis/protocol/
   ```
3. **Build the APK.** This compiles `server_diag/` into `classes2.dex`, rebuilds, aligns and signs `build/GearsPOP_diag.apk`.
   ```bash
   scripts/build_apk.sh
   ```
4. **Install it:**
   ```bash
   adb install -r build/GearsPOP_diag.apk
   ```
5. **Restart the game and show the relevant logcat lines:**
   ```bash
   scripts/aux/run.sh 50
   ```

**Gotchas:**
- After the CMS changes, **launch the game twice**. On the first download the client still parses the previous cached copy.
- Killswitches are inverted: `killswitch_enabled: true` turns the feature **off**. The tutorial and streaming-assets killswitches are on, which disables both features.
- The embedded server is a Java `ContentProvider` (`gpdiag.DiagProvider`). It listens on these ports:

  | Port | Service |
  |---|---|
  | 12000 | login, gRPC |
  | 12345 | gateway |
  | 11111 | battle, TLS |
  | 8080 | CMS, HTTP |

---

## 5. Reverse-engineering tools

| Tool | What it does |
|---|---|
| `scripts/il2cpp_calls.py` | Pseudo-decompiles a method, listing the calls it makes. |
| `scripts/il2cpp_xrefs.py` | Lists the callers of a method. |
| `scripts/il2cpp_metarefs.py` | Finds the code that references a string literal or metadata name. |
| `scripts/dto_schema.py` | Builds the protobuf schema of the DTOs from the `GeneratedProtoSerializer.Write` functions. |
| `scripts/proto_tags.py`, `scripts/proto_fields.py`, `scripts/aux/protowalk*.py`, `scripts/aux/fields.py` | Extract message tags and fields. |
| `scripts/cms_schema.py`, `scripts/cms_groups.py`, `scripts/cms_bisect.py` | Build the CMS schema and bisect a failing CMS group. |
| `scripts/aux/find.py` | Runs a regex over the method names in `script.json`. |
| `scripts/aux/patch_arm64.s` | The arm64 assembly used for the patches. |
| `scripts/aux/h2test/`, `scripts/aux/hptest/`, `scripts/aux/gen/` | HTTP/2 and HPACK test harnesses written while building the gRPC server. |
| `analysis/notes/` | Notes from Delivery 0 and intermediate dumps: the bundle list, CMS group parsing and singleton references. |

---

## 6. External sources used

The full list, with what each source contributed, is in the README under "Main sources". Locally archived copies are in `sources/`.
