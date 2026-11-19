# 08 — Benchmarks existentes de arneses (investigación 17-nov-2026, sesión 16)

Fuentes verificadas en vivo: tbench.ai (leaderboard Terminal-Bench 4.1), HN/Algolia
(story 47920787 dirac), research/01 (números ya conocidos). Fecha de captura: hoy.

## 1. EL LEADERBOARD OFICIAL: Terminal-Bench 4.1 (tbench.ai)

La tabla YA es una matriz ARNÉS×MODELO (exactamente lo que nuestro PRD quiere
publicar a escala propia). Columnas: resolution rate ± desviación, tokens, costo.

### Entradas clave capturadas (top + relevantes para nosotros)

| # | Modelo | Arnés | Resolución | Tokens | Costo corrida |
|---|--------|-------|-----------|--------|---------------|
| 1 | Copilot Fusion (max) | GitHub Copilot | 71.2% ±2.9 | 3.3B | $2.0k |
| 2 | Opus 5.5 (max) | Claude Code | 65.8% ±3.1 | 8.0B | $4.7k |
| 2 | Fable 5.2 (max) | Claude Code | 65.8% ±2.8 | 15.7B | $16.5k |
| 4 | Gemini 4 Carbon (high) | Antigravity CLI | 64.5% ±3.2 | 3.8B | $1.4k |
| 6 | GPT-6.1 Sol (max) | Codex | 60.9% ±3.0 | 1.5B | $0.6k |
| 19 | Grok 4.7 (xhigh) | Grok Build | 38.8% ±3.6 | 5.5B | $3.7k |
| 26 | **Qwen3.8-Max-0902 (max)** | **Claude Code** | **27.0% ±3.9** | 3.0B | $4.6k |
| 32 | Grok 4.6 (high) | Grok Build | 19.7% ±3.1 | 4.0B | $3.6k |
| 40 | Grok 4.5 (high) | Grok Build | 12.4% ±2.6 | 3.4B | $2.1k |

Otros arneses presentes: GitHub Copilot, Claude Code, Antigravity CLI, Codex,
Grok Build, Muse Code, mini-swe-agent. **opencode, hermes y tlamati NO están.**

### Lecturas importantes

a) **NUESTRO MODELO YA TIENE NÚMERO OFICIAL**: Qwen3.8-Max-0902 + Claude Code =
   27.0%. Si algún día corremos Tlamati + el mismo modelo en Terminal-Bench,
   existe un punto de referencia público. OJO: es la variante "max", no
   qwen3-coder (distinto modelo de la familia; NO confundir).

b) **EL DELTA DE ARNÉS SIGUE SIENDO NOTICIA VIVA**: story HN 47920787 (dirac,
   OSS): 65.2% con Gemini-3-flash-preview vs 47.8% del agente oficial de Google
   con EL MISMO modelo (+17.4 pts solo por arnés) y vs 64.3% de Junie CLI
   (cerrado, tope). Cita textual del autor: "It is astounding how much the
   harness matters". Repo: github.com/dirac-run/dirac. Pendiente de ser aceptado
   en el leaderboard (PR en HF discussions 145) — los maintainers tardan.

c) **COSTO REAL DE COMPETIR EN EL LEADERBOARD**: $200–$16,500 por corrida
   completa (columna COST). Con modelo barato (qwen3-coder vía OR, ~$0.1-0.5/M)
   sería del orden de cientos de dólares — viable solo como campaña puntual, no
   como parte de E3.

d) **HAY TRAMPAS DOCUMENTADAS**: debugml.github.io/cheating-agents — agentes
   que hacen trampa en Terminal-Bench 2.0 (skills.md inyectados, modificación
   de timeouts). Reglas de integridad: sin archivos de ayuda inyectados, sin
   modificar recursos/timeouts, misma versión OSS que la pública. Nuestras
   fixtures deben cumplir el mismo estándar (instruction.md es la ÚNICA ayuda;
   verify.py decide; nada de pistas al modelo).

