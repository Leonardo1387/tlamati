---
name: unreal-engine-playbook
description: "Unreal Engine 5.8 as a TOOL (not just the planos->recorrido pipeline): lighting/exposure (Lumen, sky capture, eye adaptation), cameras & cinematics (Sequencer, Movie Render Queue), post-process, VR/XR comfort, gameplay framework (PlayerStart, GameMode, Pawn), World Partition, Mesh Terrain + PCG forest + procedural vegetation, and photorealistic archviz (detail/variation/imperfection, HDRI dome, decals, weather). Each topic = curriculum links + a reference distilled ONLY from work measured in this environment (MCP calls, viewport captures, logs) or from full courses in the on-disk corpus. Load when touching Unreal visuals, exposure, cameras, Sequencer, terrain, PCG/vegetation, archviz realism, VR, spawn/PlayerStart, or World Partition — and before distilling a new topic."
---

# Unreal Engine Playbook (proyecto-archviz y futuros: juegos, cinemáticas, VR)

Propósito: ser experto en la HERRAMIENTA (Unreal 5.8.4 + Blender de apoyo) para producir
recorridos VR, animaciones 3D y videojuegos — empezando por el proyecto actual
(plano 2D → primera persona navegable).
**Criterio del fundador (27-nov-2026): la documentación oficial SÍ se lee completa.** Es
gasto único y amortizable; la meta es destilarla a skills permanentes. Lo que NO se hace
es re-bajarla cada vez: ya está en disco. Cada reference combina teoría destilada **[DOC]**
con hechos verificados aquí **[MEDIDO]**, y cuando el proyecto toca el tema se promueve
[DOC]→[MEDIDO] con evidencia (MCP, capturas, logs).

## Reglas de uso
- Antes de tocar iluminación/cámaras/post-proceso/VR/escala: leer la reference del tema.
- Si la reference no existe y el trabajo la necesita: destilarla EN ESA SESIÓN desde el
  corpus en disco (`grep` sobre `raw/`) y marcarla con fecha.
- Al medir algo en el editor, actualizar la reference en el MISMO turno y marcar [MEDIDO].
- Trampas del arnés WSL/Windows y del MCP de Unreal: viven en
  la skill hermana creative-apps-mcp-bridges (examples/skills/creative-apps-mcp-bridges/SKILL.md) (no duplicarlas aquí).

## Corpus destilable (YA EN DISCO, actualizado 28-nov-2026)
**No hace falta web_fetch.** El corpus completo ya está como texto limpio en:
`<proyecto>/curriculum/raw/*.txt` (corpus local del proyecto archviz)
(**37 archivos, 718 KB, ~185K tokens**). Índice y cómo re-traerlo: `curriculum/LEEME.md`.
Para destilar: `grep`/`read_file` sobre `raw/`, NUNCA re-bajar la página (el HTML crudo
cuesta 12× más; medido 111 KB → 9.0 KB).
Cuatro fuentes las pasó el fundador como texto plano (su sitio no dejaba extraerlas):
- `raw/meta_vr_locomotion_fundador.txt` (15.5 KB) — los 2 links de Meta que daban 400.
- `raw/unreal_world_building_guide.txt` (110 KB) — la página JS-rendered NO_DISPONIBLE por extractor
  (Jean-Sebastien Guay, Epic, UE 5.0-5.6; limpiado: 2350 líneas crudas → 110 KB de artículo).
- `raw/curso_bosque_58_limpio.txt` (177 KB, ~3h15m, 9 caps) — curso completo UE 5.8 patrocinado
  por Epic: escena de bosque animada. UI/navegación, mesh terrain, materiales de terreno, booleanos,
  water river, PVE (árboles procedurales), PCG forest completo, Sequencer + Movie Render Queue.
  Limpieza validada: reloj [M:SS]↔deletreo "N seconds" = 0 discrepancias en 1477 líneas.
