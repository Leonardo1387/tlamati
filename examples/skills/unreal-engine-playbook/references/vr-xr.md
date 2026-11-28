# VR / XR: confort, rendimiento y locomoción (Unreal 5.8.4)

Destilado 27-nov-2026 de 3 fuentes del corpus:
`raw/xr_best_practices_in_unreal_engine.txt` (12.8K), `raw/vr_template_in_unreal_engine.txt`
(8.1K), `raw/meta_vr_locomotion_fundador.txt` (15.5K, texto plano del fundador).
Todo es **[DOC]** salvo lo marcado **[MEDIDO]**. Meta del proyecto: recorridos VR.

## 0. CONTRADICCIONES con el proyecto actual (leer antes de portar a VR)
Lo que hoy hace la maqueta para verse bien en monitor **choca** con lo que pide VR:
| Decisión actual | Para VR la doc dice | Acción al portar |
|---|---|---|
| Lumen GI (`r.DynamicGlobalIlluminationMethod=1`, DefaultEngine.ini) | "Screen Space GI genera diferencias entre los dos ojos → malestar. Usar **Static Lights y Lightmaps**" | Cambiar a iluminación estática bakeada |
| Normal maps (48 texturas con `nor_gl`) | "En VR los normal maps se ven **planos**: no consideran display binocular ni motion parallax" | Usar **Parallax Mapping** para profundidad, o aceptar el aplanamiento |
| Post-proceso (bloom, eye adaptation) | "Evitar Depth of Field y Motion Blur" | Desactivar DoF/MotionBlur |
| SSR / Ray Tracing | "Usar **Reflection Probes** en vez de SSR (más baratas). RT no mantiene resolución+framerate en VR" | Reflection Probes |
| Transparencia (vidrio_templado, baranda) | "Transparencia se re-evalúa por frame; en VR es muy costosa" | Minimizar / fakear |
- **[MEDIDO]** El nivel actual corre Lumen y eye adaptation por default (ver
  lighting-exposure.md). Para VR hay que re-configurar: es un proyecto aparte o un modo.

## 1. Setup de proyecto VR [DOC]
- **Empezar con el VR Template** (categoría Games): trae todo lo necesario para UE5.
- Si se crea desde cero (C++ o Blueprint): Quality Preset **Scalable**, Raytracing
  **Disabled**, Starter Content **Disabled** (arranca con framerate bueno y se agregan features).
- Project Settings a activar: Description → **Start In VR**; Rendering → Forward Renderer →
  **Forward Shading**; Default Settings → Anti-Aliasing = **MSAA**; Rendering → VR →
  **Instanced Stereo**; **Mobile HDR = False**.
- Framerate: General Settings → **desactivar Smooth Frame Rate, Use Fixed Frame Rate** y
  **Custom TimeStep = None** (las apps VR controlan su propio framerate).
- .ini recomendado (`Config/DefaultEngine.ini` bajo `[SystemSettings]`):
  `vr.PixelDensity=1  r.SeparateTranslucency=0  r.HZBOcclusion=0  r.MotionBlurQuality=0
   r.PostProcessAAQuality=3  r.BloomQuality=1  r.EyeAdaptationQuality=0
   r.AmbientOcclusionLevels=0  r.SSR.Quality=1  r.DepthOfFieldQuality=...`
  Nota: **`r.EyeAdaptationQuality=0`** — en VR se apaga la auto-exposición (contradice el
  tuning de lighting-exposure.md, que es para monitor).

## 2. Frame rate objetivo por dispositivo [DOC]
Oculus Rift S 90 · Quest 1 72 · Quest 2 situacional 72/80/90/120 · HTC Vive 90 ·
Vive Pro 90 · Valve Index 90 mín (hasta 144) · HP Reverb 90 · WMR 90 ·
PSVR situacional 60/120, 90/90, 120/120.
Framerate bajo causa simulation sickness → optimizar es prioridad.

## 3. Confort / anti-mareo (dos fuentes coinciden) [DOC]
Reglas de Epic XR + guía de locomoción de Meta:
- **El usuario controla la cámara, siempre.** Nada de cámaras cinemáticas, head bobbing ni
  camera shake que le quiten el control.
