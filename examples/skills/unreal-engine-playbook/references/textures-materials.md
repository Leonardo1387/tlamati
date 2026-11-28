# Texturas, materiales PBR y pipeline Poly Haven → Unreal

Destilado 27-nov-2026. Casi todo **[MEDIDO]**: viene del proyecto proyecto-archviz
(`evidencia/s10_lexico_materiales.json` v3, `s10_ph_mapa.json`, 48 texturas en disco) y de
llamadas MCP verificadas. **[DOC]** = documentación del corpus sin comprobar aquí.

## 1. Fuente de texturas [MEDIDO]
- Proveedor **Poly Haven**, licencia **CC0** (dominio público).
- API verificada HTTP 200: `https://api.polyhaven.com/assets?t=textures` → 872 texturas (26-nov-2026).
- Descarga: `https://api.polyhaven.com/files/{id}` → json con `ftp_root` y mapas por resolución.
- 4 mapas por material: **diffuse, nor_gl, rough, ao** (en disco: `{id}_{diff,nor_gl,rough,ao}_2k.jpg`).
- **[MEDIDO]** 12 ids Poly Haven usados en el proyecto, 48 archivos 2K = 109 MB en
  `evidencia/s10/texturas/`: american_walnut_veneer, beige_wall_001, concrete_block_wall,
  concrete_floor_worn_001, dark_wood, floor_tiles_08, metal_plate, metal_plate_02,
  poly_wool_herringbone, terracotta_floor_tiles, wood_floor_deck, wool_boucle.

## 2. TRAMPA del normal map OpenGL vs DirectX [MEDIDO]
- Poly Haven entrega `nor_gl` = normal **OpenGL (+Y arriba)**. Unreal espera normal
  **DirectX (−Y)**. Hay que **invertir el canal verde** (en Blender) o marcar `sRGB=False`
  y usar el flag de canal. Si se importa tal cual, el relieve sale invertido (bultos→hoyos).
- **[MEDIDO s12]** Unreal **auto-detecta el normal map por el NOMBRE del archivo**: `nor_gl`
  entró como `TC_Normalmap` con `sRGB=False` solo. Verificar el Compression Settings del
  Texture2D resultante (`TC_Normalmap`) antes de confiar.

## 3. Importar texturas por MCP [MEDIDO]
- `TextureTools` tiene **SOLO** `get_size` e `import_file`. Firma:
  `TextureTools.import_file(folder_path, asset_name, source_file)`; acepta rutas UNC
  `\\wsl.localhost\...`.
- **[MEDIDO]** `import_file` devuelve una **LISTA** `[{refPath}]` → desanidar (`[0]['refPath']`).
- **[MEDIDO]** Antes de importar/crear un asset, preguntar `AssetTools.exists(path)`: los
  assets de una corrida fallida quedan en memoria y re-intentar revienta con
  *"asset with that name already exists"*.
- Convención de nombres del proyecto: textura UE = `T_<polyhaven_id>_{diffuse,nor_gl,rough,ao}`.

## 4. Construir el material PBR por MCP [MEDIDO]
`MaterialTools` (nodos útiles confirmados en s12):
- `create_material`, `add_expression` (quiere x/y float), `connect_expressions`,
  `connect_to_output(expression, output_name="RGB", material_property="MP_BaseColor")`,
  `create_parameter_collection`, `recompile` — **todos funcionan**.
- `list_expression_classes` **EXIGE** el param `search` (pasar `""`); devuelve 354 clases
  como dicts `{refPath:/Script/Engine.MaterialExpression...}`.
- Nodos clave: `MaterialExpressionTextureSampleParameter2D` (props: texture, samplerSource,
  samplerType, constCoordinate, constMipValue), `TextureSample`, `Multiply`, `ScalarParameter`,
  `TextureCoordinate`, `AppendVector`, `Constant3Vector`, `OneMinus`, `LinearInterpolate`.
