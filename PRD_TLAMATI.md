# PRD — TLAMATI: arnés agéntico open-source, local-first
Versión 0.1 · 14-nov-2026 · Owner: Leonardo Gutiérrez · Nombre: tlamati ("el sabio", náhuatl)
Licencia elegida: **Apache-2.0** (incluye concesión de patente; MIT aceptable, Apache preferido para proyecto que aspira a adopción corporativa).

---

## 1. Problema y oportunidad
Investigación del Paso 1 (research/01_HALLAZGOS_PASO1.md) demostró que, con modelos de capacidad similar, **el arnés —no el modelo— decide el desempeño**: Vercel +20 pts de éxito quitando herramientas (mismo modelo), LangChain 52.8→66.5% cambiando solo arnés, Letta 59.1% vs Claude Code 41.6% sobre el MISMO Claude Opus 4.5. Y Han Lee advierte la mitad del trabajo de arnés es desechable cuando sube el modelo — salvo lo PERMANENTE: sandbox, permisos, límites de gasto, auditoría, memoria, trazabilidad.

Oportunidad: los mejores arneses abiertos (opencode 226k★, hermes 263k★, codex, gemini-cli, qwen-code) convergen en una receta conocida. Ninguno es *nuestro*: Tlamati es el arnés que corre en la máquina del desarrollador con sus modelos (OpenRouter/Anthropic vía OpenRouter, GPU alquilada por hora para pesos abiertos, Ollama local), sin fugas de datos por comodidad (anti-patrón OpenCode: session-titling con modelo hosted), que hereda las decisiones probadas y evita los costos no probados (no reinventar el sandbox de Windows de 24k LOC).

## 2. Usuarios
- **Primario:** Leonardo Gutiérrez, power user en WSL/Ubuntu; CLI + TUI; un humano aprueba acciones peligrosas.
- **Secundario:** devs de la comunidad OSS que corren modelos abiertos en hardware propio (el nicho que winder.ai identifica: "running a harness against open-weight models on your own hardware").

## 3. Propuesta de valor
1. **Local-first garantizado:** ninguna llamada de red que no la haya pedido explícitamente el usuario o el modelo. Ni titling, ni analítica, ni "conveniencia hacia afuera". Modo offline con Ollama.
2. **Agnóstico real de proveedor:** adapters normales (Anthropic messages, OpenAI-compatible, OpenRouter, Ollama, vLLM, Enverge) con **fallbacks de formato de tool-calling** (anti-patrón "formats one agent emits another won't parse"). El modelo es un plug-in.
3. **El arnés no es desechable:** ingeniería concentrada en lo permanente (permisos, sandbox, presupuesto, auditoría, memoria) y heurísticas de contexto marcadas como temporales/replaceables.
4. **Todo-Plugin con núcleo mínimo:** ~500 LOC de loop; todo lo demás herramientas, políticas y skills markdown ("Markdown is now code"). Hereda de Reasonix (MIT — reutilizable con atribución; su muerte oficial lo hace material de semilla, no de dependencia).
5. **Evaluable desde el día 1:** suite de evals versionada y trazas append-only (anti-patrón: "appears to work in controlled conditions, fails under production load").