- **FOV lo fija el SDK del dispositivo**: NO modificarlo en UE ni dejarlo modificable
  (debe casar con la geometría física del headset y sus lentes).
- **La velocidad de movimiento NO debe cambiar gradualmente**: el usuario arranca a
  velocidad completa, sin aceleración progresiva.
- **Luces y colores más tenues**, evitar smearing: la iluminación fuerte y vibrante en VR
  provoca sickness más rápido.
- Evitar **Depth of Field y Motion Blur**.
- Ajustar character height/width/speed/camera location: difieren de un personaje no-VR.

## 4. Locomoción (Meta, texto del fundador) [DOC]
- **Confort = reducir vección** (la discrepancia entre lo que ve el ojo y lo que siente el
  cuerpo). Todo el diseño de locomoción gira alrededor de eso.
- **Snap turn es la opción de confort** (giros de 30/45/90°); smooth turn da más control
  pero marea más. **Ofrecer ambos.**
- **Teleport = confort, slide (smooth locomotion) = libertad.** Defaults confortables,
  las opciones intensas siempre opt-in.
- **Velocidades ancladas al mundo real: ~3 mph caminar, ~6 mph correr.** Si el avatar va
  más rápido que eso, el optic flow provoca náusea.
- Técnicas: **vignette** (oscurecer bordes al moverse), **blink** (parpadeo a negro durante
  el slide), **dash** (desplazamiento rápido de velocidad constante en teleport),
  **steps** (híbrido slide+teleport con blink segmentado, para ajustes finos en espacios chicos).
- Aceleración: **breve e infrecuente**; restringir ejes, controlar elevación de cámara,
  colisiones suaves. Terreno plano, movimiento hacia adelante, paredes lejanas, ascensores
  suaves; teleport nodes en pendientes y escaleras.
- **Las preferencias de confort son POR APP**: no existe preferencia de sistema que viaje
  entre aplicaciones. Menú accesible en juego, cambio en tiempo real sin reiniciar,
  persistencia entre sesiones.

## 5. VR Template de Unreal: qué trae y cómo funciona [DOC]
- Usa **OpenXR** (estándar multi-empresa): la misma lógica corre en varias plataformas sin
  código específico. Dispositivos: Oculus Mobile (Quest 1/2), Oculus PC (Rift S, Quest Link),
  SteamVR (Valve Index, HTC Vive), Android XR, Samsung Galaxy XR.
- **VRPawn** (Content>VRTemplate>Blueprints): la representación física del usuario; contiene
  la lógica de locomoción. **VRGameMode**: define qué Pawn usar (se fija en Project Settings →
  Maps & Modes). **Player Start**: define dónde spawnea el Pawn; **en VR su origen es el
  tracking origin del mundo virtual** (consecuencia directa del bug MEDIDO en s14: PlayerStart
  mal colocado = spawn en el vacío).
- **Teleport**: thumbstick/trackpad derecho → aparece el visualizador → soltar para teleportar.
- **Snap Turn**: thumbstick/trackpad izquierdo → gira sin mover la cabeza.
- **Áreas permitidas**: se marcan con **Navigation Mesh**; el asset `NavModifier_NoTeleport`
  (NavModifierVolume con Area Class `NavArea_Null`) hace que el visualizador de teleport
  desaparezca ahí. Tecla **P** togglea la visualización de áreas navegables.
- **Grab**: mantener Grip → Sphere Trace alrededor del GripLocation del controller; si hay un
  Actor con **GrabComponent** en la esfera, se attacha a la mano. GrabType (enum GrabType):
  **Free** (posición relativa al agarre, p.ej. cubos), **Snap** (posición/orientación fija,
  p.ej. pistolas), **Custom** (lógica propia vía OnGrabbed/OnDropped + bIsHeld).
  Haptics: `OnGrabHaptic Effect`. Todo abstracto tras el Blueprint Interface `VRInteraction BPI`.
- **Menu**: botón menu del controller → UMG (`WidgetMenu` en Content>VRTemplate>Blueprints).
- **VR Spectator**: otros ven la experiencia mientras alguien usa el HMD. Tab para togglear,
  o `VRSpectator bSpectatorEnabled=true`. **NO compatible con Mobile VR (Quest)**.