- Cableado PBR típico: diffuse→BaseColor (RGB), rough→Roughness (canal), nor_gl→Normal,
  metallic→Metallic (0 o 1 para no-metales/metales). Material UE nombrado `M_<clave>`.

## 5. Tiling a escala real (para que NO se vea repetido) [MEDIDO + DOC]
- Convención del proyecto: `tiling_cm` = tamaño físico del cuadrado de textura al 100% de UV.
  Blender escala UV para que el m² se vea a escala real; en Unreal se aplica con
  **ScalarParameter + UV scaling** (TextureCoordinate → Multiply por scalar).
- **[DOC — quad_remesher]** Al empaquetar islas UV, dejar **margen de unos pocos %** entre
  islas: sin él el bake agarra texels de la isla vecina y produce seam artifacts.
- **[DOC — bloom/hdri]** Texturas que NO deben streamear ni generar mips (cubemaps,
  backdrops de calidad full): `Mip Gen Settings = No Mipmaps`, `Never Stream = Enabled`.

## 6. Léxico español-del-plano → material jugable (16 términos MEDIDOS, v3 2026-11-26)
Propósito: diccionario entre cómo rotula la gente un plano 2D y un material PBR en Unreal.
Se consulta desde la etapa de visión (JPG→DXF) y alimenta Blender (PBR) y Unreal (TextureSample).
Reglas de resolución: (1) coincidencia literal de frase gana; (2) si no, clasificar por
tipo_superficie (piso/muro/tapizado/marco) y tomar default; (3) **NUNCA convertir el
adjetivo de color a RGB directo** — el look lo dan roughness+tiling propios de cada entrada;
(4) si no hay entrada, crear clave nueva tipo_superficie=piso, roughness 0.6, y registrarla.

| clave | superficie | polyhaven_id | rough | metal | tiling | hex |
|---|---|---|---|---|---|---|
| porcelanato_concreto_gris | piso | concrete_floor_worn_001 | 0.28 | 0.0 | 200cm | #B9B7B2 |
| roble_oscuro_ingeneria | piso | dark_wood | 0.42 | 0.0 | 150cm | #6B4E32 |
| deck_exterior | piso_exterior | wood_floor_deck | 0.62 | 0.0 | 120cm | #8A6A45 |
| latex_mate_blanco_roto | muro | beige_wall_001 | 0.88 | 0.0 | 300cm | #F2F0EC |
| acrilico_banera | mobiliario | (sin textura) | 0.12 | 0.0 | — | #FAFAF8 |
| vidrio_templado | transparente | (sin textura) | 0.03 | 0.0 | — | #DCE6E4 |
| aluminio_negro_perfileria | marco | metal_plate | 0.35 | 0.9 | 100cm | #1E1E20 |
| tela_boucle_gris | tapizado | wool_boucle | 0.92 | 0.0 | 60cm | #5A5A62 |
| alfombra_lana_beige | tapiz | poly_wool_herringbone | 0.95 | 0.0 | 100cm | #C8B49A |
| acero_negro_mate | estructura | metal_plate_02 | 0.55 | 1.0 | 100cm | #232326 |
| madera_carpinteria | mobiliario | american_walnut_veneer | 0.38 | 0.0 | 120cm | #7A5A3A |
| madera_maciza | mobiliario | dark_wood | 0.45 | 0.0 | 100cm | #6B4E32 |
| luminaria | emisor | (sin textura) | 0.5 | 0.0 | — | #FFF3E0 |
| baranda | transparente | (sin textura) | 0.05 | 0.0 | — | #DCE6E4 |
| maceta_vegetal | prop | terracotta_floor_tiles | 0.7 | 0.0 | 40cm | #A8624A |
| loseta_bano | piso | floor_tiles_08 | 0.3 | 0.0 | 60cm | #9A9A96 |

Notas de criterio MEDIDAS del léxico:
- "porcelanato efecto concreto pulido" NO es concreto estructural: es porcelanato que imita
  concreto → brillo bajo-medio y veteado suave, no agregado visto.
