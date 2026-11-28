---
name: creative-apps-mcp-bridges
description: Tender y diagnosticar puentes MCP entre el arnés tlamati (WSL) y apps creativas de Windows (Unreal Engine, Blender, y futuras). Protocolo de diagnóstico cuando un endpoint MCP no responde, trampas medidas del arnés WSL/Windows, y recetas verificadas por app. Cargar SIEMPRE antes de intentar conectar el agente a cualquier app creativa — y revisar también la memoria durable, porque ahí viven las trampas más recientes.
---

# Puentes MCP a apps creativas (tlamati ⇄ Windows)

**Regla no negociable (pedido explícito del fundador, 26-nov-2026):** antes de tender
CUALQUIER puente a una app creativa, (1) cargar esta skill y (2) `search_memory` con el
nombre de la app. Las trampas se pagan una sola vez; el valor de este proyecto está en
que queden registradas. Si pagas una trampa nueva, **escríbela aquí en el mismo turno**.

Cada app se conecta distinto. Lo que NO cambia es el método de diagnóstico (§1) ni las
trampas del arnés (§2), que son transversales.

---

## 1. Protocolo de diagnóstico: "el MCP no responde" (http_code=000)

`000` significa **sin respuesta**, no "respuesta mala". Nunca asumir la causa obvia.
Orden de verificación (barato → caro):

1. **¿El proceso está vivo?** `tasklist.exe | grep -i <app>`. Si no → arrancarla.
   OJO: "editor cerrado" NO es la única causa posible (ver caso Unreal abajo).
2. **¿Hay listener en el puerto?** `NETSTAT.EXE -ano | grep ':<puerto>'`.
   Sin listener aunque el proceso viva ⇒ **el servidor no arrancó**, aunque el plugin
   esté cargado. Buscar en la fuente/binario el flag de auto-arranque y su DEFAULT.
3. **¿La doc que tengo es de ESTA versión?** Este fue el bug real en Unreal: la doc
   guardada era de 5.9 y decía "auto-start on by default"; la 5.8.4 instalada tiene
   `bAutoStartServer = false`. **Leer la fuente del plugin, no la doc descargada.**
   Las apps closed-source traen `.uplugin`/`.ini`/`.h` legibles aunque no traigan el `.cpp`.
4. **¿El plugin/módulo está MONTADO?** En Unreal: `grep -i "<Plugin>" Saved/Logs/*.log`.
   Cero menciones ⇒ no está en el `.uproject` ⇒ no se montó, por más que exista en disco.
5. **¿Están las dependencias del servidor?** Un servidor MCP suele necesitar un registro de
   herramientas aparte (en Unreal: `ToolsetRegistry` + `AllToolsets`, ambos default false).
   Sin ellas el servidor arranca pero "conecta y no hace nada útil".
6. Solo entonces, probar el handshake (§3).

**Anti-patrón que costó 2 sesiones:** reportar "no respondió, medido con el editor cerrado"
y dar por cerrado el hallazgo. Medir con el editor ABIERTO no bastaba: la causa era un
default en la fuente. Veredictos de nivel **EJECUTADO / FUENTE / NO PROBADO** siempre.

---

## 2. Trampas del arnés tlamati en WSL⇄Windows (transversales, medidas)

| # | Trampa | Síntoma | Workaround |
|---|---|---|---|
| 1 | El tool `terminal` traduce rutas `C:\...` literales dentro del comando | `C:\x` aparece como `~/mnt/c/x` y Windows no lo encuentra | Usar `%SystemDrive%` en vez de `C:` literal |
| 2 | `/mnt/c` montado 9p **read-only** | `touch` en disco Windows → Read-only file system | `.bat` en ext4 que hace `copy /Y "\\wsl.localhost\...\src" "%SystemDrive%\...\dst"`, lanzado con `cmd.exe /c` |
| 3 | `cmd.exe /c start ... <App>.exe` hereda el pipe | la llamada cuelga hasta timeout 120 s aunque la app sí arrancó | lanzar en background: `nohup cmd.exe /c ... &` y verificar con `tasklist` |
| 4 | `/tmp` read-only en la jaula | `curl -o /tmp/x` → exit 23 (write error), parece fallo de red | escribir outputs bajo el proyecto (ext4) |
| 5 | Subprocesos en background mueren al terminar la llamada del tool | corridas largas (Blender, controladores) se cortan en silencio | correr **síncrono**; solo usar `nohup &` para lanzar procesos de Windows |
| 6 | `networkingMode=mirrored` en `.wslconfig` | — | es lo que PERMITE alcanzar `127.0.0.1` de Windows desde WSL. Si un día falla el puente, verificar que siga puesto |
| 7 | UNC no soportado como CWD de cmd | `'\\wsl.localhost\...' CMD.EXE was started with the above path` (aviso, no error) | hacer `cd /d %SystemDrive%` primero dentro del `.bat` |
| 8 | GPU ausente en WSL: `nvidia-smi` → `GPU access blocked by the OS`, no existe `/dev/dxg` | cualquier proceso gráfico en WSL cae a CPU | Unreal NO corre en WSL (vive en Windows); renders de Blender van a **CPU**; el único camino al motor es MCP + UNC |

