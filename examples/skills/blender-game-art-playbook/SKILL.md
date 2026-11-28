---
name: blender-game-art-playbook
description: "Blender as a game-asset tool: low-poly blockout to game-ready, retopology (quads vs tris, remesh, Quad Remesher), 3D character modelling for engines. Curriculum links + references distilled only from measured work (mesh stats, polycount, verified FBX exports). Load when modelling, retopologising, or preparing Blender assets for Unreal/a game engine — the planos->DXF->FBX pipeline itself lives in proyecto-archviz/docs and creative-apps-mcp-bridges."
---

# Blender Game-Art Playbook (modelado/retopo low-poly para motores)

Propósito: expertise de Blender como herramienta de asset pipeline (no el flujo
planos→DXF→FBX ya documentado en los docs internos del proyecto).

## Reglas de uso
- Curriculum original: sources-curriculum.txt (sección Blender del documento de currículo).
- Una reference se destila SOLO cuando un trabajo real la necesite y con medición
  (mesh stats, polycount, exports verificados). Nada de teoría copiada sin usar.
- Lo ya verificado del puente Blender→FBX→Unreal vive en
  la skill creative-apps-mcp-bridges y en los docs internos del proyecto; no duplicar.

## Corpus destilable (YA EN DISCO, 27-nov-2026)
Los 7 links de Blender del currículo ya están como texto limpio en
`<proyecto>/curriculum/raw/*.txt` (corpus local del proyecto). No hace falta web_fetch.

## Mapa de temas
| Tema | Reference | Corpus en `raw/` (KB) | Estado |
|---|---|---|---|
| Retopología (quads vs tris, Quad Remesher) | references/retopology.md | quads_vs_triangles 17.7, quad_remesher 13.8, retopology_for_games 11.4, retopology_dense_sculpt 9.1 | NO DESTILADA |
| Low-poly blockout→game-ready | references/lowpoly-blockout.md | low_poly_modelling 11.6, low_poly_character_blockout 7.7 | NO DESTILADA |
| Personajes 3D | references/character-modelling.md | 3d_character_modelling 11.5 | NO DESTILADA |

Convención: cada afirmación lleva **[MEDIDO]** (verificado aquí: mesh stats, polycount,
FBX exportado y comprobado) o **[DOC]** (teoría sin comprobar). Nunca mezclar.

## TRAMPA DE MEDICIÓN de renders/verificación de encuadre [MEDIDO, pagada en proyecto-archviz]
- Contar **"píxeles no negros"** da **falso positivo**: el world Background Strength=0.7 deja un
  fondo gris (46,46,46), así que el cuadro "no negro" es 100 % aunque el objeto ocupe 0.59 %. Con
  esa métrica el controlador de encuadre alejó la cámara a 131 m creyendo el cuadro lleno y aun así
  reportó veredicto positivo.
- **Métrica correcta:** diferencia contra el **color de fondo medido = mediana del cuadro**, nunca
  contra negro asumido.
- **Blender NO trae Pillow** instalado ⇒ medir el PNG desde fuera (script de Python del host).
- Los **subprocesos en background mueren** en la jaula del tool terminal ⇒ correr Blender
  **síncrono** y capturar el JSON de resultado a un archivo.
