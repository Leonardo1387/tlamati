# Cámaras, Sequencer y render de animación — [DOC curso-bosque]

Fuente principal: `curriculum/raw/curso_bosque_58_limpio.txt` cap 9 (Sequencer y animación de
cámara). Citas `[H:MM:SS]` = timestamp del transcript.
PENDIENTE de fusionar con el corpus oficial en `curriculum/raw/`: `cinematic_cameras` (16.0 KB),
`cinematics` (8.2), `using_cameras` (5.6), `cinematic_viewport` (5.6), `cameras` (5.5),
`camera_actors` (2.3). Este archivo hoy cubre el flujo de trabajo práctico del curso.

## 1. Level Sequence
- [3:05:39] Content Browser > right click > **Animation > Level Sequence**. Convención de nombre
  del curso: prefijo `LS_` (`LS_Riverband`). Guardarlo en la carpeta `Levels`.
- [3:05:57] Doble click abre el **Sequencer**.
- [3:06:06] Crear carpetas en el Outliner (`assets`) para que la escena sea legible: "esta escena es
  mucho más leíble ahora" [3:06:19].

## 2. Camera actor y qué se puede animar
- [3:06:22] Botón **New Camera** del Sequencer → crea un **Camera Actor** en la escena.
- [3:06:31] Al expandir la cámara se ven las propiedades animables: **Focal Length, Aperture,
  Focus** y el **Transform** de la cámara [3:06:39].
- [3:06:47] Modo por defecto ACTIVADO: moverte por el viewport **reposiciona la cámara**. Si lo
  desactivas, recuperas el vuelo libre [3:06:56].
- [3:07:03] Al seleccionar la cámara en el Sequencer aparece un **preview** de lo que ve (picture-in-
  picture); haciendo click en el preview pasas a **controlar la cámara** directamente [3:07:15].

## 3. Keyframes
- [3:07:30] Seleccionar el **transform** y pulsar **S** en el frame deseado = crear keyframe.
- [3:07:49] **Working Range / Length**: fijar el working length (500) y la longitud de la animación
  (300) para poder expandir la timeline.
- [3:08:16] Mover el playhead a 150, recolocar la cámara, **S** de nuevo → dos keyframes y la
  cámara ya se mueve [3:08:22].
- [3:09:08] Keyframes creados por accidente: seleccionar y **Delete**.
- [3:09:16] Las pistas se pueden **comprimir y mover**: los keyframes se conservan pero el shot va
  más rápido [3:09:28]-[3:09:35].

## 4. Interpolación (el detalle que arruina un dolly)
- [3:09:35] Expandir la pista > seleccionar los keyframes de transform > right click >
  **Interpolation**.
- Por defecto la cámara **acelera**, lo cual "no es óptimo para un shot así" [3:09:43]. Elegir
  **Linear** en ambas pistas → movimiento a velocidad constante [3:09:52].

## 5. Varias cámaras y Camera Cuts
- [3:08:30] New Camera otra vez → se añade una segunda cámara; la nueva queda activa y puedes
  alternar [3:08:38].
- [3:10:04] Ir al frame del corte (150) y en la pista **Camera Cuts** pulsar **+** y elegir la
  segunda cámara → se crea su pista y el Sequencer corta entre ambas [3:10:12].
- TRAMPA [3:10:21]: "no pasa nada" si la cámara activa no es la del corte → hay que hacer click en
  el preview de esa cámara para verla en el viewport. Y si el keyframe estaba mal, recolocar y
  volver a pulsar S [3:10:34].
- Tipos de shot que sugiere el curso: entrar a la escena por detrás del follaje, **dolly**, cortes,
  vistas top-down, y close-ups si tienes buenos assets [3:07:22], [3:11:35].

## 6. Movie Render Queue (render final)
- [3:11:43] Edit > Plugins > buscar "Q" > activar **Movie Render Queue**. Requiere **restart** del
  motor; antes, `Ctrl+Shift+S` [3:11:50].
- [3:12:01] Botón **Render** dentro del Sequencer → abre la Render Queue.
- Ajustes [3:12:09]:
  - **Output Directory**: por defecto `<Proyecto>/Saved/MovieRenders`.
  - **Resolution**: el curso elige 4K.
  - **Output format**: PNG o MP4. MP4 para un preview rápido [3:12:24].
  - **Renderer**: por defecto el normal; también existe **Path Traced** pero tarda mucho más [3:12:31].
- [3:12:49] Durante el render ves un preview en tiempo real de los frames; al terminar la ventana
  desaparece sola.
- [3:13:19] Es calidad de preview: hay mucho más por configurar en la render queue y en los quality
  settings de la escena — remitirse a la documentación de Unreal para eso [3:13:27].

## 7. Cruce con el proyecto proyecto-archviz
- Nuestro artefacto de cierre es una **captura en primera persona limpia**, no un video. La vía ya
  medida es `EditorToolset.EditorAppToolset.CaptureViewport` con `annotations={}`, `gridSpacing=0`
  y `maxLabelDistance=0` (ver SKILL.md "Hechos ya verificados"). El Sequencer solo hace falta si el
  fundador pide un **recorrido animado/render en video**, no para la captura fija.
- Si se pide video: Level Sequence + Camera Cuts + Movie Render Queue (MP4) es el camino, y la
  cámara debe respetar altura de ojo z=170 cm y el interior habitable medido de la maqueta.
