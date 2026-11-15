# HANDOFF 4 — B1+B2 ENTREGADOS · SIGUE B3 (sandbox bwrap)
# Generado por Hermes, 15-nov-2026, sesión 6 (cierre). Reemplaza HANDOFF_FASE_B.md
# en estado; el protocolo SIGUE VIGENTE (un paso → entrega → revisión, Hermes =
# auditor, clase del día al cierre).

## PROTOCOLO (no negociable, igual que siempre)
1. Carga skill `tlamati-harness-project` + lee PRD_TLAMATI.md y GUIA_IMPLEMENTACION.md §B.
2. Un paso → entrega → el fundador aprueba por COMPORTAMIENTO (no lee código:
   decisión 15-nov, el fundador es no-técnico; Hermes auto-audita con
   tests+ruff+mypy+baseline y fusiona directo con OK verbal).
3. Cierre de sesión: clase del día (la próxima es CLASE_5).

## ESTADO REAL AL CIERRE (verificado con ejecución)
GIT: ~/code/tlamati · remoto origin = github.com/leonardoGH/tlamati (PRIVADO,
  creado esta sesión con gh CLI). main = B2 fusionado (7b0a36e). Ramas b2-tools
  y fase-b ya fusionadas (se pueden borrar: `git branch -d fase-b b2-tools`).
CALIDAD: 121 tests verdes · ruff limpio · mypy --strict limpio (21 archivos).
INSTALADO: uv tool reinstall hecho tras B2 (tlamati + tlamati-eval al día).
DEPS SISTEMA: bwrap 0.9.0 + rg 14.1.0 instalados (sudo OK; clave WSL reseteada
  por el fundador vía `wsl -u root` → `passwd`). Sandbox probado:
  `bwrap --ro-bind / / --unshare-all echo ok` → "ok". YA NO HAY QUE PEDIR CLAVE.

### B1 (commit 8960f3d) — registry formal
- src/tlamati/tools/registry.py: Tool(name, description, input_schema, run,
  permission=auto|ask|deny, sandboxable). Registry: duplicados = ValueError al
  registrar; execute() = escalera unknown→tipo→jsonschema(Draft 2020-12, ANTES
  de ejecutar)→permission gate→run; TODO fallo → ToolResult(is_error=True),
  nunca excepción al loop. ASK sin approver = error honesto (nunca yolo
  silencioso). Approver es async (B4 pondrá TUI/headless). Truncado M1 (50k).
- tools_min/ ELIMINADO (git rename → tools/builtin.py). loop/cli/evals reciben
  Registry. Dep nueva: jsonschema (+types-jsonschema en dev).

### B2 (commit 7b0a36e) — herramientas formales
- src/tlamati/tools/files.py: read_file (numerado, offset/limit default 500/
  max 2000, truncado honesto 100k chars con next-offset), write_file, edit
  fuzzy 9 estrategias: S1 exact, S2 rstrip, S3 lstrip, S4 ws-collapsed,
  S5 stripped-lines, S6 crlf-normalized, S7 blank-lines, S8 anchored-fuzzy
  (first/last line + middle en orden), S9 token-subsequence (ventanas de
  tokens, span expandido a líneas completas). Ambigüedad (>1 match sin
  replace_all) = error honesto. no-op edit = error. fuzzy_replace() es función
  pura testable fuera del tool.
- src/tlamati/tools/search.py: search_files vía rg subprocess. target=content
  (--json parseado → path:line|text) | files (--files -g glob). rc=1 →
  "(no matches)" honesto; rc=2 → "ERROR: rg exit 2: ..." verbatim; rg ausente
  → error explícito. limit cap 200, timeout 30s.
- src/tlamati/tools/terminal.py: igual que Fase A (foreground 120s) +
  sandboxable=True. background+poll = v1.1 (NO construir en B3).
- builtin.py: make_tools() compone 5 tools en ORDEN ESTABLE (read, write,
  edit, search, terminal) porque las specs son parte del prefijo cacheable.
  Specs = 566 tokens (medido con cl100k_base).
- VERIFICACIÓN REAL: baseline 5/5 re-corrido vs OpenRouter (qwen3-coder);
  smoke nuevo /tmp/b2_smoke: agente usó search_files + edit (NO write_file)
  para fixear bug en calc.py, función vecina intacta, verify OK, cache_read
  95%, 8 turnos.

