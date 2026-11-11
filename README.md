# Gears POP! Revival (personal use)

The goal is to play Gears POP! again against bots, and over Wi‑Fi on a LAN. The game was shut down on April 26, 2021. The server is meant to run **inside the same phone**, with no PC needed.

> Personal and preservation use only. The game, its art and its code belong to Microsoft / Mediatonic.
> Do not distribute the APKs, the modified client or its assets. This repository is private on purpose.

**To pick the project up, start with [CONTINUING.md](CONTINUING.md).** It covers:
- machine setup;
- the build and test loop;
- the key regeneration steps;
- **what stopped the project and what is pending**.

The detailed technical log is in [analysis/startup_log.md](analysis/startup_log.md).

---

## Status (November 10, 2026)

| Area | Status |
|---|---|
| APK analysis | Done for versions 1.31, 1.50 and 1.98. All three are original builds signed by Microsoft. |
| Architecture | Confirmed. Battles are deterministic and run on the client, with a local AI; the server only relays moves. |
| Game data (CMS) | **Lost.** Being rebuilt from wikis, Pocket Gamer and videos. A minimal CMS is enough to reach the main menu. |
| IL2CPP dump | Done, in `analysis/il2cpp_dump/`. |
| Delivery 0: diagnostic APK | **Done.** The client boots and connects to the server embedded in the APK. |
| Android 16 crash | **Fixed** by `scripts/patch_libunity_16gb.py`. Unity 2018's memory table was capped at 5×4 GB; the patch raises it to 5×32 GB. |
| Delivery 1: login | **Done.** The Catapult protocol is decoded (`analysis/protocol/`). Login uses `DeviceId`, with no Xbox Live. |
| Delivery 2: CMS | **Done.** The 151-group schema was extracted from the binary, a minimal CMS is generated, and the parser is patched in `libil2cpp.so`. |
| Delivery 3: gateway | **Done in the emulator.** The client reaches the main menu (`build/emulador_menu.png`). |
| Battles | **Blocked** by the lost remote asset bundles (`fonts`, `ui`, `avatar`, `arena*`, unit animations and audio). See CONTINUING.md §2. |
| Delivery 4: LAN lobby | Not started. |
| Emulator | AVD `gpop`, Android 14 ARM64. |

---

## Contents

### `apk/`: original clients
| File | Version | Unity | Notes |
|---|---|---|---|
| `GearsPOP_1.98_arm64.apk` | 1.98 (last) | 2018.4.12f1 | Base for the patched client |
| `GearsPOP_1.50_arm64.apk` | 1.50 | 2018.4.12f1 | From APKPure. Verified: 2,822 files intact, Microsoft signature |
| `GearsPOP_1.31_arm64.apk` | 1.31 | 2018.2.3f1 | From APKMirror |

All three point to the same servers and download the same remote bundle, `asset_bundles_startup` (v28). None of them contains the CMS data or the remote bundles.

### `build/`: patched client
- **`GearsPOP_diag.apk`:** the latest diagnostic APK.
- **`work/dec/`:** the apktool tree of 1.98 with the patched `libunity.so` and `libil2cpp.so`. Its `assets/diag/` folder holds the embedded server's data. `scripts/build_apk.sh` builds from this tree.
- **`emulador_*.png`:** emulator screenshots.

### `server_diag/`: the embedded server
Java source for `gpdiag.DiagProvider`. It provides login, the CMS over HTTP, the gateway (gRPC/HTTP2) and the battle port.

### `data/`: rebuilt game data
| File | What it is |
|---|---|
| `active_roster.csv` | **Which pins are in the game for now.** 43 are active: 40 complete and 3 with estimated fields. 21 are hidden because they have no stats. Also flags pins that may be missing a model. |
| `gears_pop_pins_consolidated_v3.csv` | **Main table.** 64 pins across three eras: `base_L1_*` (launch, level 1), `mid2019_*` (late 2019) and `closure_*` (shutdown). Each row cites its sources. |
| `gears_pop_pin_upgrade_costs.csv` | Upgrade cost by rarity and level: copies, coins and XP. Validated 100% against `depressifier`. |
| `gears_pop_player_level_xp.csv` | XP per player level (2–20). Validated 100%. |
| `cms/` | The generated CMS, plus a variant without `daily_deals`. |
| `raw_sources/` | Raw per-source data and earlier versions of the main table. |

### `analysis/`: what was extracted from the APK
- **`startup_log.md`:** the full technical log, covering startup order, crashes, patches and deliveries.
- **`protocol/`:**
  - the Catapult message tags;
  - the request/response pairs;
  - the CMS schema and singletons;
  - the gateway responses.
- **`il2cpp_dump/`:** Il2CppDumper output (`dump.cs`, `script.json`, …).
- **`il2cpp_metadata_strings_1.98.txt`:** every class, method and field name.
- **`config_decoded_*.json`:** `assets/Config.json` decoded. It lists the login, gateway, battle and CMS servers.
- **`asset_cms_data_1.98.json`:** the remote bundle manifest and the original bundle base URL.
- **`asset_bundle_names.txt`:** the 278 animation and audio names the client requests from the remote bundles.
- **`pinned_ca_1.98.crt`:** the Mediatonic/Catapult CA the original client trusts. It expired in 2020.
- **`notes/`:** notes from Delivery 0 and intermediate dumps.