## 6. World Scale en VR [DOC + MEDIDO]
- **[DOC]** 1 cm = 1 Unreal Unit; 1 m = 100 UU; 1 km = 100,000 UU. Variable
  **World to Meters** en World Settings ajusta cómo de grande/pequeño se siente el usuario.
- **[MEDIDO]** El proyecto ya cumple esta escala: bounds de 58/58 meshes verificados 1:1 en cm
  (ver scale-and-realism.md). Altura de ojo usada en capturas = 170 cm.
- **[DOC]** La escala de objetos debe imitar la realidad lo más posible: objetos más
  grandes/chicos que su contraparte real causan confusión o sickness.
- **[DOC]** NO quitar caras de polígonos "invisibles" como en no-VR: en VR el usuario mira
  alrededor y las caras faltantes se notan.

## 7. Rendimiento en VR [DOC]
- **Iluminación**: Static Lights + Lightmaps (la opción más barata). Si hace falta dinámica,
  limitar al mínimo y que nunca parpadeen ni cambien abruptamente.
- **Fakear todo lo posible**: sombras dinámicas caras → trucos (en el demo Showdown de Epic,
  los personajes proyectando sombras dinámicas era demasiado caro y se fakeó).
- **VFX**: SubUV textures (fuego/humo 2D) no aguantan bien en VR; usar **static meshes** en
  vez de partículas 2D para explosiones/estelas. Cuidado con efectos near-field.
- **Reducir actor count**: ver world-partition.md §3 (Packed Level Actors, Merge, PCG).

## PlayerStart: causa raíz MEDIDA de la caída libre — mecanismo REAL leído de la fuente (27-nov-2026)
Síntoma: el exe arranca, carga el nivel correcto (`LoadMap` OK en ~0.3 s, cero crash dumps) y el
jugador cae al vacío indefinidamente. **No es el cook, ni el GameMode, ni el GameDefaultMap.**

### Mecanismo (leído de la fuente del motor, NO inferido)
`Engine/Source/Runtime/Engine/Private/GameModeBase.cpp`:
- `ChoosePlayerStart_Implementation` (línea 1093) recorre los `APlayerStart` y para cada uno llama
  `World->EncroachingBlockingGeometry(PawnToFit, ActorLocation, ActorRotation)`, donde `PawnToFit`
  es el **CDO del pawn del GameMode**. Si NO encroaching → `UnOccupiedStartPoints`; si encroaching
  pero `FindTeleportSpot` encuentra sitio → `OccupiedStartPoints`; **si encroaching y no hay teleport
  spot → el PlayerStart se DESCARTA por completo**.
- Si ambas listas quedan vacías ⇒ devuelve `nullptr` ⇒ `FindPlayerStart_Implementation` (línea 1184)
  loguea **`FindPlayerStart: PATHS NOT DEFINED or NO PLAYERSTART with positive rating`** y hace
  `BestStart = World->GetWorldSettings()` ⇒ **spawnea en el ORIGEN (0,0,0)**, que en modelos
  importados es una esquina fuera de la losa ⇒ caída libre.
- **NO existe ningún "rating negativo"** (`RatePlayerStart` no participa en esta ruta en 5.8): el
  único criterio es *encroaching / teleport spot*. Corregido aquí el 27-nov-2026 contra la fuente;
  la explicación anterior ("rating negativo por muro") era una inferencia FALSA.
- `PlayerStart.cpp`: la cápsula del actor PlayerStart es `InitCapsuleSize(40.0f, 92.0f)` (radio 40,
  media altura 92) — **pero la comprobación usa la cápsula del PAWN, no la del PlayerStart**.

### Diagnóstico del proyecto (MEDIDO 27-nov, editor vivo, MCP + trace_world)
- `trace_world` en (520,-380): hacia abajo desde z=90 → **90** (piso caminable en **z=0**); hacia
  arriba desde z=90 → 225 (techo en z≈298, coherente con techo 3.00 m); desde z=1000 → 702.
