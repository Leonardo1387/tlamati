# Mesh Terrain (UE 5.8) + PCG + Vegetation Editor — [DOC curso-bosque]

Fuente: `curriculum/raw/curso_bosque_58_limpio.txt` (curso completo UE 5.8, escena de bosque
animada, patrocinado por Epic). Citas `[HH:MM]` = timestamp del transcript.
Nada de esto está [MEDIDO] en nuestro entorno todavía: el proyecto proyecto-archviz
usa niveles World Partition SIN mesh terrain. Cuando se toque el tema, promover a [MEDIDO].

## 1. Qué es y por qué importa
- [07:54] Mesh Terrain es un **modelo 3D real**, no un heightfield como el Landscape clásico:
  permite overhangs, islas flotantes, cuevas y túneles. Modificadores **no destructivos**:
  mueves un rasgo y el terreno se regenera.
- [09:43] Es feature **experimental** en 5.8.
- Limitación del Landscape viejo que esto resuelve [09:11]: solo esculpías altura (arriba/abajo,
  shift = abajo); no podías "cavar de lado". Antes una cueva se falseaba perforando y tapando
  con assets solapados [09:18].

## 2. Activación (orden que ahorra reinicios)
Plugins necesarios [15:05]-[16:45], en Edit > Plugins:
| Plugin | Nota del curso |
|---|---|
| **Mesh Partition** | OJO: el feature se llama "mesh terrain" pero el PLUGIN es `Mesh Partition` [15:23] |
| **Mesh Terrain Mode** | el modo del editor |
| **Mesh Partition Water** | interoperar con el plugin Water |
| **PCG Mesh Partition interop** | para que PCG coopere con mesh terrain |
| **Water** + **PCG Water interop** | Water se activa solo como dependencia [16:27] |
| **Procedural Vegetation Editor** | [16:36] |
- PCG **ya no es experimental** en 5.8, viene activo por defecto [16:02].
- Lumen y Nanite vienen activos por defecto; **Nanite Foliage NO** (experimental) — hay que
  activarlo a mano [14:09].
- Truco de proceso [14:24]: activar TODOS los plugins y ajustes que piden reinicio ANTES de
  reiniciar una sola vez, en vez de reiniciar por cada uno.
- Nanite foliage activado exige restart del proyecto [14:16].

## 3. Requisito duro: World Partition
- [18:14] "Create rectangle" de mesh terrain **falla** si el nivel no tiene World Partition.
- Dos vías para convertir un nivel a WP [18:22]-[18:59]:
  1. Nivel YA ABIERTO: no se puede desde right-click ("cannot convert something that's loaded");
     ir a **Tools > Convert Level > Open and convert in place**.
  2. Nivel CERRADO: right-click en el Content Browser > add partition streaming support —
     **es mucho más rápido** [18:59].
- Señales de que la conversión funcionó [19:07]-[19:22]: mensaje "no loaded regions", y en el
  Outliner aparecen **World Data Layers** y **World Partition Minimap**. Se generan archivos extra.
- (Cruce con lo MEDIDO en nuestro proyecto: el nivel es WP y los actores viven en
  `Content/__ExternalActors__/`; ver `world-partition.md`.)

## 4. Creación y escala
- [19:38] Mesh Terrain mode > Create rectangle. Tamaño por defecto **100,000 cm = 1 km × 1 km**
  (Unreal trabaja en centímetros por defecto) [19:46].
- [23:49] El menú de mesh terrain permite **Expand**: seleccionas un lado y añade otro cuadrado —
  crecer el terreno es trivial [24:05].
- [20:12] Al crearlo, la cámara suele quedar intersectando: alejarse con RMB + WASD.

## 5. Modificadores: heightmap (el corazón del flujo)
- [24:17] Modifiers es "la feature más poderosa de todo esto". Hay mesh modifiers y texture
  modifiers. Análogos a modificadores de Blender: no destructivos [24:33].