### `sources/`: archived external material
- **`wikis/`:** full dumps of the two fan wikis (WikiTeam, Internet Archive), licensed CC-BY-SA.
- **`microsoft_store/`:** the Microsoft catalog entry. The package is `Microsoft.MonctonBaseGame`, an encrypted EAppxBundle of 275 MB.
- **`github/`:** data from `Jschii/gears-pop-depressifier`: the 64 pins with rarity, costs and Horde rewards.
- **`user_screenshots/`:** in-game stat cards for Anya Stroud and Gabe Díaz, provided by the user.

### `scripts/`
These scripts extract data, generate the server content, patch the libraries and build the APK. Run Python scripts with `python3 -I` and pass paths as arguments. CONTINUING.md §4–5 explains each tool. `scripts/aux/` holds smaller helpers and test harnesses.

---

## Key technical findings

- **Engine:** Unity IL2CPP (`libil2cpp.so` plus `global-metadata.dat` v24, unencrypted). The client is arm64-v8a only.
- **Backend:** Mediatonic's "Catapult" over **gRPC** (`libgrpc_csharp_ext.so`), serialized with protobuf-net. Login originally went through Xbox Live (`libXal.Unity.so`).
- **Servers:** listed in `Config.json`, base64-encoded:
  - `login-production.moncton.oncatapult.com`
  - `gateway-production.moncton.oncatapult.com`
  - `mpgateways-production.moncton.oncatapult.com`
  - CMS: `content.gamefuel.info`
  - assets: `assets.gamefuel.info`

  None of them resolves any more, and none has useful Wayback copies.
- **Battles:** `Catapult.Multiplayer.Deterministic`. The simulation is deterministic and runs on the client; the server only relays moves.
- **Bots:** a local AI (`StartBattleOffline`, `SetupAiPlayers`, `BotBattle`). Its parameters came from the CMS (`bot_match_ai`).
- **Battle server address:** sent in the matchmaking response (`ServerHost` / `ServerPort`). This means a phone could host the Wi‑Fi lobby.
- **Reference protocol:** `klukule/FallGuys.Protocol` (MIT) documents the Catapult core: headers and status codes.
- **Level scaling:** estimated from 10 pins. HP rises by about 8.3% of the level-1 value per level, and damage/DPS by about 9%, which fits a linear addition best.

## Roster decision (November 10, 2026)

Pins without stats are **hidden**: they stay out of the rebuilt CMS and do not appear in the game. They come back if their data turns up.
- **Active (43):**
  - By type: 31 troops, 6 projectiles, 3 fortifications (Decoy, Sentry, Shock Barrier) and 3 ultimate abilities (Seeder, Emergence Hole, Windflare).
  - By rarity: 15 common, 10 rare, 13 epic and 5 legendary.
- **With estimated values (3, marked as estimated):**
  - Kait and Sentinel: speed 5.
  - Stun Tracker: explodes on contact, with no fire rate or range.
- **Possibly missing a model (4):** Kait, Carmine, Decoy and Shock Barrier.
- **Hidden (21):** the post-launch pins that have no stats (listed in CONTINUING.md §2.2).

## Main sources

### Data
- **Fan wikis on the Internet Archive:** `wiki-gears_popfandomcom` and `wiki-gearspopfandomcom` (archived copies in `sources/wikis/`).
- **Pocket Gamer:** the pin list by Dave Aubrey, August 28, 2019. It is the source of `data/raw_sources/pocketgamer_2019_pin_stats.csv`.
- **TrueAchievements:**
  - BLOWFISH666's guide (costs and XP): https://www.trueachievements.com/a280703/major-achievement
  - patch notes from 2019 to 2021.
- **GitHub:**
  - https://github.com/Jschii/gears-pop-depressifier (game data)
  - https://github.com/klukule/FallGuys.Protocol (Catapult protocol)
  - https://github.com/klukule/CatapultServer.Proxy
- **YouTube:**
  - https://www.youtube.com/watch?v=XHyRTJkLgKs (RAWR, late 2019)
  - https://www.youtube.com/watch?v=Ha930c-gLA4 (launch, level 1)
  - https://www.youtube.com/watch?v=-pf8ebjMAHc (Rapnja City, shutdown)
- **Gears of War Wiki (Fandom):** roles and types (`data/raw_sources/gow_wiki_roles.txt`).
- **User screenshots:** Anya Stroud and Gabe Díaz.

### Searches for the asset bundles
All of these came back negative:
- the Wayback Machine CDX for `assets.gamefuel.info`;
- web searches for bundle copies or other revival projects;
- The Sounds Resource, which has audio rips but not the bundles.

CONTINUING.md §2.1 has the details.