- madera "natural" = sin barniz alto brillo (satinado); "oscuro" en habla común = medio, no café-negro.
- El sufijo `_NN` en el nombre del material = espesor en cm (concreto_block_15 = 0.15 m);
  los materiales que NO son muro no llevan sufijo. El extractor lo lee.
- Múltiples claves pueden compartir polyhaven_id (dark_wood sirve a roble_oscuro y madera_maciza;
  beige_wall_001 a Latex_Mate_12 y _20; concrete_floor_worn_001 a porcelanato y concreto_losa).
  El `s10_ph_mapa.json` tiene 15 entradas de mapa → 12 ids únicos.

## 7. Valores PBR medidos del mundo real (fuente: Epic, physically-based-materials) [DOC]
Útiles para materiales SIN textura del léxico (vidrio, acrílico, luminaria, baranda) y para
sanity-checkear los que sí la tienen. Todos los inputs PBR aceptan 0..1.
**BaseColor de no-metales** (intensidad; es el color fotografiado con filtro polarizador,
que elimina el specular de los no-metales):
| Material | BaseColor | | Material | BaseColor |
|---|---|---|---|---|
| Charcoal | 0.02 | | Desert sand | 0.36 |
| Fresh asphalt | 0.02 | | Fresh concrete | 0.51 |
| Worn asphalt | 0.08 | | Ocean ice | 0.56 |
| Bare soil | 0.13 | | Fresh snow | 0.81 |
| Green grass | 0.21 | | | |

**BaseColor de metales** (RGB lineal 0..1):
| Metal | R | G | B | | Metal | R | G | B |
|---|---|---|---|---|---|---|---|---|
| Iron | 0.560 | 0.570 | 0.580 | | Nickel | 0.660 | 0.609 | 0.526 |
| Silver | 0.972 | 0.960 | 0.915 | | Titanium | 0.542 | 0.497 | 0.449 |
| Aluminum | 0.913 | 0.921 | 0.925 | | Cobalt | 0.662 | 0.655 | 0.634 |
| Gold | 1.000 | 0.766 | 0.336 | | Platinum | 0.672 | 0.637 | 0.585 |
| Copper | 0.955 | 0.637 | 0.538 | | Chromium | 0.550 | 0.556 | 0.554 |

**Specular medido desde IOR** (el default de Unreal es **0.5 ≈ 4 % de reflexión**, correcto
para la gran mayoría de materiales): Glass 0.5 · Plastic 0.5 · Quartz 0.570 · Skin 0.35 ·
Milk 0.277 · Water 0.255 · Ice 0.224.

**Reglas duras de Epic:**
- **Metallic es BINARIO** (0 no-metal / 1 metal). Valores intermedios solo para híbridos
  reales (óxido, polvo, corrosión). ⇒ coincide con el léxico: los metales del proyecto llevan
  0.9 y 1.0, y el 0.9 de `aluminio_negro_perfileria` es el único "intermedio" — justificable
  solo si es aluminio pintado/anodizado; si es aluminio puro, debe ser 1.0.
- **NUNCA bajar Specular a 0 para hacer un material "mate".** Todos los materiales tienen
  specular. La forma correcta de hacer algo muy difuso es **Roughness alta**. (El léxico ya
  lo cumple: latex_mate 0.88, boucle 0.92, lana 0.95 — roughness alto, specular intacto.)
- El input **Specular NO es para mapas de variación**; la variación de superficie va en el
  **Roughness map**.
- **Metallic map = solo blanco y negro**, sin grises intermedios: la pintura NO se mezcla con
  el metal, se sienta encima. (Un panel metálico pintado: Metallic=0 donde hay pintura, =1
  donde se ve el metal.)
- **Cavity maps** (micro-oclusión que las sombras realtime no capturan, p.ej. grietas del
  normal map): es un AO de distancia de trazo muy corta. Se aplica
  `BaseColor = Cavity * oldBaseColor` y `Specular = Cavity * 0.5`. Epic: no es necesario
  para el 99 % de materiales.
