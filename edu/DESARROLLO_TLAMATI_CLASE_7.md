# Desarrollo Tlamati — Clase 7
## 17-nov-2026: El mapa de ruteo — routing.md y las tres capas

En la clase 6 construimos el plan-mode: el agente explora antes de ejecutar. Hoy cerramos la Fase C completa con la pieza que le faltaba al presupuesto de contexto: un mapa que le dice al agente qué leer y qué ignorar según la tarea, escrito en markdown plano. Se llama C6 (workspaces + routing.md, feature F6b del PRD) y al terminar el día quedó fusionado a main con CI verde.

El problema, en escena cotidiana: imagina que contratas a un arquitecto para arreglar el baño y, antes de escucharte, se pone a leer TODOS los planos de la casa — cimientos, jardín, instalación eléctrica del sótano. Así trabaja un agente sin ruteo: carga contexto que no necesita, paga tokens por él, y encima se distrae. El autor del video "agents as folders" (research/03, nuestro donor de hoy) lo resuelve con una idea radicalmente simple: el sistema operativo del agente es una carpeta con archivos de texto. Nada de bases de datos, nada de búsquedas vectoriales mágicas. Un archivo `routing.md` con una tabla: "para tareas de documentación → lee docs/, ignora src/".

Antes de escribir una línea de código, la sesión empezó con algo que también es ingeniería: tres decisiones abiertas se presentaron al fundador EN CRISTIANO, con opciones y recomendación. Las tres se resolvieron igual: versión determinista y simple para v1. (1) El archivo usa una tabla markdown parseable (columnas fijas: patrón, workspace, contexto, cargar, omitir, skills), no prosa libre — el programa necesita certeza, aunque al humano le guste más la prosa. (2) El mapa vive solo en cada proyecto (`.tlamati/routing.md`); no hay mapa global de usuario todavía — inventar reglas de fusión para un caso que no existe viola KISS ("keep it simple, stupid": no construyas lo que aún no necesitas). (3) Quién elige la zona: el programa, con patrones de texto (fnmatch — el comodín de toda la vida: `*docs*` significa "cualquier texto que contenga docs"), no el modelo con una herramienta propia. ¿Por qué? Porque cada cambio de zona cambia el prefijo del prompt, y el prefijo es territorio sagrado de la caché (94% de cache_read en el baseline: por cada 100 tokens de entrada, 94 ya estaban pagados). Un modelo indeciso saltando de zona rompería eso.

## Qué se construyó y cómo (sección replicable)

Archivos clave, todos reales:

- `src/tlamati/context/routing.py` (~300 líneas, nuevo): el loader. Busca `.tlamati/routing.md` subiendo desde el directorio actual hasta la frontera del repo (misma regla que C4), parsea la tabla, resuelve el workspace activo (flag `--workspace` > primer fnmatch de la tarea > ninguno), lee el archivo de contexto de la zona activa y devuelve un objeto `Routing` congelado (dataclass frozen — una vez creado, no se puede mutar, como un sello de cera).
- `src/tlamati/cli.py`: flags nuevos `--workspace NAME` y `--no-routing`; el bloque de routing se inyecta en el prefijo DESPUÉS de las instrucciones (C4) y ANTES de memoria/skills — orden estable, append-only.
- `src/tlamati/memory/skills.py`: `catalog_text(only=...)` ahora puede filtrar el catálogo de skills a las que la zona activa cablea (skills just-in-time, capa 2).
- `tests/test_routing.py`: 26 tests nuevos. Suite total: 292 verdes.

Los comandos exactos de la auditoría (el portón local que replica el CI):

```bash
cd ~/code/tlamati && git checkout -b c6-routing   # rama nueva saliendo de main
uv run pytest tests/ -q          # 292 passed in 1.44s
uv run ruff check src tests      # All checks passed!
uv run ruff format --check .     # 89 files already formatted
uv run mypy --strict src         # Success: no issues found in 37 source files
```

El smoke REAL (prueba de comportamiento, cero costo de red — la key era dummy, así que la corrida muere en el 401 del proveedor PERO el prefijo ya se construyó y el log lo delata):

```bash
mkdir -p /tmp/c6_smoke/.tlamati /tmp/c6_smoke/docs && cd /tmp/c6_smoke && git init -q .
printf '| patrón | workspace | contexto | cargar | omitir |\n|---|---|---|---|---|\n| *docs* | documentacion | docs/contexto.md | docs/*.md | src/, vendor/ |\n| *bug* | codigo | | src/ | docs/ |\n' > .tlamati/routing.md
tlamati -p "actualizar los docs de instalación"
# → [routing] workspace=documentacion v:23e262205d5a   ← detectó la zona SOLO con la tarea
tlamati -p "arregla un bug del parser"
# → [routing] workspace=codigo v:0fd9682fc606          ← otra tarea, otra zona, automático
tlamati -p "docs" --workspace inexistente
# → aviso honesto: "no existe (disponibles: documentacion, codigo)" — nunca truena
```