- Flujo con heightmap [24:41]-[27:36]:
  1. Arrastrar **Texture modifier** a la escena; tiene bounds propios.
  2. En Details, primero fijar **Extend** (cobertura por defecto, p.ej. 100k para cubrir todo el
     terreno) y SOLO DESPUÉS tocar Scale [25:28]. Orden importante: Extend = cobertura base,
     Scale multiplica. No hay extent en Z, ahí sí se usa Scale [26:02].
  3. Scale Z ≈ 3 para tener rango de operación mayor [26:10].
  4. **Height displacement** = amplitud. Con valores bajos solo salen bumps; el curso usa **25K** [26:40].
  5. Arrastrar el heightmap al slot **Texture asset** [26:19].
  6. **Zero value = 0** para que desplace desde cero hacia arriba; si no, el terreno queda
     enterrado en el exponential height fog [26:49]-[27:06].
- [27:13] Lo potente: con W **mueves el modificador y el desplazamiento se mueve** sobre el
  terreno. Puedes apilar varios y mezclarlos [27:21]. No te casas con el heightmap como en Landscape.
- Atajos [25:13]: W/R/E = move/rotate/scale (estándar de la industria).

## 6. MPD (Mesh Partition Definition) — la config del terreno
- [30:46] `Mesh Partition Definition` = archivo de configuración del mesh terrain. Por defecto
  `MPD_Default`, que vive en **contenido del motor**.
- Para verlo: Settings (engrane del Content Browser) > activar **Engine Content** y **Plugin
  Content** [10:18]. Eso hace visible la carpeta `/Engine`, cuyo contenido se puede **duplicar y
  usar en tu proyecto**, no solo explorar [10:33].
- Regla [31:26]: **NO editar el MPD del motor** (es compartido entre proyectos). Copiar
  (Ctrl+C sobre el asset) y pegar (Ctrl+V) en tu carpeta → renombrar `MPD_Terrain` → arrastrarlo
  al slot del mesh partition para **override** [32:02].
- [32:16] Dockear la pestaña del MPD al lado del nivel para alternar rápido.
- **Channel descriptions** del MPD [32:32] = el equivalente a los "blend layers" del Landscape
  viejo: canales que enmascaran texturas/capas del material [32:41].

## 7. Proyección de canales con un segundo texture modifier
- [54:11] Segundo Texture modifier (renombrarlo: `heightmap` y `slopes` con F2 [54:49]).
  Location 0,0,0; Extend 100k × 100k.
- [55:06] En este NO se usa Height displacement sino **Weight channels**: elegir a qué canal del
  MPD se proyecta (p.ej. `cliffs`) [55:33].
- Concepto [55:41]: un **pincel de textura espacial** que proyecta información a un canal definido
  en el MPD.
- ERROR QUE EL CURSO PAGA [56:58]: si solo cambias Extend (100k) pero **no el Scale**, la
  máscara sale mal recortada. Fix: Scale Z = 3 igual que el otro [57:06].
- OJO. Regla de los dos modificadores [57:36]: **misma location (0), mismo extent y mismo scale Z**,
  si no el heightmap queda offset y no coincide con la máscara de pendientes.

## 8. Muestreo del canal en el material
- [55:56] Nodos específicos (buscar "mesh partition" en el grafo):
  - **Mesh Partition Resource** = referencia al mesh terrain.
  - **Mesh Partition Sample** = muestrea; requiere elegir la **Definition** (`MPD_Terrain`) y el
    **canal** (`cliffs`) [56:18].
  - **Mesh Partition Texture Coordinates** con opción **UV unit** [37:05] — ver textures-materials.md.
- [58:04] La máscara llega en **canal rojo** → ComponentMask R → invertir con **1-x** [58:22]
  (negro=0, blanco=1, donde va el material nuevo) → **SmoothStep** con 0.5 para comprimir los
  grises a blanco/negro puros [58:39]-[58:54]. Equivalente a ColorRamp/MapRange de Blender [59:01].
- Resultado [59:10]: negro en valles, blanco en colinas = máscara de pendientes lista.