## 4. Objetivos (v1) / No-objetivos
### Sí en v1
- Loop agéntico turn-by-turn con streaming, interjección del usuario a mitad de turno (patrón xai-interjection-core), y plan-mode (explorar→aprobar→ejecutar).
- Herramientas core: terminal (con aprobación), filesystem (read/write/edit con diff y control de acceso por ruta), búsqueda (ripgrep-first, semántica opcional Tree-sitter/lsp más adelante), web (opt-in), sub-agente acotado.
- Gestión de contexto: presupuesto por tokens (tiktoken/contadores nativos), compaction con modelo barato de fallback, **prefijo cacheable estable** (cache-first, invariante de Hermes: "per-conversation prompt caching is sacred"). Jerarquía de ahorro M1-M5 (research/04): truncado en la herramienta → budget check → microcompactación de tool outputs reproducibles con placeholder+pointer (patrón qwen microcompact.ts + API Anthropic context_management/cache_edits, siempre detrás del último breakpoint de caché) → compaction con modelo barato → ventana nueva.
- Sesiones: SQLite, transcript + resumen estructurado separados; retomar sesión. Memoria de largo plazo tipo archivos markdown + memoria persistente editable.
- Permisos: política declarativa por herramienta/patrón/ruta; allowlists de red; regla "lethal trifecta" (contenido no confiable que cruza hacia comunicación externa requiere aprobación explícita).
- Sandbox: bubblewrap en Linux/WSL (read-only por defecto, rutas writable declaradas); v1 en macOS = aprobaciones estrictas; Windows host = vía WSL.
- Skills markdown + AGENTS.md (formato OpenAI) + MCP client (servidores locales stdio; catálogo).
- Workspaces con routing declarativo (patrón "agentes como carpetas", research/03): `routing.md` en el prefijo cacheable — tabla "tarea → archivos a cargar/omitir/skills"; contexto por workspace bajo demanda; convenciones de nombre como índice (sin BD). Loader `context/routing.py` ~100 LOC.
- TUI simple (Textual) y modo headless `tlamati -p "..."` para scripts/CI.
- Evals: 20 tareas propias + runner Terminal-Bench-lite; métricas: éxito, tokens/turno, costo, latencia, overhang del system prompt.
- CLI empaquetada (`uv tool install tlamati`), config.yaml único (no .env excepto secretos).

### No en v1 (explícito, evita YAGNI)
- Multi-agente orquestado tipo flota/gobernanza (capa 4 del stack).
- Editor IDE (vscode/zed/acp server), desktop app, mensajería (gateway).
- Auto-mejora recursiva del arnés (harness2) — lo dejamos como **modo v2** opcional: proposer/probe/compose.
- Reimplementar sandbox de 24k LOC para Windows nativo; soportar Windows fuera de WSL.
- RAG de código embebido (la evidencia del Paso 1 favorece búsqueda determinista barata primero).

## 5. Éxito medible (target vs estado actual de referencia)
- Overhead pre-primer-prompt < 8k tokens (réf: OpenCode 7k vs Claude Code 33k).
- ≥95% de sesiones sin error de formato tool-call en los 3 backends objetivo.
- Eval interno: ≥ el mismo % de éxito que Qwen-Coder corriendo bajo opencode con mismo modelo, y documentar el delta de arnés (nuestro experimento "cambiar arnés, no modelo").
- Costo visible: cada turno reporta tokens/costo; compaction reduce ≥40% tokens en sesiones de 50 turnos sin perder tarea.
- Adopción OSS: repo Apache-2.0 con CONTRIBUTING, CI, release v0.1 en ≤6 semanas de trabajo enfocado.

## 6. Requisitos por feature (prioridad MoSCoW)
F1 Loop+adapters [MUST] · F2 Herramientas core+permisos [MUST] · F3 Contexto: presupuesto+compaction+cache [MUST] · F4 Sesiones SQLite+memoria [MUST] · F5 Sandbox bwrap [MUST] · F6 Skills/markdown+AGENTS.md [MUST] · F6b Workspaces+routing.md [SHOULD v1, MUST v1.1] · F7 TUI/headless [SHOULD] · F8 MCP client [SHOULD] · F9 Sub-agentes [SHOULD] · F10 Evals+trazas [MUST] · F11 Plugins todo-plugin [SHOULD] · F15 "Clase del día" educativa: post-session hook que genera texto 1-3 cuartillas para alumno no-técnico (edu/PROMPT_CLASE_DIARIA.md; comparte mecanismo con auto-dream/consolidación) [SHOULD v1] · F16 Onboarding guiado por nivel: primera corrida detecta config ausente → pregunta nivel (principiante/técnico) → checklist de setup paso a paso (proveedor+llave, herramientas recomendadas como ripgrep/bwrap, REA opcional para apps cerradas, migración de skills 1-flag). Visión del fundador (sesión 20, verbatim en HANDOFF_E3d §2): "el agente te va llevando paso a paso con el setup" — el arnés es para primerizos, la ceremonia de entrada debe ser cero-fricción. Ceremonia cero con Hermes (~/.hermes/skills auto-descubierta, PASO A) y ojos Windows (PASO C) ya resuelven parte; F16 unifica la experiencia de primera vez. [COULD v2 — documentada, NO implementada en v0.1] · F12 Auto-mejora harness2-mode [COULD v2] · F13 ACP server [COULD v2] · F14 Web/browser [COULD v2] · WON'T: desktop/gateway/multi-agente v1.

