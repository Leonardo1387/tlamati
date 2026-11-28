# World Partition, OFPA y blockout (Unreal 5.8.4)

Destilado 27-nov-2026 de `raw/unreal_world_building_guide.txt` (110 KB, Jean-Sebastien Guay,
Epic, actualizado a UE 5.5/5.6) + `raw/designer_01_project_setup_and_level_blockout` +
`raw/world_partition_in_unreal_engine`. **[MEDIDO]** = verificado en este proyecto.

## 0. Por qué esto importa aquí
- **[MEDIDO]** `Lvl_Casa_S10` ES un nivel World Partition: el log dice
  `IsMainWorldPartition=1` y las WorldSettings son `WorldSettings_1.WorldPartition_0`.
- **[MEDIDO]** Los actores viven en `Content/__ExternalActors__/` como `.uasset`
  individuales (67 en S10). El `.umap` pesa solo 14,772 b y **casi no cambia por diseño**.
- **[MEDIDO]** Regla de verificación: para saber si un nivel WP se guardó, mirar el mtime de
  `__ExternalActors__` o usar `AssetTools.is_dirty(path)` — **NUNCA el mtime del `.umap`**.
  (Hipótesis falsa que se pagó en s13: "save_assets([]) excluye mapas". La firma real es
  `save_dirty_packages(save_map_packages, save_content_packages)`; el primer `True` ya pide mapas.)

## 1. PITFALL CRÍTICO: duplicar un nivel WP no copia sus actores
- **[MEDIDO s12]** `AssetTools.duplicate` de `Lvl_Casa` → `Lvl_Casa_S10_v2` produjo un nivel
  con **0 external actors** (vacío). Tuvo que borrarse.
- **[DOC — explica la causa]** OFPA guarda cada actor como archivo externo nombrado por GUID
  en su propia estructura de carpetas, FUERA del `.umap`. Duplicar el `.umap` no duplica esos
  archivos. El guide además desaconseja copiar mundos WP: *"Copying world partition/OFPA
  enabled dense and large worlds... will lead to further more files added to source control,
  always evaluate the needs before doing so"* y propone en su lugar **Level Instances**
  (reutilizables en varios niveles) o **Data Layers** (datos de prueba dentro del mundo principal).
- Consecuencia práctica: **NO existir tool MCP para crear un nivel nuevo** (solo
  `load_level`/`get_current_level`; `create_level_instance` es otra cosa) se compensa
  trabajando sobre el nivel existente, no duplicándolo.

## 2. Conceptos (definiciones del guide)
| Feature | Qué hace |
|---|---|
| World Partition | Data management automático + streaming por distancia. Elimina la necesidad de dividir niveles grandes en sublevels. |
| OFPA (One File Per Actor) | Guarda cada actor como archivo externo → quita el "file contention" entre usuarios y evita guardar el nivel entero por cada cambio. |
| Level Instances | Workflow no-destructivo: instanciar contenido y editarlo **en contexto**; anidables en jerarquía. Con OFPA + Level Behavior=Embedded (5.4) se **descomponen** en actores del persistent world. |
| Packed Level Actors (PLA) | Empaqueta contenido solo-visual en UN actor → baja el actor count en runtime y editor y da vía más rápida a la GPU. Sus **bounds** deciden en qué celda streamea. |
| Data Layers | Filtro condicional de carga (runtime y edición) sobre la lógica de streaming de los actores. |
| HLOD | Representación visual de un grupo de actores que los reemplaza a distancia; se genera automáticamente. |
| Streaming fuera de WP | Nanite, Texturas y Audio streamean por su cuenta, independiente de WP. |

## 3. Buenas prácticas [DOC]
- **Empezar con UN solo grid**: *"the less amount of grid in the end the better"*.
- Grid Size y Loading Range se basan en gameplay/física/conteo de actores y se **re-evalúan
  con profiling constante** conforme crece el contenido.
- Activar el plugin **Fast Geometry Streaming** si el mundo es geometría estática densa e
  inmutable (mundos abiertos grandes).
- **Streaming sources**: por defecto el PlayerController es streaming source, pero se pueden
  añadir componentes a cualquier actor (p.ej. la cámara de una cinemática) para cargar
  contenido en otro sitio o precargar una cinemática sin cortes. Forma, prioridad, grids
  objetivo y estado se ajustan por componente.