**Vía de entrega al motor, verificada byte a byte:** Windows lee el ext4 de WSL por UNC
`\\wsl.localhost\Ubuntu\home\usuario\...` (`certutil -hashfile` = `sha256sum` local).
Como `/mnt/c` es ro, **esa es la vía**: el agente exporta a ext4 y la app de Windows lee
por UNC. Nunca escribir en C: para entregar un asset.

---

## 3. Handshake MCP genérico (streamable HTTP)

Tres pasos, en este orden. Saltarse el paso 2 hace que `tools/list` falle o devuelva vacío.

```sh
# 1) initialize → devuelve header Mcp-Session-Id
curl -s -m 20 -X POST http://127.0.0.1:<PUERTO>/<PATH> \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"tlamati","version":"1"}}}' \
  -D headers.txt -o body.txt -w 'CODE=%{http_code}\n'
# 2) OBLIGARIO: notifications/initialized con la sesión (→ 202)
curl -s -X POST ... -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
# 3) tools/list con la sesión
curl -s -X POST ... -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

`Accept` DEBE incluir `text/event-stream` además de `application/json`.
Guardar el SID en un archivo: reutilizarlo evita re-handshakear en cada tool call.

**Si `tools/list` devuelve pocas tools (3-5):** el servidor usa *tool search* / meta-tools.
No es un fallo: hay que `list_toolsets` → `describe_toolset` → `call_tool` con
`toolset_name` + `tool_name`. Los nombres reales de las tools viven dentro de los toolsets.

---

## 4. Recetas verificadas por app

### Unreal Engine (5.8.4, MCP oficial de Epic) — VERIFICADO 26-nov-2026
- Endpoint: `http://127.0.0.1:8000/mcp`. Plugin `ModelContextProtocol` (Experimental).
- **Enable**: en el `.uproject`, `ModelContextProtocol` + `ToolsetRegistry` + `AllToolsets`
  (los tres `EnabledByDefault: false` en 5.8.4).
- **Arrancar el servidor**: flag `-ModelContextProtocolStartServer -ModelContextProtocolPort=8000`
  (garantizado, gana sobre config) **o** `bAutoStartServer=True` en
  `Config/DefaultEditorPerProjectUserSettings.ini` bajo
  `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]`.
  Sin una de las dos → plugin montado, toolsets registrados, **puerto cerrado**.
- Arranque desde WSL: `.tmp/win_launch_editor.bat` del proyecto.
- 53 toolsets, 3 meta-tools. Tools que importan para el pipeline de arquitectura:
  - `editor_toolset.toolsets.static_mesh.StaticMeshTools.import_file`
    (`folder_path`, `asset_name`, `source_file` — **acepta UNC**, `import_materials`,
    `combine_meshes`). Es EL eslabón de entrega del FBX.
  - `editor_toolset.toolsets.asset.AssetTools.save_assets` (`[]` = todos los dirty).
    El import crea en MEMORIA: sin save no hay `.uasset` en disco.
  - `editor_toolset.toolsets.scene.SceneTools`: `add_to_scene_from_asset`
    (`asset_path`,`name`,`xform`), `find_actors`, `get_current_level`, `load_level`,
    `trace_world`, `remove_from_scene`.
  - `editor_toolset.toolsets.actor.ActorTools`: `set_actor_transform`,
    `get_actor_transform`, `get_actor_bounds`, `set_label`, `add_component`.
  - `EditorToolset.EditorAppToolset`: cvars, cámara de viewport, **control de PIE**.
  - `editor_toolset.toolsets.material.MaterialTools`, `texture.TextureTools`,
    `object.ObjectTools` (list/get/set properties — los nombres NO se adivinan).
- Trampa de verificación: el import reporta éxito en el JSON pero los assets solo existen
  en memoria. **Confirmar con `ls` en `Content/` del proyecto tras `save_assets`.**
- `find_actors` declara `name`/`tag`/`collision_channels` como **required** aunque el
  schema los pinte opcionales → pasar los tres (o string vacío) o falla el tool call.
  **Llamada que SÍ funciona (medida, sesión 8):**
  `{"name":"","tag":"","collision_channels":[]}` → devuelve los 62 refPaths de Lvl_Casa.
  Se pagaron 3 llamadas fallidas por no leer esto: la tool va pidiendo los params
  **uno por uno** (primero `name`, luego `tag`, luego `collision_channels`), así que
  no se puede descubrir iterando errores — leer `inputSchema.required` de una vez.
- **Nombres de tools que NO se adivinan (medidos, sesión 6):** el nombre visible de un
  actor se lee con `ActorTools.get_label` — **NO existe `get_actor_label`** (devuelve
  `Unknown tool`). `ActorTools` tiene: get/set_label, get/set_actor_transform,
  get_actor_bounds, get_components(actor, component_type), add/remove_component,
  get/set_parent_component, look_at, add/remove/has_tag/get_tags. Si dudas del nombre,
  `describe_toolset` y leer `tools[].name`, no probar a ciegas.