- Roughness 0 = espejo, 1 = mate perfecto. Oscuro en el roughness map = espejo; claro = rugoso.
- **OJO**: este documento NO trae tabla numérica de roughness (solo BaseColor y Specular).
  Los roughness del léxico del proyecto son criterio curado, no valores medidos de Epic.

## 8. Nor_gl (OpenGL) vs DirectX: YA RESUELTO, con medición [MEDIDO 27-nov, editor vivo]
**[DOC]** Dos fuentes del corpus (StraySpark) afirman: "Unreal uses **DirectX (Y−)** normals.
Use the `_Normal_DX` map, not `_Normal_GL`. The wrong one inverts every bump." Y advierten la
trampa "agarrar `_Normal_GL` porque va primero alfabéticamente — ese es el mapa de Blender/Godot".
El proyecto usa `nor_gl` (Poly Haven no entregó `nor_dx` en el set descargado), así que la
sospecha de relieve invertido era razonable. **Se midió y está bien:**

```
ObjectTools.get_properties(instance={"refPath": "/Game/ProyectoUE_S10/Tex/T_x_nor_gl.T_x_nor_gl"},
                           properties=["bFlipGreenChannel","CompressionSettings","SRGB"])
→ {"bFlipGreenChannel": true, "CompressionSettings": "TC_Normalmap", "SRGB": false}
```
**Censo completo de las 48 texturas importadas (11/11 nor_gl, 11/11 diff, 11/11 rough, 11/11 ao):**
| sufijo | Compression | sRGB | bFlipGreenChannel | n | ¿correcto? |
|---|---|---|---|---|---|
| diff | TC_Default | **true** | false | 9 (+2 defecto §8b) | ✅ |
| rough | TC_Default | **false** | false | 9 (+2 defecto) | ✅ sRGB off = correcto (es data) |
| ao | TC_Default | **false** | false | 9 (+2 defecto) | ✅ |
| nor_gl | **TC_Normalmap** | **false** | **true** | 11 | ✅ **convención corregida** |

**Conclusión [MEDIDO]:** `bFlipGreenChannel=true` hace exactamente lo que la guía pide al usar
`_Normal_DX` — invierte el canal verde, convirtiendo OpenGL(+Y) en DirectX(−Y) en la importación.
**No hay relieve invertido. No tocar nada. NO re-descargar `nor_dx`.**
Lección de método: la guía externa y el proyecto no estaban en contradicción — el proyecto ya
había aplicado el fix por otra vía (flag de importación en vez de elegir el otro archivo).
Antes de declarar una contradicción, MEDIR el asset; el grep binario no basta (ver §8b).

### 8b. Dos defectos REALES encontrados al auditar [MEDIDO]
1. **6 texturas con `TC_EditorIcon`** en vez de `TC_Default`:
   `T_poly_wool_herringbone_{ao,diff,rough}` y `T_wool_boucle_{ao,diff,rough}`.
   **Causa raíz medida:** son las ÚNICAS 2 texturas del set cuyas dimensiones **no son múltiplo
   de 4** — `poly_wool_herringbone` = 2048×**2091**, `wool_boucle` = 2048×**2538**; las otras 10
   son 2048×2048. El auto-detect del importador las clasificó como icono/editor.
   `TC_EditorIcon` usa compresión pensada para UI: sin mips ni streaming adecuados → se verá
   peor que las demás a distancia (aliasing) justo en las 2 telas (alfombra lana beige y tela
   boucle, ambas de tapizado = primer plano).
   **Fix (barato):** `ObjectTools.set_properties` con `CompressionSettings="TC_Default"` en las 6
   (el nor_gl de esas 2 sí entró bien como TC_Normalmap). O recortar a 2048×2048 y re-importar.
2. **`metal_plate_02` nunca se importó.** Está en disco (`evidencia/s10/texturas/`, 4 archivos
   2048×2048) y está en el léxico como `acero_negro_mate`, pero **NO existe `M_acero_negro_mate`**
   en `Mat/` y sus texturas no están en `Tex/`. ⇒ 11 de 12 ids Poly Haven importados; el léxico
   tiene 16 términos pero solo 15 materiales creados (faltan acero_negro_mate; y hay 2 extras
   fuera del léxico: `M_Cielo_Raso` y `M_vidrio_ventana`/`M_loseta_ceramica_gris`).

