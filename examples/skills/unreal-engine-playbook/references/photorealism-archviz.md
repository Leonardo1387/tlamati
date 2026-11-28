# Fotorrealismo para arkviz en UE5 — [DOC curso-realismo-arq]

Fuente: `curriculum/raw/curso_realismo_arquitectonico_limpio.txt` (12 caps, ~26 min; arquviz
profesional: casa modelada en 3ds Max, exportada con Datasmith, animación fotorrealista en UE5).
Citas `[MM:SS]` = timestamp. Nada [MEDIDO] en nuestro entorno todavía.
Se descartó el contenido promocional del autor (sus cursos y membresías): no es conocimiento.
**Este es el curso más relevante para M3 (estética) de proyecto-archviz**: el juicio del
fundador "casa de 1997" es exactamente el problema que este curso ataca.

## 1. La tesis central: los 3 pilares
- [03:43] Modelo + iluminación realista + materiales realistas. Solo cuando los TRES se combinan de
  forma realista la imagen/animación resulta convincente y estéticamente agradable [03:57].
- [01:33] **El modelo es la base y es lo que más se subestima.** Textual: "si traes un modelo malo
  de SketchUp o de Revit a UE5, UE5 solo va a estar puliendo tu porquería" [01:56]. Ningún motor
  arregla un modelo pobre [01:48].
- [22:58]-[23:14] Conclusión del autor tras el proyecto: **UE5 no es el eslabón débil**; el límite
  fue su tiempo y su aprendizaje. "Nunca encontré una limitación de UE5" [23:30].
- [23:38] Realidad del "tiempo real": NO existe software que renderice 30 s de video en 30 s. En el
  viewport sí hay feedback en tiempo real, pero para anti-aliasing más nítido, mayor resolución y
  mejores ajustes hay que **producir y mandar a render** [23:53].
- Costo real medido por el autor [24:08]: ~**8 horas de render** para ~**18 clips** de cámara, de
  **500 a 1000 frames** cada uno. "Antes eso eran semanas en una sola máquina" [24:32].

## 2. Los 3 principios del fotorrealismo (marco reutilizable)
[06:31] El autor lo reduce a tres cosas, y dice que **aplican a TODOS los renderings y animaciones**:
**DETALLE, VARIACIÓN e IMPERFECCIÓN** [06:41].

### 2.1 Detalle [06:49]
- Dos herramientas clave de UE5 [06:57]: el **foliage painting** integrado y los **assets de
  Megascans** (que también están esencialmente integrados).
- Qué usó: árboles de Megascans (fotogrametría, **ajustables con controles de viento y estación**),
  twigs, rocks & pebbles, y **decals** [07:12].
- Orden de construcción, **de abajo hacia arriba** [07:46]:
  1. Material de tierra (dirt) con Megascans.
  2. Debris y underbrush (restos y maleza).
  3. Arbustos y shrubs más grandes.
  4. Canopy del bosque con los árboles más altos.
- REGLA DE EFICIENCIA [07:53]: **concentrarse solo en el área donde va a haber cámaras**, "si no
  vas a estar esparciendo rocas y ramitas para siempre".
- Método mental [08:07]: pensar y referenciar cómo se vería ESE bosque en la vida real; las
  herramientas de UE5 hacen fácil la ejecución.
- [12:54] "Las limitaciones hasta aquí son claramente mías y no del software."

### 2.2 Variación [08:39]
- Base: **rotaciones y transformaciones aleatorias** de árboles y assets [08:39].
- Nivel siguiente = materiales. Herramienta: **Easy Mapper** (Fab Marketplace, de **William
  Faucher**) [08:57]. Lo que aporta:
  - Está **optimizado para Nanite tessellation y displacement** → muchísimo detalle vía un simple
    displacement map sin castigar la escena [09:13]. Ejemplo visible: displacement en la roca [09:20].
  - Permite **mezclar varios materiales**: el autor usó **3 tipos de grava** y **vertex painting**
    para dictar dónde aparece cada una [09:28]. "Forma rápida y perfecta de añadir variación para
    que la textura no se vea tiled y monótona" [09:37].
  - Trae una **capa de charcos (puddle layer)** que también se pinta con vertex painting [09:45].
  - Nota honesta del autor [09:53]: todo esto se puede lograr SIN el plugin, pero el plugin lo hace
    muchísimo más fácil.
- (Cruce con lo MEDIDO en nuestro proyecto: nuestros 15 materiales comparten el mismo grafo de 9
  nodos con 2 ScalarParameter de tiling — ver `textures-materials.md`. La variante barata de
  "variación" ahí es romper el tiling idéntico entre materiales y pasar a master/instances.)

### 2.3 Imperfección [10:18]
- Hay que pensarlo **durante todo el proceso**, al hacer materiales y modelos, no al final [10:26].
- Herramienta principal: **decals de Megascans** [10:51]. Casos concretos del proyecto:
  - **Leakage decals** (manchas de escurrimiento) en el siding/revestimiento del edificio [10:59].
  - Imperfección en el **techo metálico** para que se vea ligeramente **weathered** (intemperizado)
    [11:06].
- [10:18] Los tres principios se solapan mucho entre sí.

