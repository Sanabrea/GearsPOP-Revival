# Gears POP! Revival (uso personal)

Objetivo: volver a jugar Gears POP! (cerrado el 26 de abril de 2021) contra bots y en LAN por Wi‑Fi,
con el servidor corriendo **dentro del mismo teléfono** (sin PC).

> Uso personal y de preservación. El juego, sus gráficos y su código son de Microsoft / Mediatonic:
> no distribuir el APK modificado ni sus assets.

---

## Estado (10 de noviembre de 2026)

| Área | Estado |
|---|---|
| Análisis del APK | Hecho (versiones 1.31, 1.50 y 1.98, todas originales firmadas por Microsoft) |
| Arquitectura | Confirmada: batalla determinista en el cliente + IA local; el servidor solo reenvía jugadas |
| Datos del juego (CMS) | **Perdidos**. Reconstrucción en curso con wikis, Pocket Gamer y videos |
| Gráficos faltantes | 4–5 modelos (Kait, Carmine, Decoy, Barrier; quizá la malla del Stun Tracker) |
| Herramientas | Instaladas: OpenJDK 17, apktool, Android SDK (platform-tools, build-tools 34, android-34), .NET 10, Il2CppDumper 6.7.46 (`~/Tools`). AssetRipper: no; emulador Android: sí |
| Volcado IL2CPP | Hecho: `analysis/il2cpp_dump/`. Arranque resumido en `analysis/arranque.md` (puertos 12000/12345/11111, transporte gRPC duplex) |
| Entrega 0: APK de diagnóstico | **Hecha** (v4, probada en el teléfono). El juego abre y se conecta al servidor embebido: `/GrpcTransport/raw` en 12000, login por `DeviceId` (sin Xbox). Se detiene porque el servidor aún no responde al login |
| Crash en Android 16 | **Corregido** con `scripts/patch_libunity_16gb.py` (tabla de memoria de Unity 2018 limitada a 5×4 GB → 5×32 GB). Arranca siempre |
| Entrega 1: login | **Hecha** (v11). Protocolo Catapult decodificado (`analysis/protocolo/`). El servidor responde el login y pide el CMS (código 471). El juego descarga `GET /cms/content` por HTTP en 8080 |
| Entrega 2: CMS | **Hecha** (16:57, emulador). Esquema de 151 grupos sacado del binario (`analysis/protocolo/cms_schema.json`), CMS mínimo generado (`scripts/build_cms.py` → `data/cms/cms.json`) y parches del parser en `libil2cpp.so`. El juego llega a "RETRIEVING PLAYER DATA… 15%" |
| Entrega 3: gateway | **Hecha (emulador); batalla bloqueada por paquetes remotos.** Llega al menú principal sin excepciones graves (`build/emulador_menu.png`). Respuestas del gateway generadas desde el binario (`scripts/build_responses.py`) y contenido mínimo en el CMS (`scripts/build_cms.py`). Sin textos ni gráficos: faltan los paquetes remotos `fonts`/`ui`/`avatar`/`arena*` |
| Emulador | Instalado: AVD `gpop` (Android 14 ARM64). `adb install` + logcat directo |

---

## Contenido

### `apk/`
| Archivo | Versión | Unity | Notas |
|---|---|---|---|
| `GearsPOP_1.98_arm64.apk` | 1.98 (última) | 2018.4.12f1 | Base para el parche |
| `GearsPOP_1.50_arm64.apk` | 1.50 | 2018.4.12f1 | De APKPure; verificado: 2,822 archivos intactos y firma de Microsoft |
| `GearsPOP_1.31_arm64.apk` | 1.31 | 2018.2.3f1 | De APKMirror |

Las tres apuntan a los mismos servidores y descargan el mismo paquete remoto `asset_bundles_startup` (v28).
Ninguna trae los datos del CMS ni los modelos faltantes.