- Cápsula del pawn real `BP_FirstPersonCharacter`: `capsuleHalfHeight=96`, `capsuleRadius≈34`,
  `baseEyeHeight=64` (medido con `ObjectTools.get_properties` sobre el CDO `Default__...:CollisionCylinder`).
- PlayerStart de `Lvl_Casa_S10` antes del fix: **(520, -380, z=0)**, yaw 180 ⇒ su cápsula va de
  z=−96 a +96 ⇒ **la mitad inferior está enterrada en la losa** ⇒ `EncroachingBlockingGeometry` = true
  ⇒ `FindTeleportSpot` no lo salva ⇒ descartado ⇒ spawn en (0,0,0) ⇒ caída.
- **FIX APLICADO Y VERIFICADO (s15, 18:03-18:04):** `evidencia/s15/p9_fix_playerstart_z.py` lo movió a
  **z=100** (= 0 + 96 + 4 de holgura) y restauró el yaw 180 (ver trampa de `set_actor_transform` abajo).
  Trazos de confirmación: 0 impactos en ±Y, 80 cm hacia +X, 113 en diagonal, 209 hacia −Y+X; mínimo 80
  > radio 34 ⇒ libre. Guardado comprobado por el **mtime del external actor**
  `Content/__ExternalActors__/ProyectoUE_S10/Lvl_Casa_S10/9/E0/4ZN1E2KC9GD679UPD98SYM.uasset`
  (18:04:27), mientras el `.umap` quedó intacto en 26-nov — exactamente como predice World Partition.
- **TRAMPA de `set_actor_transform` [MEDIDA s15]:** pasar solo `location` en `xform` **resetea la
  rotación a 0** (el yaw 180 se perdió y hubo que restaurarlo). No confiar en "campos no-set = no
  cambiar": mandar SIEMPRE `xform` completo (location + rotation + scale) y **re-leer el transform
  después** para verificar.
- Trazos horizontales a z=90 desde ese punto: 80 cm hacia +X (muro), 113 en diagonal, libre hacia −X/±Y.
  Radio de cápsula 34 < 80 ⇒ **en XY el punto SÍ está libre**. El defecto es solo la **Z**.
- **El fix de s14 (`p8_fix_playerstart_v2.py`) movió X de 600→520 pero dejó z=0** ⇒ por eso el exe
  cocinado a las 10:43 y probado a las 10:54 SIGUE con `PATHS NOT DEFINED` (verificado en
  `p7_exe_s14.log` línea 921, y el PlayerStart SÍ se cocinó: aparece en
  `Saved/Logs/WorldPartition/StreamingGeneration-Cook_Lvl_Casa_S10-...10.42.31Z.log` con
  `SpatiallyLoaded:false`). El cook no era el problema.

### Regla de colocación [MEDIDO]
**Z del PlayerStart = Z del piso caminable + `capsuleHalfHeight` del pawn** (aquí 0 + 96 = **96**;
usar ~100 para no quedar en contacto exacto). El origen del actor ES el centro de su cápsula, no su base.
Checklist antes de cocinar:
1. `trace_world` hacia abajo desde z alta en el punto → da la Z real del piso (no asumir 0 ni el
   origen del modelo, que suele ser una esquina).
2. `get_properties` del CDO del pawn → `capsuleHalfHeight`.
3. `set_actor_transform` con `z = piso + halfHeight` (+ ~4 cm de holgura).
4. `trace_world` horizontales a `z = piso + halfHeight` en 8 direcciones: todas deben dar `None` o
   distancia > `capsuleRadius`.
5. `save_assets([])` y **verificar el mtime de `Content/__ExternalActors__/`** (nivel World Partition),
   luego RE-COCINAR.

### Trampas de medición pagadas
- Una sonda casera (`probe_playerstart.json`) reportó `n_actores=1` y midió MAL el nivel. Usar
  `SceneTools.find_actors(name="", tag="", collision_channels=[])` (los tres params son required).
- `trace_world` devuelve **distancia desde `start`**, no coordenada: si devuelve exactamente la Z de
  partida puede significar "impacto inmediato" (piso justo debajo). Probar con DOS `start` distintos
  antes de interpretar; fuera del footprint devuelve `None`.
- **`AssetTools.find_assets` exige `folder_path`** además de `name` (pagado 27-nov).