## 9. Assets y contenido
- [27:52] Materiales/texturas desde **Fab** (Add > Fab content). **Quixel** es la opción legacy,
  se descontinúa, pero el mismo contenido está en Fab [28:00]. Requiere login con cuenta Epic [28:08].
- [28:29] Filtro útil: Quixel Megascans → filtrar por precio → **solo free** = biblioteca completa
  gratuita. Luego Materials & Textures > Nature > Terrain/Vegetation/Rocky [28:54].
- Elegir calidad (el curso usa High) [29:03]. Los assets caen en `Content/Fab/Megascans/...` [30:14].
- [30:22] Recién importados quedan con asterisco = sin guardar.
- **Feature/content packs** [21:07]: Add > Feature or Content Pack. Traen quick-start scenes:
  first person, third person, top down, **virtual reality gameplay**, vehicle. Sirven para
  prototipar rápido y para aprender de blueprints hechos [21:24].
- El pack third person añade carpetas Characters, Input, Level Prototyping, ThirdPerson [21:50].
- Para jugarlo: Window > **World Settings** > sección **Game Mode** > `BP_ThirdPersonGameMode`
  (el que viene en el pack) [22:16] → Play [22:25]. Escape devuelve al editor [22:43].
- Mannequin como referencia de escala [38:06]: Characters > Mannequins > Mesh > `Man_Simple`,
 coordenadas 0,0 y subir en Z hasta que emerja del suelo.

## 10. Convenciones de nombrado
- [33:05] Convención estándar Unreal: **abreviatura del tipo de objeto + guion bajo + nombre**
  (`M_Terrain`) — permite filtrar y reconocer tipos de asset.

## 11. Orden de modificadores = prioridad numérica (crítico)
- [1:05:37] **Tools > Miscellaneous > Mesh Partition Outliner**: un outliner dedicado a los
  modificadores del mesh terrain, que muestra EL ORDEN de aplicación [1:05:50].
- El orden NO es la lista: es el campo **priority / sub-priority** numérico. Un modificador con
  priority 0 queda al fondo aunque lo hayas creado al final.
