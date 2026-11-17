# 06 — OpenCrawl: "multiplayer" para agentes de código (estudio 17-nov-2026)

Estudio pedido por el fundador: ¿vale la pena integrarlo a Tlamati, usarlo
para varios agentes en conjunto, o es otro proyecto distinto?

MÉTODO: NO se usó REA — la regla (skill web-app-investigation /
rea-closed-source-analysis) es REA solo donde NO hay fuente. OpenCrawl es
open source (repo público getopencrawl/opencrawl-core, Apache-2.0 core+CLI,
MIT plugins/). Se clonó en vendor/opencrawl-core (depth 1) y se leyó fuente
+ docs directamente. Evidencia: README.md, AGENTS.md, ARCHITECTURE.md,
src/mcp/overview.md, docs/mcp.md, docs/session-capture.md,
docs/search-backends.md, docs/self-host.md. API de GitHub: 57 estrellas,
TypeScript, creado 2026-11-04 (DOS SEMANAS de vida), YC + Pareto backed.

## QUÉ ES (en cristiano)

NO es un agente ni un harness. Es un SERVIDOR de memoria compartida +
coordinación que se sienta ENTRE agentes distintos (Claude Code, Codex,
Antigravity, Grok Bot y "cualquier cliente MCP"). Dos capacidades:

1. HISTORIA COMPARTIDA VERBATIM: su CLI instala hooks en los agentes y
   captura los transcripts JSONL nativos COMPLETOS (palabra por palabra, no
   resúmenes) + fuentes conectadas (GitHub, Linear, Slack, Notion vía
   Airbyte/connectors). Cualquier agente del equipo puede buscar en la
   historia de los otros (tools MCP opencrawl_search_v1/fetch). Su pitch:
   "la memoria resumida pierde justo el detalle que el agente de tu
   compañero necesita". Benchmark BEAM propio: 90.3% @100K → 83.7% @10M
   (auto-reportado, corridas separadas de los competidores — tomar con
   pinzas, ellos mismos lo admiten en la letra chica).

2. TABLÓN DE MENSAJES ENTRE AGENTES (board): board_sync/board_post/
   board_presence vía MCP — agentes publican updates, se suscriben a topics,
   reciben menciones, y pueden pedir aprobación humana ("ask a human to
   approve the risky calls" en su demo).

## ARQUITECTURA REAL (leída de la fuente, no del marketing)

- Stack PESADO: Docker Compose con PostgreSQL + OpenSearch + Temporal (jobs
  de indexado) + object storage + Better Auth + consola React (web-v2).
  Hay modo single-host con SQLite FTS5 en vez de OpenSearch, pero Postgres +
  Temporal siguen ahí. ~16k LOC src/*.mts + CLI Bun nativo.
- Modelo de negocio: core/CLI Apache-2.0 self-host gratis; "OpenCrawl Cloud"
  gestionado (pricing no público en la landing; hosted shell propietario con
  WorkOS, billing, etc. — el AGENTS.md separa core abierto de shell hosteado).
- Captura: hooks en los harnesses (SessionStart/PostToolUse/Stop) + lectura
  incremental de los JSONL nativos; uploader con locks y deadlines.
  PRIVACIDAD: ellos mismos avisan — "sessions are team-visible by default
  and can contain sensitive information". Capture es opt-in.
- Integración con clientes: TODO vía MCP (Streamable HTTP remoto) — tools
  list/call estándar. Sin SDK propio obligatorio.

## VEREDICTO (las 3 preguntas del fundador)

1. ¿INTEGRARLO DENTRO DE TLAMATI como feature? NO. Sería importar un
   servidor multi-tenant con auth, indexado y consola web — choca de frente
   con el PRD: Tlamati es harness local-first de UN agente, y "no multi-agent
   fleet" es un NO-GOAL explícito. Construir eso dentro = destruir el
   producto. Además su valor (compartir ENTRE agentes distintos) no existe
   para un usuario de un solo agente.

2. ¿USARLO PARA VARIOS AGENTES EN CONJUNTO? SÍ — es exactamente lo que es, y
   para Tlamati sale CASI GRATIS: la integración es un MCP server remoto.
   En cuanto D3 (MCP client stdio) aterrice, un usuario podrá apuntar Tlamati
   a un OpenCrawl self-hosted con ~5 líneas de tlamati.yaml (ojalá D3 incluya
   transporte HTTP o al menos deje la puerta abierta — anotar en D3:
   OpenCrawl expone MCP por Streamable HTTP, no solo stdio; el spec de D3
   dice stdio mínimo → considerar `url:` además de `command:`). Y sus results
   son contenido de terceros → produces_untrusted=True encaja perfecto con la
   trifecta B4 (ellos mismos dicen "retrieved passages and board messages are
   untrusted source content" — su doc y nuestra política coinciden).
   Hermes también podría conectarse (soporta MCP) → el ecosistema del
   fundador (Hermes + Tlamati + Claude Code) compartiendo historia es el
   caso de uso real, si algún día trabaja en equipo.

3. ¿CONSTRUIR ALGO ASÍ = otro proyecto? SÍ, completamente distinto: es
   infraestructura de equipo (servidor + índices + conectores + consola),
   no un harness. Si en el futuro el programa/B2B pidiera "memoria de
   equipo para abogados", la respuesta correcta sería self-hostear
   OpenCrawl (Apache-2.0, permiso de uso comercial con atribución) y
   conectar nuestros agentes por MCP — NO reescribirlo.

## QUÉ SÍ PODEMOS TOMAR PRESTADO (semántica, donor Apache-2.0/MIT)

- Para D2 (plugins): su `plugins/` (MIT) es ejemplo de plugin que instala
  skills+hooks en OTROS agentes (plugins/opencrawl/skills/opencrawl/SKILL.md)
  — valida que el formato SKILL.md sigue siendo el estándar de-facto (C3).
- Para D3 (MCP): su src/mcp/overview.md es un excelente modelo de
  descriptions honestas (qué NO prueba test_connection; zero results ≠ no
  existe; defaults de privacidad explícitos en searchContext).
- Idea semilla (NO comprometer ahora, regla anti-speculative): un plugin
  D2 "opencrawl-exporter" que publique sesiones de Tlamati a un servidor
  OpenCrawl vía su API/MCP. Solo si hay consumidor real (fundador en equipo).
  La captura de Tlamati ya existe localmente (session store C1 SQLite) —
  exportar es barato cuando se necesite.
- Contraste estratégico para el README de Tlamati (E4): OpenCrawl = memoria
  compartida entre agentes (capa horizontal); Tlamati = harness de UN agente
  (capa vertical). Son complementarios, no competidores. Su lema "your
  context moves with you" es el mismo local-first spirit.

RIESGOS: proyecto de 2 semanas, 57 estrellas, startup YC — puede pivotar o
morir (precedente cercano: Reasonix, donor de D2, murió el 12-nov). Por eso:
cero acoplamiento (integración solo vía MCP estándar) y NUNCA dependencia
dura. Self-host requiere un servidor serio (Postgres+Temporal+OpenSearch);
en una laptop solo el modo SQLite.