- **Censo de escena barato:** `find_actors` devuelve refPaths de TODOS los actores del
  nivel (92 en Lvl_FirstPerson). NO iterar bounds/label de los 92 (184 llamadas MCP);
  filtrar por substring en el refPath antes (`UAID_`, `PlayerStart`, `Floor`).
- **Assets reales en disco (sesión 6):** los buenos están en `Content/ProyectoUE_Final/`
  (SM_Losa + SM_Muro_00..09 + materiales Losa_Concreto/Muro_Yeso), NO en `Content/ProyectoUE`.
  Quedan 3 carpetas basura de test de escala (Test_vA/vB/vC) y 11 actores fantasma `*_CM`
  con bounds en cero en el nivel. Verificar SIEMPRE con `ls` en Content/ + `get_label`,
  no con el nombre que recuerdas de memoria.
- **ESCALA — trampa grande (costó una sesión entera; mecanismo RE-MEDIDO en sesión 6):**
  Lo único que decide la escala es **hornear el ×100 EN LA MALLA** (`o.scale=(100,100,100)`
  + `transform_apply(scale=True)`) y exportar nativo `global_scale=1.0,
  apply_unit_scale=False`. Verificado dentro de Unreal: losa 1000×800×15, muro 1000×20×260.
  **CORRECCIÓN a la explicación anterior (era una inferencia FALSA):** se había escrito que
  "Unreal normaliza por el `UnitScaleFactor` y `apply_unit_scale=True` escribe USF=100,
  cancelando el ×100". Medido byte a byte en los 8 FBX del proyecto, **el USF del header NO
  diagnostica nada**: `escena_unreal_cmfix.fbx` y `escena_sonda.fbx` (ambos CORRECTOS) y
  las variantes `vA/vB/vC` (las tres MALAS, 100× chicas: 10.0×8×0.15) llevan **TODOS
  `UnitScaleFactor=100.0`**. El único FBX distinto fue `escena_unreal_cm.fbx` con 10000.0.
  Lo que realmente separó bueno de malo fue si la malla estaba horneada ×100.
  → Regla: **NO usar el header del FBX como prueba de escala.** El único juez es
  `ActorTools.get_actor_bounds` (devuelve **cm**) tras colocar el actor. Si el output de tu
  verificación contradice al motor, el bug es tu parser, no los datos.
- **Trampa de parsing de FBX binario (sesión 6):** al leer `UnitScaleFactor`, el marcador
  `'D'` que precede al double cae en `k+43` desde el inicio del nombre — **fuera** de una
  ventana `k+15..k+40`. Con ventana corta el parser valida bytes basura y reporta
  `USF=1.0 → OK` falsamente (pasó en `s6_modelo_a_3d.py`). Buscar el byte `0x44` en
  `range(k+15, k+90)` y desempaquetar `<d` desde `off+1`.
- **`CaptureViewport` (recorrido 1ª persona SIN input WASD) — VERIFICADO sesión 6.** Es la
  forma de *ver* el goalpost: `EditorAppToolset.CaptureViewport(captureTransform={location,
  rotation}, annotations={}, bShowUI=False)`. Con `location.z = 170` (= 1.70 m, altura de
  ojo) dentro de la maqueta captura vistas en primera persona reales. Trampa: **`annotations`
  es required** aunque el schema lo pinte opcional → pasar `{}` (= sin overlay de grid/labels).
  El `returnValue` trae `image{mimeType,data}` (PNG **base64**), `cameraLocation/Rotation/FOV`.
  **El objeto `image` NO trae width/height** → leer dims de la cabecera PNG (bytes 16:24 BE).
- **`set_actor_transform` NO toma location/rotation sueltos**: toma UN param `xform`
  (`{location,rotation,scale}`, ToolsetTransform; campos no-set = "no cambiar").
- **Limpiar actores: la marca semántica puede ir EMBEBIDA** (costó un re-censo, sesión 6).
  Los fantasmas eran `Muro_CM_00..09`, así que `label.endswith('_CM')` solo atrapaba a
  `Losa_CM`. Usar `'_CM' in label`, NO `endswith`. Borrar con `SceneTools.remove_from_scene`
  + `AssetTools.save_assets(asset_paths=[])` (guarda todos los dirty).
- **Pipeline DXF→Unreal completo VERIFICADO de punta a punta (sesión 6, 26-nov-2026):**
  `plano.dxf` → `script interno dxf_a_modelo.py` (ezdxf, en `.tmp/dxvenv`) →
  `s6_modelo.json` → `script interno modelo_a_3d.py` (Blender + `LD_LIBRARY_PATH=.tmp/libs`)
  → `s6_escena_semantica.fbx` → `script interno import_unreal.py` → `/Game/ProyectoUE_S6`.
  Resultado medido: **17/17 static meshes con bounds exactos en cm** (losa 600×400×15,
  muro EXT 615×15×260, cama 150×200×55, vidrio 140×0.6×120) y **28 `.uasset` en disco
  Windows** (`Content/ProyectoUE_S6/`: 17 meshes + 11 materiales PBR reales
  `tablaroca_blanca`, `vidrio_ventana`, `madera_nogal`, `tela_lino`, …).
  Evidencia: `s6_unreal_bounds.json`.