### `data/`: datos del juego reconstruidos
| Archivo | Qué es |
|---|---|
| `roster_activo.csv` | **Qué pins entran al juego por ahora.** 43 activos (40 completos + 3 con campos estimados) y 21 ocultos sin stats. Incluye el riesgo de modelo faltante |
| `gears_pop_pins_consolidated_v3.csv` | **Tabla principal.** La columna `roster_status` dice si el pin está activo, activo con estimados u oculto. 64 pins con tres épocas: `base_L1_*` (lanzamiento, nivel 1), `mid2019_*` (finales de 2019) y `closure_*` (cierre). Cada fila indica sus fuentes y notas |
| `gears_pop_pin_upgrade_costs.csv` | Costo de mejora por rareza y nivel (copias, monedas, XP). Validado al 100% contra `depressifier` |
| `gears_pop_player_level_xp.csv` | XP por nivel de jugador (2–20). Validado al 100% |

`data/fuentes/` guarda los datos crudos de cada fuente y las versiones anteriores de la tabla:
- `pocketgamer_2019_pin_stats.csv`: tu CSV de Pocket Gamer (agosto de 2019)
- `gearspop_wiki_stats_2019.csv`: fichas de la wiki de fans (agosto de 2019)
- `gears_pop_pins_video_launch_L1.csv`: 36 pins en nivel 1, del video `Ha930c-gLA4` (lanzamiento)
- `gears_pop_pins_video_rawr.csv`: 22 pins con ganancia por nivel, del video `XHyRTJkLgKs` (RAWR, finales de 2019)
- `gears_pop_pins_video_rapnja_cierre.csv`: 63 pins al cierre (rareza, costo, rol, tipo) y las 3 habilidades definitivas, del video `-pf8ebjMAHc` (Rapnja City)
- `gow_wiki_roles.txt`: rol y tipo según la Gears of War Wiki (CC-BY-SA)
- `gears_pop_pins_capturas_usuario.csv`: Anya Stroud y Gabe Díaz en nivel 1, de capturas enviadas por el usuario (imágenes en `sources/capturas_usuario/`)
- `gears_pop_pins_consolidated.csv`, `..._v2.csv`: versiones anteriores de la tabla

### `analysis/`: lo que se sacó del APK
- `il2cpp_metadata_strings_1.98.txt`: todos los nombres de clases, métodos y campos (82k líneas)
- `config_decoded_*.json`: `assets/Config.json` decodificado (servidores de login, gateway, batallas y CMS)
- `asset_cms_data_1.98.json`: manifiesto del paquete remoto y lista de sus 21 assets
- `pinned_ca_1.98.crt`: CA de Mediatonic/Catapult en la que confía el juego (venció en 2020)

### `sources/`
- `wikis/`: copias completas de las dos wikis de fans (WikiTeam, Internet Archive), CC-BY-SA
- `microsoft_store/`: ficha del catálogo de Microsoft (paquete `Microsoft.MonctonBaseGame`, EAppxBundle cifrado, 275 MB)
- `github/`: datos de `Jschii/gears-pop-depressifier` (lista de 64 pins con rareza, costos, recompensas de Horda)
- `capturas_usuario/`: capturas de fichas del juego enviadas por el usuario (Anya Stroud, Gabe Díaz)

### `scripts/`
Scripts de Python usados para extraer y cruzar datos (las rutas se pasan como argumentos; correr con `python3 -I`).
`yt.py` busca videos en YouTube; los demás extraen las wikis y arman la tabla consolidada.

---

## Hallazgos técnicos clave

- **Motor:** Unity IL2CPP (`libil2cpp.so` + `global-metadata.dat` v24, sin cifrar). Solo arm64-v8a.
- **Backend:** "Catapult" de Mediatonic sobre **gRPC** (`libgrpc_csharp_ext.so`). Login con Xbox Live (`libXal.Unity.so`).
- **Servidores** (en `Config.json`, base64): `login-production.moncton.oncatapult.com`,
  `gateway-production.moncton.oncatapult.com`, `mpgateways-production.moncton.oncatapult.com`,
  CMS `content.gamefuel.info`, assets `assets.gamefuel.info`. Todos sin DNS; sin copias en Wayback.
