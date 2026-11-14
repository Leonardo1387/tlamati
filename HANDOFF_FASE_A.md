# HANDOFF — ARRANCAR FASE A DE TLAMATI
# (Documento de inicio de sesión. Si eres el agente y el fundador te lo señala, ejecuta.)

## QUÉ HACER AL LEER ESTO (protocolo, no negociable)

1. Carga el skill `tlamati-harness-project` (es la fuente de verdad del proyecto).
2. Lee ~/code/tlamati/PRD_TLAMATI.md y ~/code/tlamati/GUIA_IMPLEMENTACION.md (secciones
   §0 inventario y FASE A).
3. EJECUTA LA FASE A TAREA POR TAREA (A1→A7). Protocolo del fundador: un paso → entrega
   → él revisa → siguiente. NUNCA encadenes "por eficiencia". Entrega larga = archivo +
   resumen en chat.
4. Al terminar A7: ALTO. No toques Fase B sin luz verde.
5. CIERRE DE SESIÓN OBLIGATORIO: genera "la clase del día" con
   ~/code/tlamati/edu/PROMPT_CLASE_DIARIA.md (1-3 cuartillas, profesor→alumno
   no-técnico, español mexicano, números SOLO de la sesión real). Regla fija del
   fundador: esta capa educativa va en cada sesión de Hermes Y en cada sesión de
   Tlamati (F15 del PRD).
6. Si necesitas `sudo apt install` (ripgrep/bubblewrap): NO es de Fase A — eso es
   Fase B/C; ahí se le pide la clave al fundador en su momento.
7. Auditoría: Hermes es el auditor del proyecto (coexistencia decidida 13-nov). Tras
   cada tarea A#, auto-revisión honesta contra el PRD §7 narrow waist y las
   invariantes; los hallazgos van al resumen de entrega, no se esconden.

## CONTEXTO DEL PROYECTO (decidido, no re-litigar)

- Tlamati = arnés agéntico OSS (Apache-2.0), Python desde cero, local-first estricto,
  enfocado en EDUCACIÓN. Repo local ~/code/tlamati/; GitHub target
  leonardoGH/tlamati (privado→público v0.1). PyPI nombre libre (verificado 404).
- COEXISTE con Hermes (este agente): Hermes revisa/audita lo hecho en Tlamati.
- Esqueleto Reasonix (Go, MIT, descontinuado 12-nov-26) = solo referencia
  arquitectónica. dots.llm1 es MODELO, no arnés. Claude Code y Cursor = privativos:
  análisis conductual/evidencia REA, jamás copiar líneas. Codex/Gemini/Qwen/OpenCode/
  Grok/harness2 = OSS en vendor/, lectura directa de source (Apache/MIT).
- Research completo: research/01 (arnés>modelo; Vercel 80→100, LangChain 52.8→66.5,
  Letta 59.1 vs CC 41.6), 02 (anatomía 8 sustratos), 03 (agentes-como-carpetas→F6b
  routing.md + pipeline REA Fase F), 04 (ahorro tokens M1-M5 + red CC), 05 (system
  prompt builder CC + subsistema memoria/auto-dream→F4+F15).
- Evidencia REA: rea-out/cc-analyze-v3.json = AST COMPLETO de cli.js (3.12M nodos,
  1,034 findings, 192 nodos grafo; ev_88097eb4…). v4 (semántica 6GB) murió con /new;
  DECISIÓN: no relanzar — AST v3 basta; la cirugía F3 usa function/decompile dirigido
  por offset (ya se probó: grep -b + dd leen el bundle sin Ghidra; system prompt
  builder está en offset 11,666,006).
- REA quirks ladder (documentado en skill): heap 1GB→grafo incompleto silencioso;
  timeout por fuente 300s default→subir --analysis-timeout-ms; fail-soft
  (partial_observation); --token-limit choca con output estructurado→--filter-output;
  combo bueno: heap 4096 + timeout 2e6.

## FASE A — QUÉ CONSTRUIR (GUIA §FASE A; el demo es la definición de "terminado")

DEMO: `tlamati -p "arregla X"` resuelve un bug real en repo de prueba, con presupuesto
visible. Tareas:

A1. Scaffolding: uv init --package; pyproject [project.scripts]; ruff+mypy+pytest;
    CI GH Actions; LICENSE Apache-2.0 + NOTICE.md.
    Verificar: `uv tool install --from . tlamati && tlamati --version`
A2. core/messages.py — el cuello de botella: Message, ToolCall, ToolResult, Usage.
A3. providers/base.py — Protocol stream(messages,tools)->AsyncIterator[Event];
    OpenAICompat (OpenRouter/Ollama/vLLM via base_url) + AnthropicMessages
    (tool_use/tool_result + cache_control breakpoints; SEMÁNTICA de
    ~/.hermes/hermes-agent/agent/anthropic_adapter.py, MIT). Test con httpx
    MockTransport.
A4. core/loop.py ≤500 LOC — while turno→stream→tools→append; dataclass de estado;
    interjección v1 por SIGINT→mensaje pendiente.
    CORRECCIÓN APROBADA (14-nov, fundador): el demo de A y los evals de A7 necesitan
    herramientas, que son Fase B. Incluir en A4 un mini-set PROVISIONAL (tools_min/:
    read_file, write_file, terminal-foreground, marcadas `provisional` per Han-Lee,
    sin sandbox, aprobación simple). B1-B3 lo reemplaza por el registry formal.
    A4 recibe check_budget() como protocolo simple; A5 lo implementa (inversión de
    dependencia resuelta).
A5. context/budget.py — tiktoken+aproximador; umbrales 80/95%; context_breakdown por
    SECCIÓN (patrón registry de CC: cada sección nombrada, toggleable, con costo
    visible — meta-lección de research/05).
A6. context/compaction.py — resumen modelo barato configurable; regla de oro: muta
    SOLO el sufijo, jamás el prefijo cacheable (invariante "caching is sacred").
A7. fixtures/ + tlamati-eval — 5 tareas terminal-bench-lite, JSONL éxito/tokens/costo;
    baseline con qwen3-coder vía OpenRouter (OPENROUTER_API_KEY ya vive en entorno
    Hermes; NO uses ANTHROPIC_API_KEY nativa).

METAS DE ÉXITO que miden A (PRD §5): overhead pre-primer-prompt <8k tokens; costo/tokens
visibles por turno.

## ORDEN DE ENTREGA SUGERIDO (micro-pasos dentro de A, por si A1+A2 es "un paso")

Paso A-1a: A1+A2 (esqueleto + tipos) → entregar árbol y tests verde.
Paso A-1b: A3 (adapters + mocks) → entregar transcript de normalización tool-call.
Paso A-1c: A4+A5 (loop+budget) → demo `-p` contra OpenRouter.
Paso A-1d: A6 (compaction) → prueba sesión larga sin romper caché.
Paso A-1e: A7 (evals) → JSONL baseline + clase del día que cierra la fase.

-- generado por Hermes, 14-nov-2026, sesión 3. --