- TRAMPA que el curso paga dos veces:
  - [1:06:00] La proyección de textura (`slopes`) corría ANTES del esculpido (`hills`) → no óptimo.
    Fix: heightmap=0, sculpt=1, slopes=2 [1:06:11].
  - [1:28:19] Un brush nuevo nace con **priority 0**, o sea esculpe solo sobre el plano plano
    original y NO ve el resultado de los demás modificadores ("you might wonder what happened
    here"). Fix: subirlo por encima de todos [1:28:31].
- [1:34:41] Efecto visible del orden en el viewport: si el brush está DEBAJO del modificador de
  capas pintadas, ves otra textura mientras esculpes; poniéndolo en priority 4 ves las texturas
  de tus paint layers [1:34:58]. Al terminar, devolverlo a su sitio (2.5) y el mapping mejora [1:37:13].
- Regla práctica [1:23:45]: el boolean modifier debe ir **por encima de cualquier cosa que
  modifique el terreno** (heightmap y hills) → priority 1.1 en el ejemplo.

## 12. Boolean modifier (el "game changer" del curso)
- [1:22:31] Modifiers > Boolean: se arrastra un **static mesh** (p.ej. un Megascans
  `limestone_slab`) y se fusiona con el terreno.
- En Details > Mesh Component: por defecto viene en **Dynamic Mesh**; cambiar a **Static Mesh** y
  arrastrar el asset [1:22:46].
- [1:23:02] Sirve para **expandir** el terreno solapándolo. Puedes tener varios; Ctrl+D duplica el
  modificador y hereda todo [1:25:19]-[1:25:35].
- [1:24:15] Resultado: se puede mover/rotar/escalar **como un pincel de esculpido** y queda
  integrado de forma continua. Ventaja clave [1:24:23]: **no hace falta mezclar materiales** —
  el asset SE VUELVE terreno, así que hereda el material del terreno.
- [1:24:31] No necesitas estar en mesh terrain mode para ajustarlo: seleccionas el modificador y
  lo mueves/rotas directo.
- **Operaciones** [1:45:45]: sección Boolean > Operation = `Union` (fusiona) o `Subtract`
  (**recorta** el terreno → así se hace una cueva/entrada de mina). Imposible con el Landscape
  clásico [1:46:11].
- [1:45:13] Si el wireframe estorba: Details > Visuals > desactivar **Draw Wire Mesh** para ver el
  resultado real-time del booleano.
- Escala de trabajo del curso: ~7× la escala original del slab [1:25:02].

## 13. Remesh modifier (densidad de geometría)
- [1:29:17] `Remesh` aumenta la complejidad de la geometría en un área. No siempre es necesario.
- [1:29:34] Hay que arreglar el stack: ponerlo por encima del heightmap y de los hills (1.5).
- [1:29:41] **Alt+2** muestra el área remeshada en low-poly; **Alt+4** vuelve al lit viewport
  (estabas en wireframe).
- Methods [1:29:51]: `Remesh` (bajar **Target Edge Length** = más denso) o `Tessellate` (parte el
  tamaño de triángulo a la mitad). Además hay **selection level** para ir más lejos [1:30:09].

## 14. Artefactos de mapping tras booleanos (dos soluciones)
El boolean "conflicta con el mapping" [1:32:36]. En el MPD:
1. [1:32:54] **Channel Texel Size**: los canales se hornean a una textura temporal; reducirlo
   (100 → 30) sube la resolución y casi elimina los artefactos. OJO: **sube la memoria** [1:33:02].
2. [1:33:28] **Volume Encoded UV Mapping** (experimental, nuevo en 5.8): artefactos desaparecen
   por completo, pero aparece **texture stretching** → hay que remapear en el material del terreno
   usando **triplanar mapping** en vez del Mesh Partition Coordinate [1:33:43].
- El curso elige la opción 1 con valor **30** [1:34:06].

## 15. Nanite tessellation / displacement en el material
- [1:15:52] **Nanite Visualization > Triangles** muestra los triángulos Nanite de la escena. Por
  defecto el mesh terrain **ya soporta Nanite** [1:16:08].
- [1:16:22] En el material, sección **Nanite > Enable Tessellation**: trocea la geometría Nanite
  según la información de altura del material.
- [1:17:06] El canal **Displacement** del material recibe la info de altura (duplicar el setup de
  la textura de raíces/dirt). OJO: [1:18:50] **hay que conectar las UVs** o el displacement queda
  desalineado.
- [1:17:50] Nanite > Displacement > **Magnitude**: el curso prueba 15 (demasiado fuerte, con
  ruido [1:19:15]) y termina en **0.5**, que controla la fuerza de la teselación [1:19:31].
- [1:17:58] **Center Point** = el valor que NO desplaza (gris 0.5 por defecto, entre blanco y
  negro). Al mezclar materiales, las zonas sin info de altura deben aportar **0.5 plano** [1:18:15];
  el curso hace un **Lerp entre 0.5 y la altura real** [1:18:36].
- Decisión de diseño del curso [1:15:21]: NO usar displacement en las colinas (lejanas, de fondo)
  ni en el pasto (quedará tapado por foliage); solo en las raíces, donde da volumen.

## 16. Pintado manual de canales
- [1:08:29] Con el brush modifier `layers` seleccionado: **Paint Maps** > elegir canal (los
 canales propios del MPD aparecen ahí) > pintar. **Ctrl mientras pintas = despintar/devolver** [1:08:49].
- Uso del canal "inverso" [1:06:35]: la máscara de pendientes es estática, así que el curso crea un
  canal `cliffs_remove` para **quitar a mano** material donde no toca. En el grafo:
  muestrear `cliffs` y `cliffs_remove`, y **Multiply** la segunda sobre la primera ANTES de
  conectar al Alpha del blend [1:07:30].
- Apilar capas [1:10:41]: el resultado del primer `Blend Material Attributes` va al **A** del
  siguiente blend, el material nuevo al **B**, y la máscara (canal del MPD) al **Alpha**. Así se
  añaden capas indefinidamente.
- [1:12:50] Si una capa queda demasiado brillante: **Multiply** sobre el RGB (p.ej. 0.2).
- [1:12:10] **Snapping on surface** coloca el mannequin/objetos justo sobre el terreno al arrastrar.
- [1:09:47] Preferencia del autor: Ctrl+C/Ctrl+V en vez de Ctrl+D para duplicar setups grandes,
  porque si se solapan es fácil romper cosas.

## 17. Water body river (plugin Water)
- [1:37:29] Place Actors > buscar "water" > **Water Body River**. Trae una spline y un
  water body por defecto [1:37:40].
- Colocación [1:38:04]: activar **snapping** para rotar en 90° exactos; luego W y subir en Z hasta
  que el agua aparezca donde quieres (se ve el flujo) [1:38:12].
- Splines [1:38:26]: mover los puntos a mano para casarlos con el terreno; **Alt+arrastrar un
  punto = crear punto nuevo** [1:39:01]; top view + modo lit para ver el cauce [1:38:34];
  snapping to terrain disponible para los puntos [1:39:41].
- Ancho por punto [1:40:30]: seleccionar el punto > Spline Comp > sección **Water > Width**
  (p.ej. 1000 para estrechar); más atrás aún más estrecho para que desaparezca [1:40:45].
- **River modifier del interop** [1:41:54]: con el water body seleccionado, Add Component >
  buscar "modifiers" > **River Modifier** > elegir qué Mesh Partition afecta → **recorta el
  terreno automáticamente según la spline** [1:42:15]. Si estrechas la spline, el corte se estrecha.
- DECISIÓN DEL CURSO [1:42:38]: el river modifier es bueno para enfoques **procedurales de
  gran escala**, pero para una escena pequeña el autor lo BORRA y esculpe a mano, porque de todos
  modos hay que esculpir las orillas después del modificador [1:42:53]. Lección: lo procedural no
  siempre gana en escenas chicas.
- [1:43:10] Pintar `dirt` en el cauce y las orillas (brush 500) con el agua oculta (Hide) para ver.

## 18. PVE — Procedural Vegetation Editor (árboles generados en el motor)
- [1:50:14] Content Browser > right click > **Foliage > New Procedural Vegetation**. Da plantillas
  (tree, conifer, shrub, plant) — el curso usa plantillas porque "no soy botánico" [1:50:22].
- [1:51:11] Valor: ya **no dependes de assets de árboles externos ni de SpeedTree**; creas el
  bosque completo dentro de Unreal [1:51:34].
- Grafo, de izquierda a derecha [1:51:40]-[1:55:39]:
  1. **Starter node** con "grower cycles".
  2. **Grower** = crea el esqueleto del árbol; su forma depende de una lista de propiedades muy
     larga (abrumadora, cambiar y observar) [1:51:56].
  3. **Grower Distributor** = añade ramitas, densifica el esqueleto [1:52:18]. Los grafts vienen
     de otro grower → pasarlos por un **Palette node** [1:52:46].
  4. Más grower nodes para ramas adicionales [1:53:02].
  5. Sección **Edit**: `carve` recorta el esqueleto final (0.04 → bajar reduce el árbol) [1:53:11];
     **Manual Edit** permite seleccionar puntos y moverlos, y **recuerdan la posición** [1:53:18];
     otro carve + **gravity** para bajar las ramas [1:53:35].
  6. **Mesh Builder** construye la malla del árbol con su textura [1:53:43].
  7. **Foliage Distributor** = uno de los pasos finales [1:55:33].
- Datos personalizables, todos en contenido del plugin (copiar a tu Content y editar, igual que el
  MPD) [1:54:13]:
  - **Loader** node → `trunk profiles`, que apunta a un **JSON con datos vectoriales** de perfiles
    [1:54:20].
  - **Texture setup** = archivo de definición que carga ciertas texturas [1:54:37].
  - **Foliage palette** = catálogo de ramitas; puedes poblarlo con TUS static meshes de hojas [1:54:56].
- **Export node** [1:56:00]: define la carpeta de salida y si exportas como **static mesh** o
  **skeletal mesh**. Si es skeletal → funciona con el **nuevo sistema de viento** y produce
  animación de viento realista [1:56:07]. Trae default tree wind settings (también del plugin,
  copiables) [1:56:23].
- ERROR DE EXPORT QUE EL CURSO PAGA [1:56:56]: "the mount point for export path is not correct" →
  la ruta debe ser **`/Game/...`** (empezar con slash y decir Game), no una ruta de carpeta de
  proyecto [1:57:04]. Además el nombre del export no debe **colisionar** con el nombre del asset
  PVE [1:57:20].
- [1:57:51] El skeletal mesh exportado, arrastrado tal cual a la escena, **NO se anima**: para que
  el viento funcione haría falta un Actor Blueprint que lo spawnee como skeletal mesh dentro. En la
  práctica se spawnea vía PCG, que sí lo resuelve [1:57:58].

## 19. PCG forest — el flujo completo
Setup base [1:58:46]-[2:01:40]:
1. Right click > **PCG Graph** > Create Empty Graph (`PCG_Forest`).
2. **Mesh Partition Query** (específico de mesh terrain) → consulta el terreno [1:59:32].
3. **Surface Sampler** estándar de PCG → muestrea la query [1:59:45].
4. Arrastrar el PCG graph a la escena → crea un actor con **bounding box**: nada se spawnea fuera
   de esos bounds; escalarlo con R [2:00:10].
5. TRAMPA [2:00:44]: en el Mesh Partition Query, **Query Type = `Final`**. Las opciones son base
   object / intermediate layers / final. Si dejas otra, el terreno original es PLANO y más bajo,
   así que tu bounding box quizá ni lo toca [2:00:59].
6. Debug: **tecla A** = muestra atributos (el punto amarillo; los atributos son variables que cada
   spawn point lleva) [2:01:08]. **Tecla D** = debug node (el azul), muestra el cubo PCG por
   defecto sobre la superficie [2:01:33].
7. **Density** del surface sampler: 1 = muy denso; el curso usa 0.03 → 0.003 para árboles [2:02:23].
   Los cubos blancos/negros del debug = distintos valores de densidad [2:02:06].
8. **Seed** del surface sampler [2:09:05]: con la MISMA density, cambiar la seed mueve los puntos a
   otro lado. Si duplicas un setup, **cambia la seed** o las dos capas caen en los mismos puntos
   [2:09:19], [2:21:58], [2:36:37].

Spawners:
- Static mesh: **Static Mesh Spawner** > botón **+** (mesh entries) > arrastrar el mesh [2:02:46].
  Modo por defecto **Weighted**: los pesos (5,5,3,2,1,1) distribuyen qué variante sale [2:32:26].
- Skeletal (árboles PVE con viento): **Instanced Skeletal Mesh Spawner** [2:03:01]. NO se puede
  enchufar directo: hay que pasarlo por atributos [2:03:10]:
  - **Add Attribute** node → nueva columna, tipo **Soft Object Path** → arrastrar el skeletal mesh
    [2:03:25]-[2:03:45]. Con A se ven las 3 columnas [2:03:52].
  - En el spawner, elegir el atributo (`tree`) y el **Template Descriptor =
    `Transform Wind Transform Provider`** [2:04:17] → SIN eso no hay viento; CON eso los árboles
    quedan animados con viento global [2:04:32].
- **Transform Points** entre sampler y spawner [2:05:03]: controla escala y rotación.
  - `Absolute Rotation` → que crezcan rectos hacia arriba [2:05:25]. Al final el curso lo QUITA
    para grass/rocks/river rocks, porque sin él las rotaciones son más naturales [2:54:04].
  - Random rotation: 360° en Z + ~2° en X/Y para un tilt sutil [2:06:26].
  - Scale: 2 a 4 para árboles grandes = dosel/canopy [2:05:47]. Shrubs: 0.5 min a 2 max [2:10:14].
  - Offset Z: los árboles junto al cauce aparecen "empezando sobre la superficie" → offset
    **-70 a -100** los hunde [2:07:03]. Para grass, -70 los entierra: usar **0 a -5** [2:32:57].
    Rocks: -5 a -25 [2:43:50].

Distribución natural [2:10:52]-[2:12:18]:
- **Spatial Noise** = el nodo que más se usa: modifica la densidad de forma irregular y crea
  parches. En Transform > Scale, 10×10 da "streaks" [2:11:21].
- **Density Filter** recorta por **Lower Bound** (0.4, 0.6, 0.7...): deja solo los puntos más
  densos [2:11:45].
- Por qué [2:12:09]: en la naturaleza las cosas **se agrupan** (clumping); el resultado son
  hotspots + mucho espacio vacío, que es lo natural [2:12:31].
- Para un bosque mixto europeo: usar spatial noise para agrupar tipos similares de árboles [2:12:47].

## 20. PCG: bounds y exclusiones con splines
- [2:14:16] Dos formas de hacer la spline: buscar "spline" y colocarla, o **Modeling Mode >
  Draw Spline** y dibujarla DIRECTO sobre la superficie [2:14:40]. Activar **Loop** para cerrarla,
  luego Accept [2:15:10].
- Etiquetado: el actor spline va en una carpeta `PCG` del Outliner [2:15:27], se renombra
  (`forest_bounds`) y en Details > Actor > **Advanced > Tags** se le pone una tag
  (`PCG_bounds`) [2:15:54].
- En el grafo: **Get Spline Data** → **Spline Sampler** [2:16:18].
  - Selector: `Self` si el PCG es parte de un blueprint; aquí **All World Actors** [2:16:33].
  - **Select by Tag** = `PCG_bounds`; **Select Multiple** si hay varios actores con la misma tag
    [2:21:19] (sin activarlo, la segunda spline no excluye nada [2:21:33]).
  - **Select by Class** = p.ej. `WaterBody` — así la exclusión del río funciona con CUALQUIER
    water body sin tocar la construcción [2:22:36].
  - Modo: **On Interior** para usarla como bound de área [2:17:05]; **On Spline** para muestrear
    la curva (río) [2:22:50]. OJO: poner `On Interior` con by-class de water body DA ERROR [2:22:43].
- **Bounds Modifier** [2:17:17]: los puntos siguen siendo puntos; esto les da volumen (80 hacia
  abajo + 80 hacia arriba) para poder intersectarlos con el sampler. Con 40 basta porque solo se
  intersecta con puntos que ya están sobre el terreno [2:18:02].
- Para el río: bounds modifier más agresivo (200/200) [2:23:06] y **Subdivide** el sampler (×10,
  ×50, ×75) porque hay pocos puntos muestreados y salen "líneas largas" [2:23:20]-[2:51:27].
- Operaciones de conjunto:
  - **Bounding shape** del sampler ← el bounds de la spline interior [2:17:46].
  - **Difference** [2:19:36]: Source = lo que quieres conservar, y se le enchufan varias fuentes a
    excluir (exclude, exclude2, río) — **acepta múltiples entradas**, no hace falta repetir el
    setup [2:24:05].
  - **Intersection** [2:51:38]: combina los puntos de superficie con la forma de la spline →
    rocas solo en las orillas del río.
- Anti-colisión entre capas [2:45:42]: si una roca grande spawnea dentro de un árbol, arrastra la
  salida del **tree spawner** al **Difference** del spawner de rocas (usa el bounding box real del
  mesh final). Y a la inversa: tomar los bounds de las rocas y restarlos de árboles/grass/nettle
  [2:46:35]. Así ningún árbol atraviesa una roca.
- Near bounds [2:28:58]: para el grass no sirven los bounds grandes (no hace falta pasto denso en
  todo el km²): dibujar una spline chica alrededor del punto focal, tag `PCG_near_bounds`.
- Densidad de grass [2:30:43]: spawner density 1, y para que quepan más puntos bajar
  **Point Extents** a 0.05 (casi invisibles) y luego subir la density a 5-7 [2:31:14].
- [2:33:14] El grass ya viene animado porque **el viento está en el shader** (otro tipo de
  animación que el skeletal de los árboles).

## 21. Nanite, LOD y billboarding en foliage
- [2:33:22] El grass hace **billboarding** a distancia (LOD → se vuelve una imagen 2D). Buena
  optimización, pero molesta al moverse en un área chica ya recortada [2:33:44].
- Fix [2:34:49]: abrir el **static mesh** (OJO: los Static Meshes, NO los "Foliage Types", que son
  para el foliage painting) → **LOD = Auto** → activar **Custom** y **borrar el LOD 2** de la
  lista → sin billboarding. Hay que hacerlo en TODAS las variantes [2:35:12].
- [2:35:19] Lit Mode > **Nanite Visualization > Triangles**: todo es Nanite menos el grass. Los
  skeletal meshes de PVE **sí son Nanite foliage** [2:35:28].
- Fix [2:35:40]: seleccionar todos los static meshes > right click > **Nanite > Enable** → la
  escena entera soporta Nanite, que optimiza mucho [2:35:53].
- [2:39:59] El grass de Megascans viene demasiado brillante: abrir su **Material Instance** y
  tocar Base Color / bajar Roughness para alinearlo con el resto del foliage [2:40:08].

## 22. Utilería y vestido de escena
- [1:49:02] **Bookmarks de cámara**: Ctrl+1 guarda la vista actual como bookmark 1; luego 1 la
  restaura, Ctrl+2/2 para una segunda vista. Útil para volver siempre al encuadre objetivo.
- [2:24:23] **Ctrl+L en el viewport y mover el mouse** = cambiar el ángulo de la luz del sol en
  tiempo real (para buscar luz rasante de atardecer).
- [2:13:55] **E sobre un nodo PCG** = habilitar/deshabilitar el nodo (para previews limpias:
  deshabilitas todo y solo ves los bounds).
- [2:54:35] Colapsar carpetas del Outliner deja la escena navegable sin ruido.
- [3:00:35] Vestir una escena con assets: abrir el material del asset y bajar **Brightness** /
  subir **Saturation** para integrarlo (madera más marrón, rocas más oscuras).
- [3:01:16] Si la visibilidad es mala (interior de mina): **Point Light** amarillento, y luego
  colocar una linterna/farol para que la luz tenga sentido diegético [3:01:34].
- [3:04:13] Para el fuego de la fogata: duplicar un point light y meterlo dentro del fuego.
- [3:04:44] Ajustar **Exponential Height Fog**: falloff y density según la luz (subir el falloff
  con luz rasante) [2:08:24] — con demasiada niebla y sombra, la escena se ve enterrada.
- [2:56:14] Si el suelo del bosque queda muy brillante: abrir el material del terreno y bajar el
  Multiply de la capa de raíces (0.2 → 0.1) [2:56:27].
- Water Body River material [2:54:42]: el material del agua vive en **contenido del motor** →
  Ctrl+C / Ctrl+V a tu carpeta, renombrar `MI_River` (MI = material instance), reasignarlo al
  water body y recién ahí editarlo [2:55:29]. Controles útiles: **Scattering**, **Brightness**,
  **Absorption Color** (verduzco y oscuro = arroyo de bosque, no tropical) [2:55:43].

## 23. Novedades 5.8 mencionadas (fuera del flujo del curso)
- [1:07] **Mesh to MetaHuman**: además de cabezas, ahora soporta **cuerpos**; convierte cualquier
  mesh de personaje humano en un MetaHuman riggeado en un solo flujo.
- [1:14] **MetaHuman Animator**: captura la animación completa del personaje con **UNA sola cámara**
  (sin trajes de mocap).
- [1:24] **Direct Mesh Controls**: los control rigs se representan directo sobre la malla del
  personaje; los animadores manipulan el rig tocando la superficie → animación facial intuitiva.
- [1:31] **Toon shader** nuevo, construido sobre el framework **Substrate**, para estilos cartoon
  y anime.