### 8c. TRAMPA DE MEDICIÓN pagada: el grep binario da falsos positivos [MEDIDO]
`grep -ao "T_[a-z0-9_]*_diff" M_aluminio_negro.uasset` devolvió `T_aluminio_negro_diff` Y
`T_metal_plate_diff`, sugiriendo 2 sets de texturas (uno colgante). **FALSO.** Esos nombres son
los **ParameterName** de los `MaterialExpressionTextureSampleParameter2D`, no referencias de
asset. La prueba autoritativa es `AssetTools.get_dependencies(asset_path=...)`:
```
get_dependencies("/Game/ProyectoUE_S10/Mat/M_aluminio_negro.M_aluminio_negro")
→ [".../T_metal_plate_ao",".../T_metal_plate_diff",".../T_metal_plate_nor_gl",".../T_metal_plate_rough"]
```
Solo 4 dependencias, todas válidas. **Regla: para saber qué usa un asset, `get_dependencies`;
el grep sobre el .uasset solo muestra la tabla de nombres (ParameterNames incluidos).**
Nota de diseño positiva [MEDIDO]: el grafo nombra los parámetros de textura con la clave del
léxico (`T_aluminio_negro_diff`) aunque apunten al id de Poly Haven (`T_metal_plate_diff`) —
o sea que ya están preparados para convertirse en Material Instances sin re-cablear (§9).

### 8d. Firmas MCP corregidas (los nombres de params NO se adivinan) [MEDIDO]
- `ObjectTools.get_properties(instance={"refPath": "..."}, properties=["..."])` — **NO** `ref_path`.
  `instance` es objeto anidado con clave `refPath`.
- Devuelve `{"returnValue": "<JSON como string>"}` y a veces ya viene como dict → **unwrap
  robusto**: `while isinstance(rv,str): rv=json.loads(rv)`. Un parse fijo revienta con
  `TypeError: the JSON object must be str... not dict`.
- `AssetTools.get_dependencies(asset_path=...)` — NO `asset`. `AssetTools.exists(path=...)`.
- `MaterialTools.get_expressions(material_or_function={"refPath":...})` — NO `material`.
  **NO existe `list_expressions`** (devuelve "Unknown tool"). Devuelve lista de `{refPath}`
  donde el sufijo tras `:` es el tipo de nodo + índice.
- Toolsets de materiales: `editor_toolset.toolsets.material.MaterialTools` Y
  `editor_toolset.toolsets.material_instance.MaterialInstanceTools` (**existe y no estaba
  documentado en la memo** — es el que se necesita para la jerarquía de §9).
- Los toolsets van **calificados**; con nombre corto (`ObjectTools`) responde
  "Toolset 'ObjectTools' not found". `list_toolsets` devolvió **60** esta sesión (la memo decía 26).
- `mcp_ue.UE` es una **CLASE**: `ue=UE(); ue.connect()` — no `import mcp_ue; mcp_ue.UE.call(...)`.

### 8e. Estado REAL del grafo de materiales [MEDIDO — base para la refactorización de §9]
`MaterialTools.get_expressions` sobre los 20 materiales de `ProyectoUE_S10/Mat/` → **solo 4
grafos distintos**:
| ×n | nodos | grafo |
|---|---|---|
| **15** | 9 | TextureCoordinate → Multiply ← 2×ScalarParameter; 4× TextureSampleParameter2D (diff/nor_gl/rough/ao) |
| 2 | 2 | Constant3Vector + ScalarParameter |
| 2 | 3 | Constant3Vector + 2×ScalarParameter |
| 1 | 3 | 2×Constant3Vector + ScalarParameter |
Sin textura (0 TextureSample): `M_Cielo_Raso`, `M_acrilico_banera`, `M_luminaria`, `M_vidrio`,
`M_vidrio_ventana`.
**Diagnóstico:** los 15 materiales texturizados tienen **exactamente el mismo grafo** — es el
patrón de duplicación que §9 dice evitar (15 PSOs donde cabría 1 master + 15 instances).
Es el candidato ideal para la conversión: `M_Surface_Opaque` master + `MaterialInstanceTools`.
No es urgente para M1 (caminar) pero sí para M3 (que se vea bien) y para el tiempo de cook.


