# Iluminación, sombras y exposición (Unreal 5.8.4)

Destilado 27-nov-2026. Corpus: `<proyecto>/curriculum/raw/`
(virtual_shadow_maps 43.5K, shadowing 14.4K, hdri_backdrop 12.0K, designing_visuals 8.1K,
add_post_process_volumes, bloom, color_grading).
**[MEDIDO]** = verificado contra el editor vivo por MCP el 27-nov-2026.
**[DOC]** = documentación oficial, sin comprobar aún en el editor.

## 0. El problema concreto de este proyecto (exterior quemado)
- **[MEDIDO s14]** Warning del editor en las capturas: *"Cached lighting in Lumen and
  real-time sky capture lighting is going to be clipped. Adjust
  r.EyeAdaptation.CachedLightingPreExposure"*. El exterior blown-out de las capturas M3-A
  es **exposición**, no geometría.
- **[MEDIDO]** La cvar hoy está en su default. Leída por MCP:
  `r.EyeAdaptation.CachedLightingPreExposure = 4`.
  Help oficial (textual, de SearchCVars): *"Fixed pre-exposure offset in EV units for
  cached lighting... Default 4 maps to ~[-8; 12] of usable exposure range, which should
  mostly cover physically based lighting range without any lighting response clipping.
  **8 maps to ~[-4; 16] of usable exposure range, which fully covers physically based
  lighting range.**"*
  ⇒ candidato a probar en M3-B: subir a **8** y comparar captura antes/después.
- **[MEDIDO]** cvars relacionadas leídas: `r.EyeAdaptationQuality=2` (normal; <=0 off,
  2 default, 3 high), `r.EyeAdaptation.PreExposureOverride=0` (0 = no override),
  `r.EyeAdaptation.MethodOverride=-1` (-1 no override, 1 Auto Histogram, 2 Auto Basic,
  3 Manual).

## 1. Cómo leer y fijar cvars por MCP (recetas verificadas)
Lectura (solo LEE, no escribe) — toolset `EditorToolset.EditorAppToolset`:
```
SearchCVars(name="EyeAdaptation")   # acepta substring; devuelve dict JSON
```
**[MEDIDO]** El returnValue es un **STRING con JSON dentro** → `json.loads` dos veces.
Formato: `{"r.Nombre": {"help": "...", "value": ...}}`. El help es oro: trae rangos y
defaults oficiales sin abrir la doc.

Escritura PERSISTENTE (sin tocar .ini a mano) — toolset
`ConfigSettingsToolset.ConfigSettingsToolset`:
```
ListContainers()                                     -> ["Editor","InputBinding","Project"]
ListCategories(containerName="Project")              -> [Editor, Engine, Game, Platforms, Plugins, Project]
ListSections(containerName="Project", categoryName="Engine")
   -> 48 secciones; relevantes: "Console", "DataDrivenConsoleVariableSettings",
      "Rendering", "Rendering Overrides"
GetSectionSchema(containerName="Project", categoryName="Engine",
                 sectionName="DataDrivenConsoleVariableSettings")
```
**[MEDIDO]** Schema de cvars persistentes: objeto con clave `cVarsArray`, array de
`{type: "CVarFloat"|"CVarInt"|"CVarBool", name, toolTip, defaultValueFloat,
defaultValueInt, defaultValueBool}` — los **6 campos son required** (rellenar los que no
aplican con 0/false). Se escribe con `SetSectionProperties(containerName, categoryName,
sectionName, propertiesJson)` y se persiste con `SaveSection(...)`.
**NO VERIFICADO aún**: el round-trip completo de Set+Save. Hacerlo en M3-B con respaldo
previo del DefaultEngine.ini.

Batch de llamadas (ahorra tokens y round-trips) — **[MEDIDO]**
`editor_toolset.toolsets.programmatic.ProgrammaticToolset`:
- `get_execution_environment()` → leer su campo `instructions` ANTES de escribir script.
- `execute_tool_script(script=...)` → el script debe definir `run()` que devuelve dict;
  dentro se usa `execute_tool("Toolset.Tool", json.dumps({...}))` que devuelve dict-like y
  **lanza RuntimeError en fallo** (no hay que validar errores a mano).