- Detalles del extractor DXF que costaron iteraciones: los huecos pueden estar en capa
  `HUECOS` **además de** `PUERTAS` (consultar ambas o se pierden puertas); los muros
  exteriores crecen **hacia adentro** (el eje del DXF es la cara exterior, no el centro);
  y al proyectar un hueco sobre el muro hay que **ordenar `t0,t1 = sorted([t0,t1])`** o el
  booleano no corta. La cota se lee con `entity.text`, NO con `str(entity)`.
- **Convivencia en el nivel:** los 11 actores `UAID_*` de la sesión 5 siguen vivos en
  `Lvl_FirstPerson`. Al colocar una maqueta nueva usar un offset (`x=+6000` cm) para no
  solaparlos, y una carpeta de contenido nueva (`/Game/ProyectoUE_S6`).
- **Nombres reales del cliente (`el cliente MCP de UE interno`):** la clase es `UE`, **no `UEClient`**.
  `SceneTools` usa `find_actors`, **NO existe `list_actors`**. `AssetTools.find_assets`
  requiere el param `name` (falla sin él). `ActorTools.get_label`, no `get_actor_label`.
- Evidencia completa: en la carpeta de evidencia interna del proyecto.
  `ensamblado_final.json`, `test_escala_variantes.json`, `s6_unreal_bounds.json`.
  Cliente MCP reutilizable en Python:
  `el cliente MCP de UE interno` (handshake de 3 pasos, reusa/renegocia session-id, deserializa SSE).

### Blender (blender-mcp addon) — VERIFICADO sesión 2-3
- Socket **9876**, lectura + escritura confirmadas (`execute_code`).
- **NO abre socket con `bpy.app.background = true`** → necesita display real. No usar
  para headless puro; para headless usar `bpy` directo por CLI.
- El `python3` del sistema no trae ezdxf/Pillow: usar el venv del proyecto.
- Sin `LD_LIBRARY_PATH=<proyecto>/.tmp/libs` Blender no arranca.
- `hasattr()` MIENTE en `bpy.ops`; validar con `in dir()`.

### Apps aún SIN probar (closed-source, usar REA solo si no hay fuente)
Maya, ZBrush, 3ds Max, Cinema 4D, Houdini, SolidWorks, Revit, AutoCAD, Figma.
Para OSS con fuente (Blender, FreeCAD, UPBGE, Godot, Krita): **leer la fuente, no REA**.

---

## 5. Al terminar cualquier sesión de puentes
1. ¿Pagaste una trampa nueva? → añádela a §2 o a la receta de §4 **en el mismo turno**.
2. ¿Cerraste un pendiente? → `memory` (durable) + evidencia con stdout real en el proyecto.
3. Distingue EJECUTADO / FUENTE / NO PROBADO. "El operador no dio error" no es evidencia:
   releer el archivo, medir el volumen, contar píxeles, hacer `ls` en disco.
4. Los hallazgos van **INLINE en el chat**, no solo al archivo (preferencia del fundador).

---

## 6. Trampa NUEVA del arnes (pagada sesion 10, 26-nov-2026): truncamiento del output al escribir codigo

**Sintoma:** `write_file` reporta "wrote N chars to ..." con N MENOR al que pretendias, y el
archivo termina a mitad de un string literal -> `SyntaxError: unterminated string literal`.
Lo enganosos: la tool NO fallo, escribio fielmente lo que el modelo alcanzo a generar. El
corte es el **presupuesto de tokens de salida por turno del modelo**, no un limite de la tool.

**Por que es cara:** se ve como exito (exit 0, mensaje "wrote N chars"), el archivo EXISTE,
y nada lo invalida. Asi se creo un emitente DXF roto que parecia escrito. Si despues el
pipeline "no encuentra el DXF", la tentacion es culpar al pipeline.

**Regla dura:** despues de CUALQUIER `write_file` de un archivo de codigo, verificar en el
mismo turno con las tres comprobaciones baratas:
```sh
python3 -c "compile(open('<ruta>').read(),'<ruta>','exec'); print('SINTAXIS OK')"
tail -3 <ruta>                      # la ultima linea debe ser codigo completo, no a medias
wc -c <ruta>                        # comparar contra lo que la tool reporto
```
Un JSON se verifica con `json.load`, no con `compile`.

**Umbral medido:** archivos de hasta ~4.5 KB salen enteros en una sola llamada. A partir de
~9 KB de codigo se corta. **No escribir scripts >5 KB en una sola `write_file`.**

**Workaround que SI funciono (medido sesion 10):** particar con heredoc por `terminal`, que
no gasta el presupuesto de salida del mismo modo y admite append:
```sh
cat >  parte.py <<'PY'     # primera mitad
PY
cat >> parte.py <<'PY'     # segunda mitad (append)
PY
python3 -c "compile(open('parte.py').read(),'x','exec')"
```
Alternativa: `write_file` con el esqueleto + `edit` para anadir bloques.

**Leccion de diseno (vale para todo el proyecto):** separar la *lectura* (datos) del
*emitente* (codigo). La lectura de vision va a un JSON pequeno y re-obtenible; el emitente
es generico y se escribe una sola vez. Asi un truncamiento rompe el emitente, nunca los datos.

