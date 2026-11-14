# PASO 2.7 — El system prompt builder de Claude Code + el problema de MEMORIA

Método: REA `decompile` es para nativos (Ghidra); para el bundle JS usamos las
coordenadas byte-offset que el propio inventario REA estableció (grep -b + dd sobre
cli.js). Lectura de comportamiento/arquitectura, sin copiar código. v2.1.92.

## 1. System prompt builder (función GW, offset 11666006) — hallazgos

1. EL PROMPT ES UNA LISTA DE SECCIONES CON NOMBRE, no un string:
   [identity | session_guidance, memory, ant_model_override, env_info, language,
    output_style, bg-job-dir, scratchpad, frc, summarize_tool_results, brief]
   cada una es una función lazy que puede devolver null y filtrarse.
2. LA PRUEBA DE FUEGO CONTRA NUESTRO TESIS DE OVERHEAD: la variable de entorno
   `CLAUDE_CODE_SIMPLE` colapsa TODO el system prompt a 3 líneas (identidad + CWD +
   fecha). Es decir: los ~33k tokens que midimos en el Paso 1 son andamiaje OPCIONAL
   por diseño de Anthropic. Lección Tlamati: el system prompt debe ser un registry de
   secciones con toggle por sesión y un modo "simple" de primer clase — y medimos el
   costo de cada sección (nuestro context_breakdown hace visible ESTO por sección).
3. Identidad = UNA frase fija con 3 variantes por entrypoint (CLI / Agent SDK / agente
   headless). El header dinámico (versión, entrypoint, workload) viaja en un HEADER
   HTTP de atribución (x-anthropic-billing-header), NO en el prompt → así el prompt
   permanece byte-estable y cacheable. Nuestro patrón equivalente: metadatos dinámicos
   fuera del prefijo cacheable.
4. El bloque env trae: modelo por nombre+ID, knowledge-cutoff mapeado a MANO por modelo,
   warning si es git-worktree ("no vuelvas al repo original"), y nota de sintaxis de
   shell en Windows. Regla ratchet visible: cada línea responde a fallos reales
   (cwd que persiste mal, rutas relativas, etc.).
5. Notas de comunicación con el usuario: "usa SIEMPRE rutas absolutas", "no recapitules
   código que solo leíste", "cero emojis", "no dos puntos antes de tool calls" — el
   ratchet de Osmani en estado puro, copiable como semilla de nuestras reglas.

## 2. Subsistema de memoria de CC (función bl8 + config auto-memory) — hallazgos

- Arquitectura: directorio de memoria + archivo índice MEMORY.md (EW="MEMORY.md",
  constantes s56=200 y j58=25000 = límites de líneas/bytes del índice), tres ESCOPOS:
  user (~/.claude/agent-memory), project (.claude/agent-memory, compartible por VCS),
  local (.claude/agent-memory-local, no versionado) + TEAM memory con sync push/pull
  (eventos tengu_team_mem_sync_* y team_mem_entries_capped → hay CAP de entradas).
- Guidance por scope en el prompt: "user-scope → aprendizajes GENERALES; project-scope
  → sintoniza con este proyecto; local-scope → no se comparte". Exactamente el modelo
  mental que Hermes usa (user vs memory targets).
- AUTO-DREAM (autoDreamEnabled, "background memory consolidation"): consolidación de
  memoria EN SEGUNDO PLANO, fuera del turno — el mecanismo que Weaviate/Letta llaman
  "sleep-time compute". El agente no aprende durante la tarea; un job posterior destila.
- Gate de escritura existe (descripción: "when false, Claude will not read from nor
  write to") + claudeMdExcludes (globs para NO cargar ciertos CLAUDE.md → control de
  overhead de memoria-contexto).
- qwen-code (source Apache, vendor): services/memory/extract.ts +
  extractionAgentPlanner → la EXTRACCIÓN de memoria es un agente/planner separado, con
  tool search_memory como herramienta compactable (¡está en la whitelist M2 de
  microcompactación! — la memoria se re-puede buscar, por eso su resultado es borradle).

## 3. Síntesis "la memoria es un grave problema" → diseño Tlamati (F4 ampliado)

El consenso de los 4 arneses con memoria seria (CC, qwen, letta-patrón, hermes):
1. ESCRITURA CON GATE: solo hechos durables (preferencias, correcciones, entorno);
   prohibido volcar progreso de sesión. (Hermes memory tool dice lo mismo.)
2. ÍNDICE PEQUEÑO + CUERPOS FUERA: MEMORY.md (≤~200 líneas) es un catálogo; el cuerpo
   vive en archivos por tema, se lee bajo demanda. Nunca todo-en-el-prompt.
3. CONSOLIDACIÓN ASÍNCRONA (auto-dream): destilar al terminar la sesión / en cron,
   NUNCA en el turno caliente. Costo: modelo barato.
4. ESCOPOS + CAPS: user/project/local(/team), con límites duros de entradas y bytes.
5. BÚSQUEDA BARATA como herramienta (grep/BM25) → su RESULTADO es microcompactable.
6. Trazabilidad: cada memoria apunta a la sesión/fallo que la originó (ratchet).

Anti-patrones detectados en foros/fuentes (no repetir): memoria tipo "chat history
dump", embeddings mágicos como único acceso, consolidación inline que rompe caché.

## 4. Capa educativa (nuevo enfoque del producto)

Decisión 14-nov: Tlamati es arnés enfocado en EDUCACIÓN → artifact "clase del día":
al cerrar cada sesión, generar 1-3 cuartillas como si un profesor de ML/CS/fullstack
explicara a un alumno NO técnico qué se hizo ese día. Prompt canónico:
edu/PROMPT_CLASE_DIARIA.md. Se prueba YA con nuestras sesiones de Hermes (uso manual
del prompt al cierre) y se porta a Tlamati como F15 [SHOULD v1] (post-session hook +
auto-dream comparten el mismo mecanismo: job asíncrono al cerrar sesión).
