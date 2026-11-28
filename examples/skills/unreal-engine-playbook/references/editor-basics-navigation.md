# Editor: UI, navegación, guardado y setup de luz — [DOC curso-bosque]

Fuente: `curriculum/raw/curso_bosque_58_limpio.txt` caps 1-2 (curso completo UE 5.8, Epic).
Citas `[MM:SS]`/`[H:MM:SS]` = timestamp del transcript. No medido aún en nuestro entorno.

## 1. Crear proyecto
- [2:40] Epic Launcher > Library > **+** para instalar la última versión del motor (el curso usa
  5.8.x) > Launch.
- New Project > template **Games** > Blank, **Blueprint** (no C++), **Target Platform: Desktop**,
  elegir carpeta y nombre [2:48]-[2:57].
- Al abrir: splash + compilación de shaders (hay que esperar) [3:13].
- La escena por defecto es `Untitled`, NO guardada; se abre cada vez hasta que especifiques otra
  [3:22]-[3:30].

## 2. Layout y UI
- [3:37] **Window > Load Layout > Default Editor Layout** — para que todos vean lo mismo.
- [6:52] **Content Drawer** = lo más importante: todo el contenido del proyecto. Se expande/cierra
  con **Ctrl+Space** [7:08]. Se puede **dockear** al layout para no perder espacio [7:19].
- Paneles [5:29]: barra de modos (Selection, Landscape, Foliage, Modeling...), herramientas de
  transform (select/move/rotate/scale), coordenadas, snapping, viewport controls y filtros de vista.
- [5:37] A la derecha: **Outliner** (objetos de la escena) y **Details** (propiedades del
  seleccionado).
- [10:18] Settings (engrane del Content Browser) > activar **Engine Content** y **Plugin Content**:
  hace visible `/Engine`, que se puede explorar Y **duplicar para usar en tu proyecto** [10:33].
- [21:07] **Add > Feature or Content Pack**: quick-start scenes (first person, third person, top
  down, VR, vehicle) para prototipar y aprender de blueprints hechos.
- [22:16] Window > **World Settings** > sección **Game Mode** = dónde se fija el GameMode del nivel
  (p.ej. `BP_ThirdPersonGameMode` del feature pack). Play [22:25], Escape sale [22:43].

## 3. Guardado (error de principiante que el curso remarca 5+ veces)
- [11:33] `Ctrl+S` guarda SOLO el nivel/asset activo. **`Ctrl+Shift+S` = Save All** y es lo que el
  autor usa SIEMPRE [11:40].
- [23:22] Los assets recién importados muestran **asterisco** = sin guardar; `Ctrl+S` NO los guarda,
  hace falta `Ctrl+Shift+S` [23:28].
- [31:26] Regla general: el contenido de `/Engine` es compartido → **copiar al proyecto y editar la
  copia**, nunca el original.

## 4. Navegación del viewport
- [4:01] RMB + WASD = volar. Q/E = subir/bajar [4:56]. A/D = izquierda/derecha.
- [4:19] RMB + **rueda del ratón** = velocidad de cámara. Subirla para mundos grandes; bajarla cerca
  de objetos [4:40].
- [5:05] Seleccionar objeto + **F** = enfocar. Luego **Alt + LMB** = orbitar, **Alt + rueda** = zoom
  (estilo Blender) [5:12].
- [25:13] **W/E/R** = mover/rotar/escalar el gizmo.
- [12:10] **Snapping on surface** = los objetos caen sobre el terreno al arrastrar.
- [27:46] Cambiar a **top view** para posicionar brushes/splines desde arriba; [29:41] **Alt+2** =
  wireframe del área, **Alt+4** = volver a lit.
- [49:02] **Ctrl+1 / Ctrl+2** = guardar bookmarks de cámara; **1 / 2** = restaurarlos.
- [24:23] **Ctrl+L + mover mouse** = rotar el sol en tiempo real.
- [2:13:55] **E sobre un nodo PCG** = activar/desactivar el nodo.
- [2:01:08] **A** = mostrar atributos PCG (punto amarillo); **D** = debug node (azul).
- [1:29:41] Snapping de rotación: activarlo para giros exactos de 90° [1:38:04]; desactivarlo para
  libertad [1:45:45].
- [1:12:10] Desactivar grid snapping para mover objetos libremente [38:50].

## 5. Setup de cielo y luz en segundos: Environment Light Mixer
- [12:13] **Window > Environment Light Mixer**. Muestra qué le falta a la escena y crea cada actor
  con un clic: **Skylight, Directional Light, Sky Atmosphere, Volumetric Cloud, Exponential Height
  Fog** [12:32]. "Y básicamente eso es todo" — setup de cielo completo en segundos [12:42].
- El mixer queda abierto para **modificar todo en un solo lugar** [12:50].
- Roles [12:59]:
  - **Directional Light** = la fuente; controla dirección e intensidad de la luz del mundo [13:12].
  - **Skylight** = captura lo que pasa alrededor y lo proyecta, "algo así como un HDRI" [13:06].
    Captura sky atmosphere, fog y nubes volumétricas [13:12].
- [13:41] Project Settings: **Lumen viene activo por defecto** (GI y reflection method = Lumen)
  [13:50]. **Nanite también activo por defecto** [14:09]. Nanite Foliage NO (experimental) [14:16].
- [14:24] Proceso eficiente: activar TODOS los plugins/ajustes que piden reinicio antes de reiniciar
  UNA sola vez.
- [17:09] Project Settings > **Maps & Modes** > Startup Map y Default Map: fijarlos a tu nivel para
  que el proyecto abra directo ahí (igual que el `GameDefaultMap` de `DefaultEngine.ini` que usa
  nuestro packaging).

## 6. Niveles y World Partition
- [10:56] Organizar: crear carpeta `Levels` en Content y crear el nivel dentro (right click >
  New Level) [11:09].
- [7:52] El nivel por defecto usa **streaming + partitioning**: solo puedes seleccionar los
  cuadrados cercanos. Pensado para mundos grandes — streamea contenido según dónde está el jugador
  y libera memoria del resto [8:08]. "Funciona out of the box, no necesitas meterte en la técnica"
  [8:25]. (En nuestro proyecto SÍ nos metemos: ver `world-partition.md`.)
- [18:22] Convertir un nivel a World Partition: si está ABIERTO, Tools > Convert Level > Open and
  convert in place; si está CERRADO, right click > Add Partition Streaming Support (**más rápido**).
- [25:28] Crear contenido de referencia de escala: Characters > Mannequins > Mesh > `Man_Simple`,
  en 0,0, subido en Z hasta que emerja del suelo.