## 7. Trampas nuevas (pagadas sesion 12, 27-nov-2026)

**7.1 Meta-tools de MCP NO van por el wrapper `call_tool`.** En el MCP oficial de Unreal,
`list_toolsets` y `describe_toolset` son tools de PRIMER NIVEL: se invocan con
`params.name = "describe_toolset"`. Si un cliente reutilizable envuelve todo en
`{"name":"call_tool","arguments":{"toolset_name":…,"tool_name":…}}` (patron correcto para las
tools normales), el server interpreta `ToolsetRegistry` como toolset y responde
`tool error: Toolset 'X' not found`. Pagado 8 veces en una corrida. Forma buena:
```python
def describe(ue, ts):
    txt = ue._post({"jsonrpc":"2.0","id":1,"method":"tools/call",
        "params":{"name":"describe_toolset","arguments":{"toolset_name": ts}}})
    return "".join(c.get("text","") for c in txt.get("result",{}).get("content",[])
                   if c.get("type")=="text")
```
Regla: si una tool es de DESCUBRIMIENTO (lista otras tools), sospechar que es meta-tool. Verificar
con `tools/list` antes de asumir el wrapper.

**7.2 El nombre visible de un objeto NO suele venir en su identificador.** `SceneTools.find_actors`
devuelve `refPath` (`/Game/…Lvl_Casa.Lvl_Casa:PersistentLevel.WorldSettings_1`), que NUNCA contiene
el label. Buscar substring del nombre amigable en el refPath da 0 coincidencias y hace concluir
"los actores no existen" (falso negativo caro). Hay que iterar `ActorTools.get_label` con
`actor={"refPath": …}`. Equivalente en otros puentes: id interno != display name.

**7.3 `/` y `/tmp` son read-only en la jaula del tool terminal.** `cat > /tmp_x.py` falla con
`Read-only file system`. Escribir SIEMPRE bajo el directorio del proyecto. (Variante de la trampa
`curl -o /tmp` ya documentada.) Nota: `python3 - <<'EOF'` SI funciona (el heredoc va a stdin, no
escribe archivo), y `/bin/sh` no soporta process substitution `<( )` -> `diff a b > out`.

**7.4 CORRECCION al umbral de §6: `write_file` escribio 15.5 KB de Markdown de una sola vez,
integro** (verificado con `wc -c` + `tail -4` + grep de las 9 secciones). El corte de §6 es el
presupuesto de salida del modelo por turno, no un limite de tamano de la tool: depende de cuanto
mas se genere en el mismo turno. La regla sigue siendo **verificar siempre** (compile/tail/wc),
pero no hace falta particionar de entrada un documento de 15 KB.

**7.5 Artefactos con timestamps embebidos NO tienen sha256 reproducible.** Un DXF de ezdxf cambia
12 lineas entre corridas (fecha juliana x2, GUIDs de bloque, string de version) y un FBX de Blender
cambia el sha aunque pese EXACTAMENTE lo mismo (177756 b ambas veces). Comparar corridas por
**hojas semanticas**, no por sha:
```python
def hojas(x, p=''):
    d = {}
    if isinstance(x, dict):
        for k, v in x.items(): d.update(hojas(v, f'{p}.{k}'))
    elif isinstance(x, list):
        for i, v in enumerate(x): d.update(hojas(v, f'{p}[{i}]'))
    else: d[p] = x
    return d
# diff de dos: [k for k in set(a)|set(b) if a.get(k)!=b.get(k)]
```
Medido: 1795/1796 hojas iguales en el modelo y 622/622 en el registro de escena => flujo
determinista, aunque los sha digan lo contrario. Regla R4 compatible: afirmar reproducibilidad
por geometria, y declarar el sha como NO reproducible en vez de fingir que calza.

## 8. Trampas de parseo de MCP (sesion 12, transversales a cualquier puente Unreal/otro)

Estas son del PROPIO protocolo/plugin, no del proyecto: se repiten en cualquier app con el MCP
oficial. Todas pagadas y corregidas en el proyecto real (sesión 12).

**8.1 Los retornos NO tienen forma uniforme: hay que desanidar por tipo, no asumir.**
```python
rv = resp.get("returnValue", resp)
if isinstance(rv, str):                     # ObjectTools.list_properties/get_properties
    rv = json.loads(rv)                     #   -> STRING con JSON dentro (doble parse)
if isinstance(rv, list) and rv and isinstance(rv[0], dict) and "refPath" in rv[0]:
    rv = rv[0]["refPath"]                   # TextureTools.import_file -> LISTA [{refPath}]
elif isinstance(rv, dict) and "refPath" in rv:
    rv = rv["refPath"]                      # StaticMeshTools/MaterialTools -> dict
```
Regla: escribir un helper `_ref(resp)` y usarlo SIEMPRE. Guardar el `returnValue` crudo en un dict
propio produce referencias basura del estilo `[{'refPath': '/Game/...'}]` que revientan dos pasos
despues con un error confuso.