## 3. Iluminación (setup concreto)
- [04:22] El autor NO trae la iluminación desde 3ds Max: **ilumina desde cero en UE5**.
- Exterior [04:30]: un **HDRI** como environment light, con la intensidad **muy subida** ("crank it
  way up") para conseguir specular reflections muy buenas — que pagan después en el follaje [04:38].
- Interior [04:47]: luces básicas de UE5, **cálidas** como corresponde a una luz interior, con
  **area shadows** y a los niveles correctos.
- [04:54] **Con Lumen ya no hay que hornear ni volver estáticas las luces**: todo es en tiempo real
  y dinámico, "algo muy equivalente al ray tracing" [05:09].
- HDRI Dome [14:27]-[15:25]:
  - Dentro del dome vive un **skylight**.
  - Subir la intensidad CAMBIA la exposición de cámara y la intensidad relativa de las demás luces,
    y está bien, porque a cambio obtienes esas specular reflections en hojas mojadas [14:44].
  - Con intensidad 1 o 10 el resultado es totalmente distinto [15:09].
  - **El tamaño del dome debe abarcar toda la escena** [15:25].
- Volumetric fog [15:32]: **Exponential Height Fog normal con Volumetric activado** + jugar con
  density. "Nada especial".
- CLAVE para los rayos [15:48]: un **Directional Light cuya posición coincida con la del HDRI** —
  eso es lo que realmente lanza los rayos volumétricos entre los árboles.
- [15:56] Además usó un **blueprint gratuito de "Misty Fog"**: crea niebla volumétrica **dentro de
  un cubo**, como ground fog para rellenar las zonas brumosas del bosque.
- [12:37] Categoría "efectos": weather effects, environment effects (volumetric fog), camera
  effects y post-processing — todos suman al realismo global [12:45].

## 4. Ajustes de cámara para realismo
- [16:59] Ajustar la cámara para que el shot se parezca a uno de cámara física:
  **depth of field**, **chromatic aberration** en dosis mínima ("tiny bits"), **vignetting**.
  "Todas estas cosas añaden realismo" [17:08].
- [16:43] El autor anuncia un video dedicado a los ajustes de cámara; aquí solo los enuncia.
- (Cruce: nuestro corpus oficial tiene `cinematic_cameras`, `using_cameras`, `camera_actors` y
  `color_grading_and_the_filmic_tonemapper` en `curriculum/raw/` para profundizar.)

## 5. Gente en escena
- [13:02] Meter gente "parece intimidante pero es bastante fácil con un plugin".
- [13:24] Plugin de **Chaos Group** (el transcript fonético dice "Ana/anima/anime"; **nombre exacto
  POR CONFIRMAR, no inventarlo**). Es una colección enorme de personas.
- Versión **Light/gratuita** = solo unos pocos personajes y capacidades limitadas; para gente en
  serio hay que pagar la colección completa [13:16], [14:11].
- Flujo [13:32]-[14:03]: usar los **ambient people**, colocarlos (se puede traer un modelo de fondo
  para saber dónde ponerlos, pero el autor los coloca directo en UE5), **hornear (burn in) las
  animaciones**, guardar el archivo, **importar directo a UE5** — la gente llega con sus
  animaciones asociadas, y solo falta **añadir esas animaciones al Level Sequencer**.

## 6. Clima: Easy Rain (lo que sale mal)
- [17:32] **Easy Rain** (también de William Faucher, Fab Marketplace): solución casi drag-and-drop
  para añadir lluvia.
- ADVERTENCIA MEDIDA POR EL AUTOR [17:39]: "spoiler: no terminó siendo tan fácil. Es fácil de
  AÑADIR, pero no es fácil que se vea exactamente como quieres y art-directed. La razón principal:
  **se ve de una forma en el viewport y al renderizar daba resultados inesperados**, y tuve que
  re-renderizar varias veces para lograr lo que quería." Puede ser limitación suya de no saber
  usarlo bien [17:55]. ⇒ Lección para nosotros: **no confiar en el viewport para juzgar un efecto
  de clima; validar con un render real** (y presupuestar re-renders).
- Lo bueno [18:04]: añade **material functions a TODOS los materiales de la escena** con facilidad:
  salpicaduras (splashes), gotas corriendo por el vidrio, charcos [18:12]-[18:26].
- Setup [18:26]: los materiales deben usar **material attributes**, se pasan por esa función, y
  entonces todos los ajustes afectan a cualquier material configurado así. "Crear todo esto desde
  cero sería una tarea ridícula" [18:41]. Costo pequeño, vale la pena [18:49].

## 7. Materiales y assets
- [05:25] Aplicar materiales de alta calidad a las superficies que **no llegaron bien desde 3ds
  Max**; Megascans es enorme para esto [05:34].
- [05:42] Recorrer TODO el proyecto asegurando que cada material tenga un **muy buen punto de
  partida**; en muchos casos ese punto de partida es Megascans [05:50].
- [05:58] Megascans también sirvió para **añadir elementos fotogramétricos al modelo**, reforzando
  la base.
- [02:04] En el modelo original: muchos objetos custom + **V-Ray Cosmos Library** (calidad
  típicamente alta) [02:11], presupuesto $0 [02:28].
- [02:43] Exportación 3ds Max → UE5 con **Datasmith**.

## 8. Checklist operativo destilada para M3 de proyecto-archviz
Orden que se deriva del curso (no es cita textual):
1. Modelo: detalle donde la cámara lo ve; nada de geometría pobre esperando que la luz la salve.
2. Iluminación desde cero en UE5: HDRI dome (skylight, intensidad alta, tamaño que abarque la
   escena) + directional light alineado con el HDRI + luces interiores cálidas con area shadows.
3. Materiales: buen punto de partida en TODAS las superficies; romper la repetición.
4. Detalle de abajo hacia arriba y SOLO donde hay cámaras.
5. Variación: rotaciones/escalas aleatorias, mezcla de materiales por vertex painting, displacement.
6. Imperfección: decals (escurrimientos, intemperizado).
7. Niebla: Exponential Height Fog + Volumetric, y ground fog en cubo si hace falta.
8. Cámara: DOF, chromatic aberration mínima, vignetting.
9. Clima (opcional): validar con render, no con viewport.
10. Render final: presupuestar horas, no "tiempo real".