- `raw/curso_realismo_arquitectonico_limpio.txt` (24 KB, ~26 min, 12 caps) — arquviz fotorrealista:
  casa 3ds Max → Datasmith → UE5. Los 3 principios (detalle/variación/imperfección), HDRI dome,
  volumetric fog, Easy Rain, gente con plugin de Chaos. **El más relevante para M3.**
  (Regla del fundador 28-nov-2026: destilar el curso ENTERO como skill de futuro, NO filtrar por
  "lo que sirve al flujo actual" — filtrar desperdicia el curso.)
Único faltante: el PDF `lighting-for-educators` (19.4 MB, existe; el extractor es HTML-only).

## Mapa de temas
| Tema | Reference | Corpus en `raw/` (KB) | Estado |
|---|---|---|---|
| Escala y medidas realistas | references/scale-and-realism.md | designer_01_blockout 41.4, hdri_backdrop 12.0 | **DESTILADA** (4 MEDIDO, 13 DOC) |
| Iluminación/exposición/sombras | references/lighting-exposure.md | virtual_shadow_maps 43.5, shadowing 14.4, hdri_backdrop 12.0, designing_visuals 8.1, post_process 17.7, bloom, color_grading | **DESTILADA** (6 MEDIDO, 8 DOC) — incluye recetas MCP para cvars |
| Post-proceso (tonemapper, bloom, volúmenes) | references/post-process.md | post_process_effects 24.7, add_post_process_volumes 17.7, color_grading 16.1, bloom 8.8 | PENDIENTE (parcial en lighting-exposure §3-4) |
| Texturas y materiales PBR | references/textures-materials.md | léxico del proyecto (16 términos), physically_based_materials 8.5, strayspark_import_pbr 7.1, strayspark_master_materials 13.8 | **DESTILADA** (10 secciones, 19 MEDIDO / 6 DOC) — valores PBR reales de Epic, arquitectura master/instance, censo de las 48 texturas y 20 materiales. ✅ `nor_gl` está BIEN (`bFlipGreenChannel=true` + `TC_Normalmap`, medido). ⚠️ 2 defectos reales abiertos: 6 texturas con `TC_EditorIcon` (causa: dims no múltiplo de 4) y `metal_plate_02` nunca importado (no existe `M_acero_negro_mate`) |
| Cámaras y cinemáticas | references/cameras-cinematics.md | curso_bosque_58 cap 9 (Sequencer, Movie Render Queue), cinematic_cameras 16.0, cinematics 8.2, using_cameras 5.6, cinematic_viewport 5.6, cameras 5.5, camera_actors 2.3 | **PARCIAL** (destilado el flujo práctico del curso: Level Sequence, keyframes con S, interpolación Linear, Camera Cuts, Movie Render Queue). PENDIENTE fusionar el corpus oficial de cámaras |
| Mesh Terrain, MPD y PCG (UE 5.8) | references/mesh-terrain-pcg.md | curso_bosque_58 caps 3-8 (177 KB) | **DESTILADA [DOC]** (23 secciones: plugins, World Partition obligatorio, heightmap, MPD/Channel Texel Size, booleanos Union/Subtract, remesh, Nanite displacement, PVE árboles procedurales, PCG forest completo con bounds/splines/density, water river, LOD/billboard/Nanite enable) |
| Editor: UI, navegación, guardado, luz | references/editor-basics-navigation.md | curso_bosque_58 caps 1-2 | **DESTILADA [DOC]** (Ctrl+Shift+S, Content Drawer, atajos de viewport, Environment Light Mixer, Project Settings Maps & Modes) |
| Fotorrealismo arkviz (M3) | references/photorealism-archviz.md | curso_realismo_arquitectonico (24 KB) | **DESTILADA [DOC]** (12 caps: 3 pilares, detalle/variación/imperfección, HDRI dome, fog volumétrico + directional alineado, ajustes de cámara, Easy Rain y su trampa viewport-vs-render, checklist de 10 pasos) |
| World Partition, OFPA y blockout | references/world-partition.md | unreal_world_building_guide 110, designer_01_blockout 41.4, world_partition 18.6 | **DESTILADA** (5 MEDIDO, 3 DOC) — incluye el pitfall MEDIDO de duplicar nivel WP (0 actores) |
| VR / XR confort y locomoción | references/vr-xr.md | xr_best_practices 12.8, vr_template 8.1, meta_vr_locomotion 15.5 | **DESTILADA** (3 MEDIDO, 11 DOC) — ver §0 CONTRADICCIONES con el proyecto actual |
| PlayerStart: Z, spawn y caída libre | references/vr-xr.md §"PlayerStart: causa raíz MEDIDA" | gameplay_framework 9.3, GameModeBase.cpp del motor | **DESTILADA Y CORREGIDA 27-nov**: mecanismo leído de `GameModeBase.cpp` (`EncroachingBlockingGeometry` sobre la cápsula del PAWN; en 5.8 NO existe "rating negativo"). Diagnóstico MEDIDO del proyecto: PlayerStart en z=0 con `capsuleHalfHeight=96` ⇒ mitad enterrada ⇒ spawn en el origen. Regla: `Z = piso + capsuleHalfHeight` |
| Gameplay framework (spawn, GameMode, Pawn) | references/gameplay-framework.md | gameplay_framework 9.3, get_started 5.3, game_objects 4.9, quick_reference 4.2, GAS 2.9 | PARCIAL — el mecanismo de spawn/caída libre YA está destilado y MEDIDO en vr-xr.md §"PlayerStart: causa raíz MEDIDA" (leer ahí, no aquí) |