## PENDIENTE — B3 (siguiente paso, luz verde YA dada de palabra: "arranca b3"
## pendiente de confirmación al inicio de la próxima sesión)
B3. sandbox/bwrap.py: jaula de ejecución para terminal (y edit si aplica):
  `--ro-bind / / --bind <workdir> <workdir> --dev /dev --unshare-net` por
  defecto; flag --net = permiso separado. Perfil default: fs read-only +
  workdir escribible. GUIA_IMPLEMENTACION.md §B3 es la especificación.
  Sugerencias de la sesión 6 (no son spec, decidir al implementar):
  - bwrap en WSL: --unshare-all YA verificado funcionando (ver arriba).
  - El tool terminal ya tiene sandboxable=True: B3 = construir el wrapper y
    engancharlo en make_terminal_tools (flag de config para activar/desactivar,
    default ON si bwrap existe, degradación honesta si no).
  - Test de fuga: comando que intente escribir fuera de workdir DEBE fallar.
  - Cuidado: --ro-bind / / hace que /tmp sea read-only también; los fixtures
    de evals corren en tmp_path → o se bindea el workdir del eval también, o
    el sandbox se activa solo en CLI real. DECIDIR EN B3 y documentar.
Luego: B4 policy/ (auto|ask|deny + trifecta untrusted→ask; approver real para
el ASK del registry) y B5 ledger SQLite + `tlamati audit`.

## IDEA DEL FUNDADOR (15-nov, NO es tarea de B3 — backlog Fase C+)
El fundador propuso: integrar el flujo de ingeniería de datos RAG de Proyecto Legal
(extracción PDF → chunking → embeddings → FAISS+BM25+RRF → reranker → LLM, ver
skills proyecto-legal-corpus-pipeline / rag-pipeline-local) como parte de las
herramientas de Tlamati. Análisis Hermes (para discutir con el fundador antes
de construir nada):
- NO meterlo en read_file (mezcla de responsabilidades; read_file es lectura
  cruda honesta). La forma correcta sería tools NUEVAS del ladder de footprint
  (regla hermes: extensión antes que core tool nuevo): p.ej. `index_corpus`
  (ingesta un directorio → store local) y `semantic_search` (query → top-k
  chunks con score). Encaja con el everything-plugin del research 02.
- Tension con el PRD: "No-goals: no RAG-code-first" — el no-goal es no hacer
  de Tlamati un framework RAG, pero tools opcionales de retrieval local no lo
  violan si son un plugin/extra, no el núcleo. DECISIÓN DEL FUNDADOR requerida:
  ¿tool opcional instalable (extras) o plugin Fase C+?
- Reutilizar: pipeline proyecto-legal ya existe y funciona (FAISS+BM25+RRF+reranker,
  entry buscar_con_evaluacion()); Tlamati podría llamarlo como librería, no
  reescribirlo. Local-first encaja (todo en disco, sin red).
- Estado: IDEA REGISTRADA, sin spec, sin estimación. No arrancar sin decisión.

## PITFALLS NUEVOS (acumular en skill references/fase-a-state.md al leer esto)
- Prefijo crece con cada tool nuevo: specs de 5 tools = 566 tokens; tests con
  Budget apretado (750) mueren en budget_exceeded aunque todo funcione.
  Recalibrar: el mínimo real del test de compaction pasó 750→1100 (medido con
  sonda binaria); se dejó en 1200 con margen. SIEMPRE medir el mínimo, no
  adivinar.
- La escalera fuzzy hace cortocircuito en la PRIMERA estrategia que matchea:
  tests que afirman "usó S3" pueden recibir S1/S2 si el input también matchea
  antes. Afirmar resultado + estrategia solo cuando el caso fuerza esa
  estrategia (p.ej. CRLF solo matchea en S6; líneas insertadas solo en S8).
- gh repo create --source=. --push solo sube la rama activa: push manual de
  main + gh repo edit --default-branch main después.
- apt en WSL: unattended-upgrades deja procesos colgados con el lock (26h en
  esta máquina). El mensaje de error da el PID; kill al PID, NUNCA borrar
  lockfiles.
- El bloque de Hermes NO permite probar contraseñas sudo por stdin (ni debe).
  SUDO_PASSWORD en ~/.hermes/.env es el mecanismo oficial si se quiere que el
  agente corra sudo (texto plano; decidir con el fundador).

-- Hermes, 15-nov-2026, sesión 6. B1+B2 EN MAIN. Sigue B3. --