e) **Efecto techo**: los 10 fixtures nuestros son toys; con Opus/GPT-6 todo
   dará 10/10 y la tabla no discrimina. Por eso el leaderboard real usa tareas
   duras (por eso cuestan $2k+). Corolario: nuestras tablas solo comparan
   arneses/models de nivel similar (qwen3-coder, coder80B), NO frontier.

## 2. ¿QUÉ BENCHMARKS PÚBLICOS EXISTEN POR ARNÉS? (estado del arte)

- **Terminal-Bench 4.1** (tbench.ai / harborframework en HF): el estándar
  de-facto para agentes de terminal. Matriz arnés×modelo. Arneses presentes:
  los de la tabla de arriba. opencode NO aparece (aunque es vendor nuestro).
- **SWE-bench Verified**: repos GitHub reales (issues→PR). Domina el discurso
  "modelo" más que "arnés" (casi todos corren el agente scaffold mínimo).
- **Benchmarks de vendor** (Anthropic/OpenAI/xAI publican números propios):
  NO comparables entre sí (cada quien elige su benchmark) — por eso existe
  Terminal-Bench como árbitro neutral.
- **Letta 59.1 vs Claude Code 41.6** (mismo Opus 4.5, research/01): punto
  harness-vs-harness publicado por un vendor sobre benchmark propio.
- **LangChain Terminal Bench 52.8→66.5 harness-only** (research/01).

## 3. RESPUESTA A "¿PODEMOS USAR LOS NÚMEROS DE ELLOS?"

SÍ, con dos reglas:
1. **Citar, no mezclar**: los números del leaderboard son de OTRA pista
   (tareas duras, $2k+, infraestructura harbor). No se pueden poner en la
   misma tabla que nuestras 10 fixtures (sería comparar peras con manzanas).
   En EVALS.md van en una sección "contexto público" con fuente+fecha.
2. **Sí son usables como REFERENCIA DE MODELO**: p.ej. "Qwen3.8-Max-0902 hace
   27% en Terminal-Bench con Claude Code (tbench.ai, 17-nov-2026)" da marco a
   qué esperar de modelos de esa familia en tareas duras.

## 4. COMPARAR CON LOS MODELOS DEL ENJAMBRE (GPU alquilada por hora) vs FRONTIER

Lo que hay: node0=Super-VL (nemotron), w1=coder80B+q35b, w2/w3=q35b. Túneles
SSH frágiles (mueren, reconectar desde WSL). ¿Versión API? El enjambre es
nuestro: se puede apuntar un provider OpenAI-compatible al túnel (si expone
endpoint compatible; verificar en la próxima ventana que el túnel viva).

Opinión honesta (Hermes):
- **Eje arnés (E3b) = fuerte y barato**: mismo modelo, 4-5 arneses, nuestras
  fixtures. Delta publicable, reproducible, $centavos.
- **Eje modelo local vs frontier = débil con nuestras fixtures**: techo (todos
  10/10) → no discrimina. Y si bajamos la dificultad, frontier aplasta y el
  titular es obvio ("Claude gana"), no aporta. Para que sea serio haría falta
  Terminal-Bench real (cientos de dólares + infra harbor) — campaña aparte,
  decisión de negocio, no de E3.
- **Lo que SÍ vale la pena y es barato**: tabla "mismo arnés (Tlamati), tres
  modelos": qwen3-coder (OR) vs coder80B (enjambre, si el túnel vive) vs
  sonnet (OR). En fixtures MEDIA-ALTAS (las 5 nuevas) el techo no se toca: si
  qwen3-coder hace 6/10 y sonnet 9/10, hay delta real. Esto prueba además que
  Tlamati es model-agnostic (argumento de adopción OSS) y le da uso al enjambre
  como "proveedor local barato" — narrativa de cómputo propio (costo $0 marginal).

## 5. PROPUESTA CONCRETA PARA E3 (para decisión del fundador)