## Convención de destilación (no negociable)
Cada afirmación de una reference lleva marca de origen:
- **[MEDIDO]** = verificado en ESTE entorno (MCP, captura de viewport, log, asset en disco).
- **[DOC]** = destilado de la documentación, aún sin comprobar en el editor.
Nunca se presenta teoría como hecho medido.

## Hallazgos MEDIDOS del editor (27-nov-2026, ahorran re-sondear)
- `EditorToolset.EditorAppToolset.SearchCVars(name="substring")` LEE cvars (help+valor);
  returnValue es string con JSON dentro (json.loads ×2). NO escribe. Ver lighting-exposure §1.
- `ConfigSettingsToolset` fija cvars PERSISTENTES vía sección `DataDrivenConsoleVariableSettings`
  (container Project / category Engine) con SetSectionProperties+SaveSection. Schema en lighting-exposure §1.
- `editor_toolset.toolsets.programmatic.ProgrammaticToolset.execute_tool_script(script=...)`
  batchea llamadas MCP en un round-trip: definir `run()`→dict, usar `execute_tool("Toolset.Tool", json)`.
  Módulos permitidos: json, datetime, time, copy, math, re. Leer `get_execution_environment()` primero.
- La cvar del warning del exterior quemado, `r.EyeAdaptation.CachedLightingPreExposure`, está en default **4**;
  su help oficial sugiere **8** para cubrir todo el rango físico. Candidato de M3-B.

## Hechos ya verificados del pipeline/viewport (no re-sondear)
- Editor warning medido en capturas s14: "Cached lighting in Lumen and real-time sky capture
  lighting is going to be clipped. Adjust r.EyeAdaptation.CachedLightingPreExposure" → el
  blown-out exterior de las capturas M3-A es **exposición, no geometría**.
- CaptureViewport: `annotations={}` obligatorio; `gridSpacing=0` Y `maxLabelDistance=0` para
  capturas limpias (gridSpacing=100 ACTIVA la rejilla, no la quita). z=170 cm = altura de ojo.
- StartPIE exige params no vacíos (schema PIESessionOptions); llamarlo sin options da
  error de schema, no de sesión.
- Bounds locales de los meshes importados YA traen las coordenadas de mundo (eje Y negado);
  colocar actores con xform IDENTIDAD, nunca recalcular desde posicion_m del modelo.
