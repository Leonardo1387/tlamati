# PASO 2.5 — "Agentes como carpetas" (video, 14-nov-2026) + estado real de REA

## 1. Video revisado: /mnt/c/Users/<usuario>/Desktop/agents as folders.txt (transcripción, 22:55)

Tesis del autor: el "archivo de trabajo" (workspace) como sistema operativo del agente —
 folders + markdown + routing en lenguaje natural, sin base de datos ni código.

Arquitectura de 3 capas:
- Capa 1 MAPA: CLAUDE.md raíz — se carga SIEMPRE. Estructura de carpetas, convenciones
  de nombre, tabla de ruteo ("para esta tarea lee estos archivos, ignora aquellos,
  quizás necesitas estas skills"). El autor lo llama "the most important pattern".
- Capa 2 HABITACIONES: contexto.md por workspace (community/production/writing room).
  Solo se carga cuando entras a ese workspace. Ahí van cableadas las skills y MCPs
  "just-in-time", no todo el tiempo.
- Capa 3 MESAS DE TRABAJO: los archivos reales + convenciones de nombre que reemplazan
  la base de datos ("API-off-guide-draft-v2.md" → el agente encuentra el artefacto por
  nombre sin SQL/RAG).

LO QUE VALE PARA TLAMATI (copiar legal = construir nuestra versión):
1. RUTEADOR DECLARATIVO EN MARKDOWN. La tabla "tarea → carga estos archivos, omite
   estos" ES la respuesta al problema del overhead que medimos en el Paso 1 (CC 33k
   tokens antes del prompt vs OpenCode 7k). En Tlamati: `routing.md` como parte del
   prefijo cacheable, y el loader respeta la tabla → contexto por workspace bajo
   demanda. Esto es un DIFERENCIADOR local-first gratis: no es magic RAG, es un
   subsistema de presupuesto de contexto (budget.py, Fase A5) con interfaz en markdown.
2. CONVENCIÓN DE NOMBRE COMO ÍNDICE. Anti-lección de "grep is all you need" (Paso 1):
   recuperar por nombre literal predecible > embeddings mágicos. Tlamati: patrón de
   nombre de artefactos como metadato parseable (slug + estado + versión), sin BD.
3. SKILLS DENTRO DE UN PROCESO, NO SUELTAS. El autor insiste: la diferencia con
   "un montón de skills" es que van cableadas en la cadena de pensamiento de cada
   workspace (brief → spec → build → output, pipeline de 4 etapas con contexto por
   etapa). Tlamati: los hooks de plugin (D2) + stages de pipeline como config, no
   como agentes separados. "No construyas un agente por tarea: sé el agente del
   workspace" — alinea con loop único + plugins.
4. CAPAS = FRONTERAS DE CACHÉ. Map (inmutable → cacheable), workspace-context (semi),
   history (variable). Lección de economía: la separación del autor coincide exacta
   con la regla del prefijo cacheable del Paso 1.

LO QUE DESCARTAMOS (no copiar):
- Su claim "cero código/Python/framework": es un power-user de Claude Code, no una
  arquitectura de arnés. Tlamati SÍ necesita presupuesto de tokens, sandbox y spends
  caps que un folder de markdown no impone. Su modelo de seguridad es implícito
  (confía en el suscripción); el nuestro es explícito (permisos por herramienta).
- Su "5-layer paper" es marketing pendiente (template a los VIP); no hay evidencia.
- Voice-first "en 6 meses todos harán esto" — predicción, no dato.

Acción concreta: agregar al PRD como feature "workspaces con routing.md" (Should-have
v1, Must-have v1.1) y a GUIA Fase D como `context/routing.py` (~100 LOC que parsean
la tabla y filtran el loader).

## 2. Estado REAL y honesto de REA (respuesta a "¿ya lo usaste para CC y codex?")

NO todavía. Lo que sí está hecho: verificación de instalación (rea@6.7.0, capabilities
Linux OK) y planificación como Fase F. HOY corrimos el PRIMER smoke test real contra
el bundle de Claude Code y salieron hallazgos importantes:

- COMANDOS CLAVE QUE RESPONDEN "¿para qué sirve?": 
  `analyze-javascript-application` (reconstrucción estática del bundle: grafo de
  módulos, entrypoints, límites Electron/IPC), `decompile` (leer parte de la app
  como pseudocódigo), `function` (analizar una función completa con evidencia),
  `compare-application-versions` (diff de grafos entre versiones — ver QUÉ CAMBIÓ
  sin source), `compare-javascript-export-shapes` (formas de retorno de exports),
  `capture-electron-scenario` / `capture-process` (evidencia conductual en vivo),
  `annotate-native-function`. Output orientado a LLM (--llms, --token-count,
  --filter-output) = hecho para que un AGENTE (yo) lo opere.
- SMOKE TEST 1 (heap default 1GB): exit 0, pero "worker exhausted its heap" en cli.js
  → grafo INCOMPLETO (22 nodos, 44 findings, 2 JS parseados).
- ATENTO 2 (heap 6144MB): exit 1 por `provider_timeout` — el límite de 300s por
  fuente (option --analysis-timeout-ms) no se subió; cli.js necesita más tiempo, no
  más RAM (máquina: 7.6GB total). REA devolvió `details.partial_observation` con
  evidencia parcial del intento: 1.93M AST nodes visitados, 990 findings, grafo 192
  nodos/1011 edges, coverage=partial + límite registrado. REA es fail-soft: el
  timeout NO destruye lo ya analizado. evidence_id de esta observación parcial
  registrado para F3.
- ATENTO 3 (v3, en curso): heap 4096 + --analysis-timeout-ms 2,000,000.
- LECCIÓN OPERATIVA (aplica a nuestra fase F): REA es análisis EVIDENCIA→SEMÁNTICA,
  no decompilador mágico. Para CC: usarlo con --max-heap-mb alto (probando 6GB) y
  luego `function`/`decompile` quirúrgicos por dirección de evidencia; y combinar
  con mods/ de su repo público (que SÍ es MIT-adjacent y auditable) y con
  observación conductual (spend caps, tool schemas vía /cost, logs).
- CODEX NO NECESITA REA: openai/codex es Rust+TS OSS con source completo en
  vendor/codex — copiar legalmente = leer source Apache-2.0 y reescribir en Python.
  REA es para lo PRIVATIVO (Claude Code) y para verificación binaria (si Grok-build
  distribuye binarios). Regla del proyecto: REA solo donde no hay source; donde hay
  source, lectura directa + atribución mental (licencia lo permite).
- Ética/legal reaffirmada: REA produce EVIDENCIA de arquitectura y contratos
  (formas de tool-call, límites de sistema, canales IPC). Nosotros construimos
  implementaciones propias en Python a partir de la SEMÁNTICA aprendida. Minifier-
  ofuscado no se "traduce" línea a línea; y la licencia de CC prohíbe reverse
  engineering para competencia directa de producto — de ahí que nuestro uso sea
  análisis conductual/arquitectónico documentado, sin derivar código.

## 3. Pipeline F propuesto (reemplaza "Fase F transversal" genérica)

F1. analyze-javascript-application --max-heap-mb 6144 (en curso ahora) → grafo
    completo de cli.js + fingerprints.
F2. compare-source-to-bundle: su repo público (mods/plugins/examples) contra el
    bundle → qué mods oficiales revelan de la arquitectura interna.
F3. Querurgía: `function`/`decompile` sobre nodos de evidencia específicos:
    (a) construcción del system prompt (¿qué manda esos 33k tokens?), (b) esquema
    de tool definitions, (c) loop de compaction, (d) permission engine, (e) streaming
    retry/fallback. Cada hallazgo → nota en research/rea/cc/FX_<tema>.md con
    evidence_id referenciado.
F4. Conductual complementario: corrermos CC local con --output-format json /
    /cost / OTel debug (mods/telemetry existe) y loggear overhead real por turno.
F5. SÍNTESIS: tabla "feature CC → semántica observada → decisión Tlamati (copiar
    concepto/rechazar/temporal)" → insumo directo del PRD v1.1.
Codex/Gemini/Qwen/OpenCode/Grok: sin REA; lectura de source + tests propios.