## 9. Arquitectura de materiales: master + instances [DOC — aplica DIRECTO al proyecto]
Fuente: StraySpark, "Master Materials and Material Instances: The Complete Guide".
**[MEDIDO 27-nov] El proyecto tiene 20 materiales** en `ProyectoUE_S10/Mat/` y, por §8e,
**15 de ellos comparten el mismo grafo exacto de 9 nodos**. La guía dice que un proyecto bien
organizado tiene **3 a 8 master materials en TOTAL**, no por asset.
- **Por qué importa (mecanismo):** un Material NO es un set de valores, es un PROGRAMA que se
  compila a HLSL → bytecode **una vez por permutación** (vertex factory × quality level ×
  static switches). Un Material Instance **NO compila nada**: guarda una tabla de overrides de
  parámetros que se suben como constantes de shader y apunta al shader YA compilado del padre.
  ⇒ 1000 instances = 1000 tablas chicas + **0 compilaciones**. Duplicar un material para
  cambiar un color = recompilación completa + PSO nuevo + rompe el batching.
- **Cada material único = un PSO distinto**, y el conteo de PSOs es lo que causa el *shader
  stutter* de los juegos Unreal. 19 materiales sueltos = 19 PSOs donde podría haber 1-2.
- **Set recomendado para un juego 3D:** `M_Surface_Opaque` (la gran mayoría de superficies),
  `M_Surface_Masked` (alpha cutout: rejas, follaje), `M_Translucent` (vidrio, agua),
  `M_Decal`, `M_UI`, `M_Character` (solo si piel/tela necesita otro lighting model).
  ⇒ Para este proyecto bastan **2**: `M_Surface_Opaque` (los 15 texturizados de §8e) y
  `M_Translucent` (los 5 sin textura: M_vidrio, M_vidrio_ventana, M_acrilico_banera,
  M_luminaria, M_Cielo_Raso — estos hoy son Constant3Vector+Scalar, o sea color plano).
  Los 16 términos del léxico serían instances. **Y la toolset existe:**
  `editor_toolset.toolsets.material_instance.MaterialInstanceTools` [MEDIDO en list_toolsets].
  Los ParameterName ya llevan la clave del léxico (§8c) ⇒ la conversión no requiere re-cablear.
- **TRAMPA DEL STATIC SWITCH** (el conocimiento de mayor valor de la guía): los Scalar/Vector/
  Texture parameters se resuelven en runtime (cambio gratis); los **Static Switch Parameters se
  resuelven en COMPILACIÓN** y multiplican permutaciones: 1 switch=2, 4=16, 8=256, 12=4096,
  16=65536 — y eso ×cada vertex factory ×cada quality level que se cocine.
  Reglas: usar `Lerp` con un scalar cuando la feature es barata; reservar static switches para
  features caras de verdad (triplanar, POM, vertex-blending multicapa); **presupuestar un techo
  (~6)** y tratar el séptimo como decisión que se justifica; NUNCA añadir un switch para resolver
  un problema de un solo asset — para eso sirve un segundo master (más barato que duplicar todas
  las permutaciones). "Just add a switch" son las 4 palabras más caras de una revisión de materiales.
- **Jerarquía de instances** (casi nadie la usa; es la diferencia entre cambiar un valor
  proyecto-wide 1 vez o 400): `M_Surface_Opaque` → `MI_Surface_Base` (defaults del proyecto) →
  `MI_Concrete_Base` → `MI_Concrete_Clean` / `MI_Concrete_Cracked`. Regla: **una hoja solo
  sobreescribe lo que la hace diferente**; si sobreescribe "por si acaso", se sale de la
  jerarquía y se pierde el beneficio.