- Módulos importables permitidos: **json, datetime, time, copy, math, re** (nada más).
- OJO: los schemas publicados describen solo los INPUTS; para parsear retornos, llamar
  antes `describe_toolset` o haber visto ya el returnValue.

## 2. Sombras: qué método y cuándo [DOC]
| Método | Cuándo | Notas |
|---|---|---|
| Shadow Maps (convencional) | plataformas sin VSM; todo lo que soporte dynamic shadowing | Requiere configurar distancias a mano, culla solo por componente → **mal rendimiento con escenas de muchos polígonos**. **No soporta Nanite**. Usa Shadow Biasing (artefactos de self-shadow/faceting) y Shadow Resolution Scale. |
| Virtual Shadow Maps | default moderno con Nanite + Lumen | **No usa cascadas** ni las propiedades de biasing. Resolución alta y consistente. |
| Distance Field Shadows | sombras suaves de área con luz Movable | Las usa **Lumen Software Ray Tracing**. Penumbra controlada por Source Angle / Radius / Size, igual que HW RT y VSM. |
| MegaLights | muchas luces que proyectan sombra a costo bajo y consistente | Las luces MegaLights se sombrean por RT o VSM según su `MegaLights Shadow Method`. |
- **[DOC]** Cascaded Shadow Maps solo aplican con Shadow Map Method = "Shadow Maps"; con
  VSM la Directional Light no renderiza cascadas. Far Shadow Cascades para objetos más
  allá de la distancia máxima (hay que activar Far Shadow por asset).
- **[DOC]** Rendimiento: fijar **Attenuation Radius** en Point/Spot/Rect lights (no es
  físicamente exacto pero acota cuántos objetos se somborean); desactivar **Cast Shadows**
  en luces dinámicas cuyas sombras aporten poco.

## 3. Exposición / Eye Adaptation [DOC]
- Exposure = "Eye Adaptation": controla límites superior/inferior de brillo. **No cambia la
  luz**, cambia cuánto de ella se ve (como el diafragma o la pupila).
- Valores del tutorial oficial (Post Process Volume): `MIN EV100 = -10`, `MAX EV100 = 20`
  para el volumen global; un volumen acotado a una habitación oscura usa `MIN EV100 = -1.0`.
- Transición suave entre volúmenes: **Blend Radius = 1500** (sin él el cambio de exposure
  al entrar a otra sala es brusco).
- **No usar Gain para exponer la escena.** Gain es para ajuste fino de color. Para exposure
  usar **Exposure Bias** en Lens > Auto-Exposure.
- Emissives físicamente correctos: al subir la potencia el color se aclara; si satura el
  film/sensor, **se vuelve blanco** (tonemapper filmic).

## 4. Bloom y lens flare [DOC]
- Bloom = sangrado de luz más allá del borde de la fuente. Punto de partida del tutorial:
  Lens > Bloom, `Intensity = 0.8`, `Threshold = 1`.
- `Threshold` = valor mínimo a partir del cual el bloom actúa (es un clamp).
  **Threshold = -1 hace que TODO el nivel afecte al bloom** (ruido, evitar).
- Bloom aparece ya cuando un material emissive tiene Brightness > 1.

## 5. HDRI Backdrop (iluminar con una foto 360) [DOC]
- **[DOC]** Z del Projection Center ≈ **90 cm** (altura típica de trípode al capturar el HDR).
  X/Y normalmente no se tocan.
- `Lighting Distance Factor` ≈ **0.5** (o algo más) para que sombras/AO propias casen con el
  backdrop. Muy alto → aparece una línea horizontal; 0 si no se necesita componer sombras.
- **Trampa**: al añadir el HDRI Backdrop se crea una **Sky Light dinámica como subcomponente**.
  Si ya había una Sky Light normal, **borrarla** — varias Sky Lights degradan rendimiento y calidad.
- Menos estiramiento: colocar la cámara cerca del origen de la proyección y mirando alrededor.
- `Use Camera Projection` desactiva el ground tracking y hace que la imagen siga a la cámara.