## 7. Arquitectura (narrow waist)
```
tlamati/
  core/        loop, mensajes, turnos (≈500 LOC, estable)
  providers/   adapters: anthropic, openai_compat, ollama (+ OpenRouter/GPU-alquilada como configs)
  tools/       registro declarativo: name, schema, permission, sandbox_policy, run()
  policy/      permisos, aprobaciones, reglas trifecta, allowlists red
  context/     budget, compaction, prompt-cache estable, snippets
  session/     SQLite (transcript, resumen, ledger), retomar
  memory/      archivos markdown (memoria + skills), AGENTS.md loader
  sandbox/     bwrap profile, rutas, red
  subagent/    scope acotado, read-only default, límite recurrencia
  evals/       tareas, runner, trazas
  ui/          textual TUI + headless
  plugins/     entry-points (todo-plugin estilo Reasonix)
```
Invariantes: (1) prefijo del system prompt byte-estable por conversación; (2) toda llamada al proveedor pasa por provider adapter que normaliza tool_calls a formato interno y degrada con fallback declarado; (3) ninguna herramienta sin permission declarada; (4) cada acción del modelo se escribe en ledger append-only con costo; (5) el loop nunca muta contexto pasado salvo compaction explícita.

## 8. Riesgos y mitigación
- **Modelo→arnés se reescribe cada generación:** mitigar con interfaces estrechas y heurísticas etiquetadas `provisional` (test de Lee: ¿un modelo mejor anularía esto?).
- **Seguridad (trifecta letal):** web-reading + filesystem privado + comunicación externa = exfiltración → política default: contenido externo marcado untrusted, herramientas de salida (red/envío) piden aprobación cuando el turno incluyó contenido no confiable.
- **Licencia:** REA sobre Claude Code/Cursor (privativos): **estudio de comportamiento** permitido; prohibido copar código/bundle. Lo reutilizable viene de MIT/Apache (Reasonix, hermes-agent, opencode, codex, gemini-cli, qwen-code) con atribución NOTICE.
- **Scope creep:** lista WON'T + revisión mensual "regla del ratchet" (Osmani): ninguna nueva regla/prompt sin un fallo real que la justifique.

## 9. Competencia y por qué existe Tlamati
| | opencode | hermes | qwen-code | codex | **tlamati** |
|---|---|---|---|---|---|
| Local-first estricto | parcial | sí | parcial | no | sí |
| Agnóstico modelos | 75+ | sí | bugs multi-modelo | solo OpenAI | sí + fallbacks formato |
| Todo-plugin | plugins | skills+plugins | parcial | no | sí (semilla Reasonix) |
| Harness2 auto-mejora | no | no | no | no | modo v2 |
| Personal/máquina propia | general | sí | Qwen-first | OpenAI-first | propio, auditable |

## 10. Glosario
arnés/harness = todo lo que rodea al modelo para que actúe; capability = unidad plugin (tools+hooks+instrucciones+settings, sentido Pydantic v2); ACP = Agent Client Protocol (Zed); MCP = Model Context Protocol (Anthropic); AGENTS.md = formato de instrucciones (OpenAI).
