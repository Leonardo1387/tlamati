# PASO 1 — Qué hace sobresalir a un arnés agéntico (investigación en foros de devs)
Fecha: 14-nov-2026. Fuentes primarias en `sources/` (capturas crudas).

## Tesis central: el arnés mueve más la aguja que el modelo
Evidencia recogida (winder.ai + MongoDB compilado abril 2026 + HN):

| Experimento | Resultado |
|---|---|
| Vercel: quitar 80% de las herramientas a un agente, MISMO modelo | éxito 80%→100%, tokens a la mitad, latencia 724s→141s |
| LangChain: cambiar SOLO el arnés de su coding agent | Terminal Bench 52.8%→66.5% |
| Princeton CORE-Bench: mismo modelo, otro scaffold | 42% vs 78% |
| Harvey (legal): solo trabajo de arnés | >2x accuracy en agentes legales |
| Letta Code vs Claude Code, AMBOS con Claude Opus 4.5 (Terminal-Bench 2.0) | Letta 59.1% vs Claude Code 41.6% — un arnés tercero le ganó al primero en el modelo de SU propio vendor, por memoria duradera |

Conclusión Raschka (matizada): modelos vanilla actuales son "de mucho parecidos"; el arnés "often can be the distinguishing factor". Philipp Schmid: "1% en un leaderboard no detecta si el modelo se desvía tras 50 pasos" → la fiabilidad del loop es lo que importa, no el pico de capacidad.

## Anatomía canónica del arnés (consensuada 2026)
Definiciones: LangChain = "todo el código/config/lógica de ejecución que no es el modelo". Harness EJECUTA un agente; framework COMPONE varios; plataforma de flota los gobernar a todos (capa 4: durable execution, atribución de costos, auditoría).

Componentes de un harness de coding (Raschka, 6) + lo que los foros añaden:
1. **Contexto vivo del repo ANTES del primer prompt** (mapeo, dependencias, AGENTS.md).
2. **Prompt dividido en prefijo cacheable + sufijo variable** → economía de caché es sagrada (Hermes lo llama "per-conversation prompt caching is sacred"; CC manda 33k tokens antes de leer el prompt, OpenCode 7k — HN 48883275, 706 pts: el overhead del arnés ES el costo).
3. **Herramientas predefinidas con validación + control de acceso por ruta.**
4. **Compresión/recorte de contexto** (compaction) — Hermes lo hace con un modelo aparte; codex con "rollout/compaction"; grok con crate xai-grok-compaction.
5. **Memoria de sesión ESTRUCTURADA, separada de la transcripción** — el diferencial Letta vs Claude Code.
6. **Subagentes acotados**: permisos read-only, límite de recurrencia.
Añadidos por los foros: sandboxing, persistencia, conectividad (MCP), triggers/crons, planeación vs ejecución (plan mode en qwen/gemini/codex), permisos/aprobaciones, hooks.

## Los 4 diferenciadores que separan a los buenos arneses de los mediocres
Recurrentes en HN (hilos 48460863, 47990675, 48883275, 43735550, 50094994) y winder:

**A) Gestión de contexto = el arte principal.** No es "meter más contexto" (ingenuo, 0xbadcafebee en HN: Tree-sitter/LSP/PageRank dan contexto SEMÁNTICO en vez de voliar tokens con grep). El benchmark "grep is all you need" muestra que string-matching gana en recuperación literal — la lección real: **herramienta de búsqueda barata y predecible > RAG mágico para código**. Compaction sin romper caché. Regla "context is a resource" (Anthropic best-practices, HN 43735550).

**B) Seguridad con postura "harness afuera, agente adentro"** (HN 47990675, 182pts): el arnés controla y ejecuta; el LLM solo mueve contenedores de datos. Simon Willison "lethal trifecta": datos privados + contenido no confiable + comunicación externa = exfiltración garantizada si se combinan sin controles. El arnés debe poder romper la trifecta (permisos por herramienta, redallow-lists, sandbox). Sandbox NO protege la factura (OpenHands loop-e y quema tokens): faltan **límites de gasto/spend caps y presupuesto por tarea** (hermes-agent lo llama rollout budget / budget_config).

**C) Simplicidad del loop y del formato de herramientas.** Pu.sh: arnés completo en 400 líneas de shell (HN 47968112). Lección: el loop es ~150 líneas; todo lo demás son herramientas y política. Formato de tool-call: el ecosistema reporta "formats that one agent emits another won't parse" → **normalizar a function-calling nativo por proveedor con fallbacks** (hermes-agent tiene anthropic_adapter, codex_responses_adapter, bedrock_adapter, azure_identity_adapter: la misma clase de problema resuelto con adapters por backend).

**D) Memoria duradera + aprendizaje desde fallos (Osmani's ratchet).** "Cada vez que el agente se equivoca, ingeniería para que nunca vuelva a pasar; cada regla en el archivo de instrucciones trazable a un fallo real, y ninguna regla antes de uno." → los skills/archivos markdown SON el código del arnés ("Markdown is now code" — Winder). Letta gana por sustrato de memoria. DeepSeek convierte el loop entero en plugin: todo es composición.

## Qué NO hacer (anti-patrones citados)
- Tool-count inflado: cada herramienta viaja en cada llamada API → "narrow waist, capabilities at the edges" (AGENTS.md de hermes-agent; Vercel: menos tools = más éxito).
- Reglas especulativas ("infraestructura para la que no hay consumidor" — hermes rejects speculative hooks).
- Comodidad que llama afuera por defecto (OpenCode mandaba el 1er mensaje a gpt-5-nano hosted para titular sesiones hasta v1.2.23 — HN; para un arnés local-first esto es traición de confianza).
- workarounds de arnés que el próximo modelo volverá obsoletos: Han Lee, "el harness es deuda técnica invisible; casi todo se disolverá en la siguiente generación". Test: ¿un modelo mejor haría esto innecesario? Compaction: probablemente sí (temporal). Sandboxing, permisos, spend limits, auditoría: NO — codifican "qué permite la organización" (permanente). → **Invertir la ingeniería en la parte permanente.**

## Licencias y estándares que el proyecto debe respetar
Estándares de facto 2026: **MCP** (Anthropic, herramientas), **AGENTS.md** (OpenAI, instrucciones), **ACP — Agent Client Protocol** (Zed; interop entre arneses: Zed/OpenHands/DeepSeek/grok-build/qwen lo hablan). Fundación Linux "Agentic AI Foundation" ancla en esos tres. Si Tlamati es open source MIT/Apache-2.0, conviene hablar los tres protocolos desde temprano.

## Fuentes
- sources/winder-ai-harness-comparison-SNAPSHOT.txt (acceso via browser; curl sin render devuelve nav-only — SPA/JS)
- sources/hn-comments-harness.txt (HN Algolia API, hilos listados)
- sources/lethal-trifecta.txt (simonwillison.net 2025-06-16)
- sources/harness2-arxiv.txt (arXiv 2610.14224)
- Referencias internas citadas: AGENTS.md de NousResearch/hermes-agent (reglas de caché/narrow waist verificadas en el repo local, v0.18.2)