- **Diseño del set de parámetros:** nombrar por INTENCIÓN no por implementación
  (`Roughness_Min/Max` le gana a `MulValue_03`); poner **Group y Sort Priority** en cada nodo
  de parámetro (40 parámetros sin agrupar son inutilizables; agrupados en Base/Detail/Wear/
  Emissive son agradables — 5 minutos de trabajo que se paga a diario); defaults sensatos +
  **SliderMin/SliderMax** ("un slider de roughness que llega a 100 es un bug report esperando
  a ocurrir"); **exponer un color tint aunque creas que no lo vas a necesitar — lo vas a necesitar**.
- **ORM packing:** AO→R, Roughness→G, Metallic→B en una sola textura RGBA. Un sample en vez de
  tres (memoria + sample count). El proyecto NO usa ORM hoy (trae rough y ao por separado) —
  se podría empaquetar, pero con 12 materiales no es el cuello de botella. **NO hacer ahora.**
- **Configuración de import por mapa** (la que decide si se ve real o "washed-out"):
  | Mapa | sRGB | Compression |
  |---|---|---|
  | BaseColor | ✅ checked | Default (DXT1/5) |
  | Normal | ❌ unchecked | **Normalmap (BC5)** |
  | ORM / masks | ❌ unchecked | **Masks (no sRGB)** |
  | Height | ❌ unchecked | Grayscale (high precision, 16-bit) |
  **"Solo BaseColor es sRGB; todo lo demás es DATA, no color."** Importar Roughness/Metallic/
  Normal como sRGB es la causa #1 de materiales lavados e incorrectos: Unreal aplica una curva
  gamma a las texturas sRGB — el color la quiere, un valor de roughness 0.5 NO (gamma-curvarlo
  da la microsuperficie equivocada). Diagnóstico visual: abrir la textura ORM/mask — si se ve
  teñida/de colores o "brillante", sRGB sigue puesto. Banding en roughness = Compression en
  Default en vez de Masks.
- **MIDs (Dynamic Material Instance) en runtime:** crear UNA vez y cachear la referencia
  (`Create Dynamic Material Instance` asigna memoria; llamarlo cada frame o dentro de un Tick
  es un bug de churn que se perfila como "picos misteriosos de GC"). Preferir
  `Set Scalar Parameter Value` sobre un MID cacheado antes que **swapear el material** (swap
  rompe batching y fuerza PSO nuevo). Alternativas más baratas, en orden: per-instance custom
  data en ISM (casi gratis, escala a miles) → vertex colors bakeadas → **Material Parameter
  Collection** si el valor es global ("qué tan mojado está el mundo" = 1 MPC, NO 100 MIDs).
  MIDs en personajes está bien (decenas); MIDs en cada prop disperso de un open world = error
  de diseño.
- **Auditar sprawl heredado** (orden que funciona): contar Materials (filtrar Material, NO
  Material Instance) → hallar duplicados (grafos casi idénticos que difieren en una textura o
  constante = candidatos a instance) → elegir los 3-8 supervivientes que cubran la unión de
  features → convertir de abajo hacia arriba, una categoría a la vez (props primero, menor
  riesgo) usando **Replace References** para que las colocaciones existentes se re-targeteen →
  **RE-MEDIR** (shader compile time, PSO count, package size; **si no se movieron, convertiste
  lo equivocado**) → recién entonces mirar instruction counts (`stat gpu` + el readout del
  Material Editor).
- **Cuándo romper las reglas:** hero assets (el arma del jugador, el landmark donde la cámara
  se queda); lighting models genuinamente distintos (piel, pelo, ojos, tela, capas Substrate);
  post-process materials (otro dominio); **prototipado** (duplicar libre mientras se descubre
  qué necesita el material, consolidar ANTES de que se propague — el costo del sprawl es
  proporcional al tiempo que se le dejó crecer).