Y el baseline real (este SÍ gasta centavos vía OpenRouter): `tlamati-eval --out evals/c6_check.jsonl` → 5/5 OK, cache_read 94-95%. El ratchet de Osmani se mantiene: ningún merge puede bajar de 5/5.

## La teoría detrás

El patrón de hoy tiene nombre: **presupuesto de contexto con fronteras de caché** (context budgeting). La idea reusable: en cualquier sistema donde el contexto cuesta dinero o atención, sepáralo en capas por VOLATILIDAD, no por tema. Research/03 las llama MAPA / HABITACIONES / MESAS: capa 1 el mapa completo (cambia rara vez → entra en el prefijo cacheable, versionado con hash sha256[:12] — el mismo truco de C4: el prefijo solo cambia si cambia el contenido, nunca por metadatos de la corrida); capa 2 el contexto de la zona activa (semi-estable, solo la zona activa, nunca todas); capa 3 los archivos reales (variables → NUNCA en el prefijo, se leen bajo demanda con read_file). Este patrón de "nombre predecible como índice" es la anti-lección de "grep is all you need": recuperar por convención de nombres beats embeddings mágicos cuando el espacio es pequeño y el dueño escribe los nombres.

La herramienta nueva del día: **fnmatch** de la librería estándar de Python (`from fnmatch import fnmatch`). Recibe dos cadenas — un texto y un patrón con comodines (`*` = cualquier cosa, `?` = un carácter) — y devuelve True/False. Es el mecanismo de los globs de shell. Cero dependencias, determinista, auditable: misma entrada, misma respuesta, siempre.

El contrato transversal que se respetó (y que ya viste en B5, C1, C3): **fail-soft** — routing.md ausente, roto, ilegible, tabla inválida, contexto fuera del proyecto… cada fallo degrada con un aviso honesto y NUNCA rompe la corrida. Un mapa es una mejora, no un órgano vital. Y el path-escape guard (donor C5): el archivo de contexto se resuelve y se verifica que viva dentro del proyecto (`relative_to`), porque "../secreto.md" no es un contexto, es una fuga.

## Qué decidimos NO construir

El mapa global de usuario (reglas de merge inexistentes para un caso inexistente), la herramienta `switch_workspace` para el modelo (llegará, si acaso, en D2 con plugins), y cualquier forma de RAG o embeddings para resolver la tarea a la zona. Decir que no es parte del diseño: las tres negativas son la misma filosofía — v1 determinista sobre base sólida, lo flexible después.

## El error del día

El más instructivo fue un test que nació rojo: `test_version_stable_and_content_hash`. Añadí una fila nueva al routing.md… DESPUÉS del texto al pie, y la versión NO cambió. ¿Bug del hash? No: bug del test. El parser (correctamente) ignora todo lo que no sea la tabla contigua — la fila había quedado fuera de ella, tras el párrafo de notas. El test se corrigió inyectando la fila DENTRO de la tabla. La lección: cuando un test falla, primero pregunta si el código está mal o si tu SUPUESTO sobre el código está mal. Hoy el supuesto estaba mal. Hubo dos menores más: un `run_loop()` llamado sin su argumento obligatorio `budget=` (TypeError inmediato — Python te cobra los kwargs faltantes al instante, y eso es bueno) y un assert con mayúscula equivocada ("workspace ACTIVO" vs "Workspace ACTIVO"). Los tres cazados antes del commit, por eso existe la auditoría local como portón.

## Estado al cierre y gancho

Main = cdf8e4a: FASES A + B + C COMPLETAS (C1-C6). CI verde (run 44128533570). 292 tests. Baseline 5/5 con caché 94-95%. Rama `c6-routing` fusionada con OK verbal del fundador.

Siguiente frente: **FASE D**, la frontera exterior del arnés — D1 subagentes (el agente delega una tarea aislada a un hijo con toolset read-only, presupuesto propio y profundidad máxima 1), D2 plugins (hooks before_tool/after_tool/on_error, con el ledger B5 como primer consumidor real), D3 cliente MCP (conectar herramientas de servidores externos, tratados como territorio NO confiable). La pregunta de la clase 6 (save_plan fuera de plan-mode) queda anotada para Fase E.

**Pregunta abierta para mañana: en D1 el subagente hereda el tope de presupuesto del padre pero corre con herramientas read-only por defecto. ¿Debería el padre poder darle permiso de escritura a un hijo, o la escalera de permisos solo puede ENDURECER hacia abajo — un hijo nunca más poderoso que lo que el padre permitiría directamente? La política del proyecto dice "nunca relajar"; el patrón delegate de Hermes dice "toolset reducido fijo". Hoy ambos coinciden… ¿y si mañana no?**