**8.2 Los assets creados por MCP viven EN MEMORIA del editor aunque no esten en disco.** `ls` de la
carpeta Content/ puede dar VACIO mientras `AssetTools.exists` devuelve `true` y `get_properties` lee
el asset sin problema. Tres consecuencias: (a) `save_assets([...])` explicito o se pierde todo al
cerrar el editor; (b) un `ls` no es prueba de nada — la fuente de verdad es `exists`; (c) los
residuos de un piloto se limpian con `AssetTools.delete(path=...)`.

**8.3 Params "opcionales" que el schema exige igual.** Medido: `MaterialTools.list_expression_classes`
requiere `search` (pasar `""`); `MaterialTools.add_expression` requiere `x`/`y` como **float**
(`0.0`, no `0`); `AssetTools.save_assets` requiere `asset_paths` (`[]` = guardar todo);
`EditorAppToolset.CaptureViewport` requiere `annotations` (`{}` = sin overlay). Patron: ante
"Required fields are missing: X", pasar el valor neutro, no insistir en que es opcional.

**8.4 Los nombres de propiedades/clases se DESCUBREN, no se adivinan.** Flujo que funciono a la
primera: `list_properties(instance={"refPath": obj})` para leer las props de un nodo/asset (devuelve
nombre+type+title+description+enum+default), y `list_expression_classes(search="")` para las 354
clases de nodo de material (como dicts `{"refPath": "/Script/Engine.MaterialExpression..."}`).
Ejemplo de ganancia real: el nodo `MaterialExpressionTextureSampleParameter2D` tiene 16 props y las
utiles son `texture`, `samplerSource`, `samplerType`, `constCoordinate`, `constMipValue` — ninguna
se adivina.

**8.5 El motor auto-configura por convencion de nombres.** Unreal detecto el normal map y puso
`compressionSettings=TC_Normalmap` con `sRGB=false` SOLO porque el archivo se llamaba `*_nor_gl_2k.jpg`.
Antes de forzar propiedades por `set_properties`, medir el estado actual con `get_properties`: a
veces el trabajo ya esta hecho y forzarlo lo rompe.

**8.6 Scripts que tocan el motor DEBEN ser idempotentes.** Un piloto que falla a mitad deja assets
creados; al re-correr, `import_file`/`create_material` revientan con "asset with that name already
exists". Patron: `if ue.call(ASSET,"exists",path=ruta): reutilizar` antes de crear. Se pago 2 veces.

## 9. Trampas pagadas sesion 13 (27-nov-2026): idempotencia de assets a medias y UAT

**T16 — `MaterialTools.add_expression` NO toma `material`:** el param se llama
`material_or_function` (y `recompile` igual). Con `material=` el server responde
"input param material_or_function is required". Medido contra el schema vivo.

**T17 — `SceneTools.find_actors` exige TRES params:** `name`, `tag` Y
`collision_channels` (lista, puede ir vacia). Con solo name/tag:
"input param collision_channels is required". Y devuelve refPaths con nombre interno
`StaticMeshActor_UAID_*`: para buscar por label hay que iterar `ActorTools.get_label`.

**T18 — `AssetTools.delete` toma `path` (singular),** no `asset_paths` (ese es de
`save_assets`). Medido con describe_toolset.

**T19 — `ActorTools.get_components(actor, component_type="StaticMeshComponent")` NO
sirve:** el server exige un OBJECT PATH en component_type ("is not a valid object path").
Para colision per-poly el patron que SI funciona (u4, probado en 58 meshes) es sobre el
ASSET: `ObjectTools.get_properties(instance=mesh, properties=["bodySetup"])` ->
`set_properties(bodySetup, {"collisionTraceFlag":"CTF_UseComplexAsSimple"})`.

**T20 — Idempotencia de assets creados A MEDIAS (la cara de esta sesion):** si una
corrida trona DESPUES de `create_material` pero ANTES de poblarlo, el asset queda
existente y VACIO. `AssetTools.exists()` dice True y el guion lo "reutiliza" sin
cablear -> el mesh sale sin color y el log dice OK. Regla: reutilizar solo si esta
CABLEADO (verificar con `MaterialTools.get_property_input` por cada salida que se
pide); si existe y no lo esta, `AssetTools.delete` y reconstruir. Medido:
M_Cielo_Raso existia con get_expressions()==[] tras una corrida fallida.

**T21 — `list_expression_classes` devuelve refPaths `/Script/Engine.MaterialExpressionXxx`**
(el nombre va tras el PUNTO, no tras una barra) y envueltos en un STRING con JSON dentro.
Matchear con `endswith("MaterialExpression"+nombre)` tras parsear el string anidado;
un `rsplit("/")` da falso negativo silencioso.

**T22 — `SceneTools.trace_world(start, end)` devuelve la DISTANCIA al primer impacto**
(numero) o null si el rayo no pega en nada. Es la prueba FISICA de geometria sin
render: un rayo vertical desde z=170 en cada recinto debe impactar a la altura del
techo; fuera del footprint debe dar null (= ve cielo). No depende de luces ni colores.