1. E3a: 5 fixtures nuevas media-alta (diseño ya acordado: moldeadas en bugs
   reales del historial, sintéticas y limpias).
2. E3b-tabla1 (eje ARNÉS): Tlamati vs opencode vs codex vs hermes (vs
   gemini-cli si instala) — mismo modelo qwen3-coder vía OR. 10 fixtures.
3. E3b-tabla2 (eje MODELO, nueva y barata): Tlamati + {qwen3-coder OR,
   coder80B enjambre, sonnet OR} en las 5 fixtures duras. Requiere túnel
   el proveedor de GPU vivo en el momento de la corrida.
4. EVALS.md: nuestras tablas + sección "contexto público" citando tbench.ai
   (con fecha) y el caso dirac. NUNCA números inventados.
5. Terminal-Bench oficial = campaña post-v0.1 opcional (presupuesto aparte).

Costo estimado tablas 1+2: ~5 arneses × 10 tareas + 3 modelos × 5 tareas con
qwen3-coder/sonnet vía OR = decenas de corridas de centavos cada una; el mayor
gasto es sonnet (caro por tarea). Total probable: <$5-10. Enjambre: $0 marginal.

## 6. PLAN DGX SPARK (acordado con el fundador 17-nov, sesión 16 — SIGUIENTE FASE)

Idea del fundador (verbatim): "rentamos 1 DGX Spark de 90 centavos la hora, le
integramos los modelos de código abierto y los evals... probar el 120b, coder
80b y 35b". Ya existen scripts de instalación del enjambre de GPU alquilada
(los modelos van FP4/cuantizados 4-bit para CUDA del Spark — decisión previa
del fundador, no re-cuantizar).

Lo que habilita, en cristiano: el costo del leaderboard ($2k-16k) es del
CEREBRO frontier, no de la PISTA. Con el Spark alquilado servimos cerebros
abiertos locales (120B/80B/35B fp4 vía vLLM/SGLang, endpoint OpenAI-compat)
a $0/token marginal; la corrida completa = solo la renta ($0.90/h × horas).

Tablas que se persiguen:
- TABLA MODELO (arnés constante Tlamati): qwen3-coder OR vs 35B vs 80B vs
  120B locales vs sonnet frontier, en las 5 fixtures duras. Prueba
  model-agnostic + narrativa de cómputo propio vs paga.
- TABLA ARNÉS con modelo LOCAL (el dato estrella estilo dirac): "Nemotron
  120B con Claude Code = X%, con Tlamati = Y%". Claude Code acepta apuntar
  fuera de Anthropic vía ANTHROPIC_BASE_URL / claude-code-router; codex vía
  config.toml model_providers; opencode/hermes nativos OpenAI-compat.
- NIVEL 2 (harbor oficial): clonar harbor-framework/terminal-bench-2 (OSS,
  449★), registrar agente custom Tlamati, correr subset con modelos locales
  en el Spark. Cifra publicable: "auto-corrido, metodología oficial".
  Reglas de integridad (anti-cheating documentado): instruction única,
  verify decide, cero skills.md inyectados, timeouts sin tocar, versión
  pública = versión corrida.

Riesgos/caveats honestos:
- Claude Code puede degradarse con modelos no-Claude (tool-format optimizado
  para Anthropic) — si pasa, ES dato publicable y la comparación limpia
  queda entre arneses model-agnostic.
- 120B fp4 en 128GB unificados: cabe pero lento; medir throughput ANTES de
  prometer tiempos de corrida.
- bwrap (sandbox de evals) puede no anidar en contenedores: en Spark
  rentado-desechable correr sin sandbox es aceptable y se documenta.
- Precondición económica: primero fusionar E3a y tener las fixtures duras
  listas (son el corpus); el Spark se renta cuando YA hay qué medir.

Orden acordado: E3a (HECHO, esta sesión) → E3b tabla arnés barata (WSL,
qwen3-coder OR, centavos) → alquiler Spark + tabla modelo + tabla arnés-local
→ nivel 2 harbor si el humo es bueno.