- **Batalla:** `Catapult.Multiplayer.Deterministic`: simulación determinista en el cliente; el servidor solo reenvía jugadas.
- **Bots:** IA local (`StartBattleOffline`, `SetupAiPlayers`, `BotBattle`). Sus parámetros venían del CMS (`bot_match_ai`).
- **Dirección del servidor de batalla:** llega en la respuesta del matchmaking (`ServerHost` / `ServerPort`).
  Así un teléfono puede ser anfitrión del lobby por Wi‑Fi.
- **Protocolo de referencia:** `klukule/FallGuys.Protocol` (MIT) documenta el núcleo de Catapult (encabezados, códigos de estado).
- **Escalado por nivel (estimado con 10 pins):** vida ≈ +8.3% del valor de nivel 1 por nivel; daño/DPS ≈ +9%. Encaja mejor con suma lineal.

## Plan
1. Instalar herramientas y volcar el código (mensajes gRPC, estructura del CMS).
2. Servidor embebido en el APK (Kotlin + gRPC): login falso, gateway mínimo, CMS por HTTP, relay de batallas, descubrimiento en la red.
3. Parche del cliente: `Config.json` → `127.0.0.1`, CA propia, saltar Xbox Live, desactivar Firebase/Braze/compras.
4. Entregas de prueba: 0 diagnóstico → 1 pantalla de carga → 2 primera batalla → 3 juego completo contra bots → 4 lobby Wi‑Fi.

## Roster activo (decisión del 10 de noviembre de 2026)
Para avanzar, los pins sin stats quedan **ocultos**: no entran al CMS reconstruido ni aparecen en el juego.
Se reactivan cuando aparezcan sus datos.
- **Activos (43):** 31 tropas, 6 proyectiles, 3 fortificaciones (Decoy, Sentry, Shock Barrier) y 3 habilidades definitivas (Seeder, Emergence Hole, Windflare).
  Por rareza: 15 comunes, 10 raros, 13 épicos y 5 legendarios.
- **Con valores estimados (3, marcados `ESTIMADO`):** Kait y Sentinel (velocidad 5), Stun Tracker (explota al contacto, sin cadencia ni alcance).
- **Riesgo de modelo faltante (4):** Kait, Carmine, Decoy y Shock Barrier. Siguen activos; si al probar no tienen modelo, se ocultan también.
- **Ocultos (21):** los pins posteriores al lanzamiento sin stats (lista abajo).

## Lo que falta
- Stats de combate de 21 pins posteriores al lanzamiento (RAAM, Sid, Alex Brand, Bruce, Mina Jinn, Hoffman,
  Winter Kait, Jack, Fahz, Sam, Bernadette, Del Walker, Tai Kaliso, Scion, Juvies, Ticker, Onyx Guards, Spotters,
  Drop Pod, Power Generator, Shock Sentry). Ya tienen rol, tipo, rareza y costo. Anya y Gabe ya están (capturas del usuario).
- Kait y Sentinel: solo stats de Pocket Gamer.
- Detalle de habilidades, proyectiles y parámetros de la IA.
- Modelos de Kait, Carmine, Decoy y Barrier. Fuentes posibles: un caché viejo
  (`Android/data/com.microsoft.gearspop`, `%LOCALAPPDATA%\Packages\Microsoft.MonctonBaseGame_8wekyb3d8bbwe`,
  backup de iPhone) o MyllaDinX (extrajo el modelo de Kait).

## Fuentes principales
- Wikis de fans en Internet Archive: `wiki-gears_popfandomcom`, `wiki-gearspopfandomcom`
- Pocket Gamer: lista de pins (Dave Aubrey, 28 de agosto de 2019)
- TrueAchievements: guía de BLOWFISH666 (costos y XP) y notas de parche de 2019–2021
- GitHub: `Jschii/gears-pop-depressifier`, `klukule/FallGuys.Protocol`, `klukule/CatapultServer.Proxy`
- YouTube: `XHyRTJkLgKs` (RAWR), `Ha930c-gLA4` (lanzamiento, nivel 1), `-pf8ebjMAHc` (Rapnja City, cierre)
- Gears of War Wiki (Fandom): roles y tipos