**T23 — UAT trata el proyecto como code-based si el .uproject tiene plugins con codigo
(ModelContextProtocol/ToolsetRegistry/AllToolsets):** sin carpeta Source/ el cook
revienta en 3 s con `DirectoryNotFoundException ... Binaries\Win64\<Proyecto>Editor.target`
(TargetReceipt). El cook exitoso previo usaba un .uproject con `"Plugins": []` (el log
lo imprimia). Patron verificado: el .bat hace backup del .uproject, copia el
simplificado (Plugins:[]), cocina, y RESTAURA el original al final (el editor vivo
necesita el MCP). El editor con MCP abierto NO impide el cook.

**T24 — `cmd.exe /c \\wsl.localhost\...bat` avisa "UNC paths are not supported,
defaulting to Windows directory":** el .bat corre igual pero con CWD cambiado; usar
SOLO rutas absolutas (%SystemDrive%, %ProgramFiles%) dentro del .bat, nunca relativas.

## 10. Trampas de DIAGNOSTICO del build empaquetado (sesion 13, transversales a cualquier Unreal cook)

Estas no rompen el trabajo: hacen que se diagnostique MAL trabajo que esta bien, y por tanto que se
rehaga lo que no hacia falta. Las tres se pagaron en la misma tarde con el mismo exe.

**T25 — El exe reusa el mismo nombre de log entre corridas y el de una corrida ANTERIOR se queda
horas en `Saved/Logs/`:** un `MiProyectoUE.log` de las 16:10 que decia
`LoadMap: /Game/ProyectoUE/Lvl_Casa` (mapa viejo) hizo concluir que el cook de las 22:25 no habia
tomado el `GameDefaultMap`. El exe de las 22:25 SI lo tomaba; simplemente ese log no era suyo.
Regla: arrancar SIEMPRE con `-log -windowed -abslog="<ruta unica>"`, borrar el log anterior PRIMERO
(`rm -f`) y comprobar el mtime del log ANTES de leerlo. Runner de referencia reutilizable:
`un script interno de diagnóstico` (rm + nohup cmd.exe por UNC + sleep 90 +
grep `LoadMap|FindPlayerStart|Error:|Fatal` + `taskkill`).

**T26 — Auditar el contenido de un build con `strings *.pak` da FALSOS NEGATIVOS:** el `.pak` esta
comprimido y devuelve 0 rutas `/Game/`. El indice legible es el `.utoc` hermano (o el `.ucas`, que
es el contenedor de datos IoStore). Comando correcto:
`strings .../Paks/<Proyecto>-Windows.utoc | grep -c <Carpeta>` y
`strings .../Paks/<Proyecto>-Windows.utoc | grep -oE "SM_[A-Za-z0-9_]+" | sort -u | wc -l`.

**T27 — En World Partition el `.umap` NO es la prueba de que el nivel se guardo.** Los actores viven
en `Content/__ExternalActors__/<Carpeta>/<Nivel>/` como `.uasset` individuales; el `.umap` pesa ~15 KB
y su mtime casi no cambia POR DISENO. Un script que compare mtimes del `.umap` reportara
"UMAP_SIGUE_VIEJO" con los 59 actores ya escritos en disco. Regla: medir
`find Content/__ExternalActors__/<Nivel> -name '*.uasset' | wc -l` y su mtime, o usar
`AssetTools.is_dirty(path)`. La firma real de UE es
`save_dirty_packages(save_map_packages, save_content_packages)` — el PRIMER True ya pide mapas; no
asumir de memoria que `save_assets([])` "excluye mapas" (leer la fuente del plugin:
`EditorToolset/Content/Python/editor_toolset/toolsets/asset.py`).

**T28 — `FindPlayerStart: PATHS NOT DEFINED or NO PLAYERSTART with positive rating` en el log del
exe NO es un fallo del cook ni del GameMode:** es que el nivel no tiene PlayerStart (o el que tiene
esta fuera de la geometria). Sintoma visible: el juego arranca, la pantalla se mueve y el jugador
cae al vacio indefinidamente. Al duplicar un nivel por `AssetTools.duplicate` los external actors NO
se copian, asi que el nivel nuevo nace SIN PlayerStart aunque el original lo tuviera. Fix:
`SceneTools.add_to_scene_from_class(actor_type={"refPath": "/Script/Engine.PlayerStart"}, name=...,
xform=...)` con coordenadas DERIVADAS de los bounds medidos del piso (no el origen del mundo, que en
modelos importados suele ser una esquina), `save_assets([])` y RE-COCINAR. Patron idempotente en
`un script interno fix_playerstart.py`.

**T29 — `find` sobre `/mnt/c/Program Files/Epic Games/UE_5.8/Engine` agota el timeout de 120 s del
tool terminal** (9p read-only, cientos de miles de archivos; dos veces en una sesion). Acotar con
`-maxdepth`, con `| head`, o buscar directamente la ruta conocida del plugin
(`Engine/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/*.py`).

## 11. Firmas MCP autoritativas y rutas del proyecto (medido 27-nov-2026)

Movido desde la memoria durable el 27-nov-2026 (consolidación): estos son los hechos que una
sesión necesita ANTES de la primera llamada, y viven aquí para no gastar el cap de MEMORY.

