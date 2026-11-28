# Escala y realismo de medidas (Unreal 5.8.4)

Destilado 27-nov-2026 desde el corpus en
`<proyecto>/curriculum/raw/`
(designer_01_project_setup_and_level_blockout, hdri_backdrop) + hechos MEDIDOS en
proyecto-archviz. Convención: **[MEDIDO]** = verificado en este entorno;
**[DOC]** = documentación oficial, aún sin comprobar en el editor.

## Unidad base
- **[MEDIDO]** Unreal trabaja en CENTÍMETROS. 100 uu = 1 m. Todo el pipeline
  planos→DXF→Blender→FBX→Unreal de proyecto-archviz entrega en cm y coincide
  1:1 (bounds de 58/58 meshes verificados a escala 1:1 en sesión 12).
- **[MEDIDO]** Grid-snap por defecto = 10 uu (10 cm) al mover objetos.
- **[DOC]** El cubo de blockout SM_Cube mide 1×1×1 m; su material de grid dibuja
  líneas oscuras cada 1 m, claras cada 0.1 m en el suelo y cada 0.2 m en verticales.
  Es la referencia visual rápida de escala.

## Medidas antropométricas estándar (para que se vea creíble)
| Elemento | Medida estándar | Origen |
|---|---|---|
| Personaje humano | 1.8 m de alto, salta 0.5 m | [DOC] |
| Altura de ojo (1a persona) | **170 cm** (z=170) | [MEDIDO s6/s14: CaptureViewport a z=170 da vista real a altura de ojo] |
| Puertas | 1.0–1.5 m de ancho × 2.0 m de alto | [DOC] |
| Paredes (alto) | ~4 m (exterior/estructural); interior habitable 2.6–3.0 m | [DOC] + [MEDIDO s10: techo interior = 3.00 m, dato del fundador] |
| Grosor de muro | 10–30 cm es buen punto de partida (casa: más fino) | [DOC] + [MEDIDO: muros del plano = 20 cm] |
| Pasillos | 2–3 m de ancho × 3–4 m de alto | [DOC] |
| Altura trípode HDRI | ~90 cm (Z del Projection Center del HDRI Backdrop) | [DOC] |

## Reglas de legibilidad (no solo realismo)
- **[DOC]** La escala debe ser PREDECIBLE: al acercarse, el jugador debe saber de un
  vistazo si algo es cubierta (crouch), saltable, trepable o imposible. Ejemplo del
  tutorial: una tapia de 0.6 m (= salto 0.5 m + 0.1) frustra porque parece saltable y no
  lo es; mejor usar trepaderas visuales que comuniquen "por aquí no".
- **[DOC]** Mantener MEDIDAS CONSISTENTES en todo el nivel sostiene la credibilidad.
  El contraste se usa a propósito (una puerta más grande insinúa importancia).
- **[DOC]** Realismo total NO siempre juega bien: una puerta de 0.8 m se siente
  cómoda en la vida real pero en juego aprieta y la cámara puede clipar. Equilibrar
  realismo y diversión según el tipo de juego.
- **[DOC]** **Tercera persona: multiplicar la escala ×1.5** (la cámara va más atrás,
  todo se ve más chico). Primera persona (nuestro caso) usa escala 1:1.
- **[DOC]** Poner un maniquí de referencia (SKM_Manny_Simple, Content>Characters>
  Mannequins) en cada espacio mientras se bloquea, para no perder la escala humana.
  En proyecto-archviz el equivalente MEDIDO es la propia captura a z=170.

## Aplicado a la maqueta actual (proyecto-archviz) [MEDIDO]
- Escala = OPCIÓN A: 1:1 sobre la cadena SUPERIOR de cotas → losa **12.000 × 7.600 mm**
  = 1200 × 760 cm. Los m² rotulados (250/100/150) son decorativos de imagen IA, se ignoran.
- bbox global de los 58 meshes importados = **12.15 × 7.75 × 3.17 m**
  (min[-7.5,-767.5,-17] max[1207.5,7.5,300]); z=0 es el piso caminable.
- Eje Y sale NEGADO (Unreal es left-handed). No recalcular transformadas desde
  posicion_m: colocar actores con xform IDENTIDAD (los bounds locales ya traen la posición).
- Techo interior = 300 cm; muros = 300 cm de alto × 20 cm de espesor.
- Área útil ~85.41 m². Altura de ojo de recorrido = 170 cm. FOV de captura = 90°.