- **Spacing**: en pre-producción, tematizar y distribuir el contenido pesado/único según el
  loading range objetivo. Usar **Show Grid Preview** como ayuda visual del grid y su rango
  aproximado (no sustituye debugging real en juego).
- **Disable Streaming**: el streaming puede desactivarse por completo en un nivel WP y aun
  así conservar los beneficios de OFPA, Level Instances y sobre todo Data Layers.
- **Block On Slow Streaming + Grid priority**: juntos sirven para localizar problemas de
  streaming; el ratio se controla con `wp.Runtime.BlockOnSlowStreamingRatio`.
- **Reducir actor count** (Strategies): Packed Level Actors, Merge Actors (batch mode →
  Instanced Static Mesh components) y PCG (favorece instancing; desde 5.6 puede spawear
  Instanced Actors con hidratación/deshidratación).
- **Production workflow**: "Check Map for Errors" para encontrar errores de contenido que
  rompan cook/gameplay; Submit Validation en source control; version estable QA-testeada
  diaria en producciones grandes; presupuestar memoria/rendimiento/disco en cada etapa.

## 4. Pitfalls [DOC]
- **Multiplicación de niveles por grids apilados**: cada celda de cada grid con ≥1 actor
  produce un streaming level, y además uno por cada combinación única de runtime data layers
  en esa celda. El número total impacta rendimiento → validar y profilear antes de apilar grids.
- **Bounds de actores**: bounds grandes promueven contenido a "persistent", lo que anula el
  streaming automático (p.ej. un actor con spline mesh component). Monitorear con validación.
- **Hard references entre actores** (attached/parented) se consideran como un todo para
  streaming → afectan los bounds. Limitarlas a actores cercanos/solapados/dentro del rango
  de celda; preferir **soft references**.
- **No micro-gestionar la promoción de grid**: la reacción típica es intentar controlarla
  moviendo placement/bounds/tamaños. *"Don't micromanage but do monitoring"*. (Además su
  impacto bajó mucho con Runtime Hash + Loose Hierarchical Grid, de celda variable.)
- **No hay carga automática por cámara en el editor**: el contenido se carga con el World
  Partition Editor, Location Volumes o HLODs.
- **Limitaciones con actores particionados** (Landscape, Foliage): se rebanan según el grid
  size configurado y **NO se actualizan al reconfigurar el grid**; no hay World Partition
  Landscape Builder aún; cambiar sus data layers solo es posible en Foliage (herramienta Move).
- **OFPA + P4V**: usar P4V para commitear debe evitarse/desaconsejarse/prohibirse — los
  archivos externos están nombrados por GUID y son imposibles de identificar fuera de Unreal.
  Usar la integración de source control de Unreal (View Changelist muestra display name,
  tipo, validación al submit) y **Uncontrolled CL** (trabajo local, archivos fantasma,
  mover edits cuando el SC está caído). Los programadores deberían usar siempre Uncontrolled CL.
- **Acceder a actores no cargados**: las utilities necesitan `ActorDescs` para obtener GUIDs
  y cargar antes de interactuar; no se puede acceder a actores sin el mundo cargado en el editor.
- **No hay sistema de bloqueo de actores** (falta frecuente): nada impide que dos usuarios
  editen el mismo external actor.

## 5. Blockout (flujo del tutorial oficial) [DOC]
- Empezar con **Landscape** (LandMass plugin para formas específicas) + **BSP Brushes**
  (modo Place) o **Static Meshes** para el layout; Model mode para formas simples.
- Usar **snap-to-grid** para mantener consistencia: Select > Snap/Grid Settings > Grid Snap
  = 10 (uu, o sea 10 cm).
- Bloquear a **escala humana**: cubo 1×1×1 m; puertas 1–1.5 × 2 m; personaje 1.8 m alto y
  salta 0.5 m; pasillos 2–3 × 3–4 m; paredes ~4 m; **tercera persona = ×1.5**.
- Poner un **maniquí** de referencia (SKM_Manny_Simple) en cada espacio mientras se bloquea.
- La escala debe ser **predecible** y las medidas **consistentes**; realismo total no siempre
  juega bien (una puerta de 0.8 m aprieta y la cámara puede clipar).
- Ver detalles y medidas en `references/scale-and-realism.md`.