**11.1 Nombres de toolset: SIEMPRE calificados.** Con nombre corto (`ObjectTools`, `MaterialTools`)
el server responde `Toolset 'ObjectTools' not found`. La forma correcta es la ruta de módulo:
`editor_toolset.toolsets.object.ObjectTools`, `...material.MaterialTools`,
`...material_instance.MaterialInstanceTools` (**existe** y es el que hace falta para la jerarquía
master→instance; no venía documentado), `...static_mesh.StaticMeshTools`,
`...texture.TextureTools`, `...asset.AssetTools`, `...scene.SceneTools`, `...actor.ActorTools`.
`list_toolsets` devolvió **60** toolsets esta sesión (antes 26) y **sigue sin ser autoritativo** —
la fuente de verdad es `describe_toolset` y, en última instancia, la fuente del plugin en
`Engine/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/*.py`.

**11.2 Nombres de params que NO se adivinan (pagados):**
| Tool | Param correcto | NO usar |
|---|---|---|
| `ObjectTools.get/set/list_properties` | `instance={"refPath": "..."}`; **`set_properties` además exige `values` y su firma es `values: str` → hay que pasar `values=json.dumps({...})`** mientras `get_properties` usa `properties=[...]`. Pasar un **dict** en `values` devuelve `returnValue=false` y NO cambia nada, **sin lanzar error** (fallo silencioso: siempre assertear el `True`) | `ref_path`; `values={...}` |
| cualquier tool que reciba un **asset** (textura, material, mesh) | `refPath` en forma **`paquete.objeto`** (`/Game/.../T_x.T_x`); solo el paquete responde `is not a valid object path for property instance` | `/Game/.../T_x` |
| `AssetTools.find_assets` | `folder_path=` **y** `name=` (ambos required); devuelve **lista de strings** (refPaths de paquete), no dicts | `name` solo |
| `AssetTools.get_dependencies` | `asset_path=` | `asset` |
| `AssetTools.exists` | `path=` | — |
| `MaterialTools.get_expressions` | `material_or_function={"refPath": "..."}` | `material` |
| `MaterialTools.add_expression` / `recompile` | `material_or_function=`, `x`/`y` como float | `material=` |
| `AssetTools.duplicate` | `path=` / `new_path=` | `source` / `destination` |
| `AssetTools.delete` | `path=` (singular) | `asset_paths=` (ese es de `save_assets`) |
| `ActorTools.set_actor_transform` | `xform={location,rotation,scale}` | params sueltos |

**NO existe** `MaterialTools.list_expressions` (devuelve "Unknown tool"); el grafo se lee con
`get_expressions` → lista de `{refPath}` cuyo sufijo tras `:` es el tipo de nodo + índice.

**11.3 `get_properties` devuelve `{"returnValue": "<JSON como string>"}` y a veces ya llega como
dict.** Un parse fijo revienta con `TypeError: the JSON object must be str... not dict`. Unwrap
robusto: `while isinstance(rv, str): rv = json.loads(rv)`.

**11.4 El cliente reutilizable `el cliente MCP de UE interno` expone una CLASE:** `ue = UE(); ue.connect()`
— no `mcp_ue.UE.call(...)` a nivel de módulo. Reusa `mcp_sid.txt` y renegocia si caducó.

**11.5 NO existe toolset MCP de empaquetado/cook.** El `.exe` se hace por `UAT BuildCookRun`
lanzado desde Windows (~782 s medidos); el comando literal y el patrón de `.bat` que
backup/restaura el `.uproject` viven en `los docs de handoff internos del proyecto` §4 P6
y en §9 T23 de esta skill.

**11.6 Ruta REAL del proyecto Unreal (con ESPACIO):**
`/mnt/c/Users/TuUsuario/Documents/Unreal Projects/MiProyectoUE/` — `UnrealProjects` (sin
espacio) NO existe. Empaquetado en `.../Unreal Projects/MiProyectoUE_Packaged/Windows/`.

**11.7 Inventario de assets vigente (27-nov-2026):** los buenos viven en
`Content/ProyectoUE_S10/` (143 `.uasset`, 104 MB) = `Tex/` (48 texturas = **11** ids Poly Haven ×
4 mapas diff/nor_gl/rough/ao; `metal_plate_02` NO se importó) + `Mat/` (20 materiales).
Nivel vigente: `/Game/ProyectoUE_S10/Lvl_Casa_S10` (67 external actors en
`Content/__ExternalActors__/ProyectoUE_S10`). BASURA que se puede borrar: `Content/ProyectoUE`,
`ProyectoUE_Final`, `ProyectoUE_S6`, las 3 carpetas `Test_v*_gs*` y el nivel
`Lvl_Casa_S10_v2` (duplicado fallido, 0 external actors).
**NO existe ninguna tool MCP para crear un nivel nuevo** (solo `load_level`/`get_current_level`;
`create_level_instance` es Level Instances): la vía es `AssetTools.duplicate` de un `.umap` +
`save_assets([])` + `load_level`, y luego borrar los actores heredados. OJO: al duplicar, los
external actors NO se copian → el nivel nuevo nace sin PlayerStart (T28).
