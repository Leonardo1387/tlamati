# INFORME CONSOLIDADO — tlamati vs codex vs hermes vs opencode

Fecha: 20-nov-2026. Fuentes: datos PROPIOS de este repo (todas las corridas
ejecutadas en la misma máquina WSL2, mismo modelo qwen/qwen3-coder vía
OpenRouter salvo H9-frontera). JSONL crudos en evals/. Este informe no
incluye datos externos (ver sección final sobre esa posibilidad).

## 1. Qué se midió y con qué rigor

Tres corpus, complejidad creciente:

| corpus | fixtures | horizonte típico | réplicas | arneses |
|---|---|---|---|---|
| lite (18-nov) | 10 (5 fáciles + 5 duras) | 4-23 turnos | ×2 corridas | 4 |
| E3c (19-nov) | 15 (+5 de robustez) | 4-30 turnos | ×3 | 4 |
| H9 v2 (20-nov) | 2 anti-batch (L1/L2) | frontera colapsa a 4-10t | ×1 y ×3 | 2 (tlamati/codex) × 3 modelos frontera |
| H9 v4 (20-nov) | ducto_cascada_l3 (34 módulos, revelado runtime) | 36-110 turnos forzados | n=1 + ×3/×2 | 2 × 3 modelos frontera |

Reglas anti-cheating (donor: debugml.github.io/cheating-agents): instrucción
única, verify.py decide el éxito, timeouts idénticos, cero configuración
especial, fallos upstream filtrados y reportados aparte.

## 2. RESULTADO CENTRAL — corpus E3c (15 fixtures × 3 réplicas, qwen3-coder)

| arnés | corridas OK | de 15 (todas ×3) | costo | tokens_in | dur total |
|---|---|---|---|---|---|
| **tlamati** | 37/45* | 11/15 | **$0.18** | **1.39M** | 16.9 min |
| opencode | 42/45 | 13/15 | $0.49 | 4.05M | 17.3 min |
| codex | 43/45 | 14/15 | $0.86 | 7.35M | 38.0 min |
| hermes | 45/45 | 15/15 | n/d** | n/d** | 40.0 min |

\* Los 8 fallos de tlamati son TODOS rc=4 "Provider returned error"
(OpenRouter indigestado en esa ventana) — fallos de infraestructura, no del
arnés. Al-menos-una-réplica: tlamati 14/15.
\** hermes one-shot no expone tokens/costo — solo % resueltas y duración.

Lectura: tlamati resolvió con **5.3x menos tokens que codex**, **2.9x menos
que opencode**, al menor costo y menor duración. hermes resolvió todo (45/45)
pero tardó 2.4x más que tlamati. codex y hermes son los más fiables en
términos absolutos; tlamati es el más eficiente por unidad de trabajo.

## 3. Horizonte largo con modelos FRONTERA (H9 — solo tlamati vs codex)

hermes/opencode NO corrieron en H9 (hermes por decisión de costo/tiempo del
fundador; opencode fuera del alcance frontera). Con gpt-6.2-sol, opus-5.5 y
qwen3.8-max sobre ducto_cascada_l3 (34 módulos, revelado escalonado runtime,
entorno hostil anti-trampa auditado):

| modelo | ratio costo codex/tlamati | ratio duración |
|---|---|---|
| gpt-6.2-sol | **×8.58** (tlamati gana) | ×2.30 |
| opus-5.5 | **×1.89** (tlamati gana) | ×1.10 |
| qwen3.8-max | ×0.98 (INVERTIDO) | ×1.03 |

Mecanismo verificado por tokens: codex re-manda el historial completo y
re-lee archivos entre etapas (bola de nieve cuadrática; 985k-1.32M tok_in vs
226k-460k de tlamati para el mismo resultado). La ventaja del arnés depende
del modelo: con qwen3.8-max (que divaga, 75±33 turnos) se evapora.

22/22 corridas success=True, $9.31 gastados, auditoría anti-trampa limpia en
los 11 brazos tlamati (0 lecturas fuera del workdir, 0 memoria, canary
intacto; 2 banderas investigadas = falsos positivos del auditor).

## 4. Conclusión por arnés

**tlamati** — El más eficiente del panel cuando el proveedor está sano:
menor costo, menor tiempo y 3-5x menos tokens que codex en TODOS los corpus,
ventaja que CRECE con el horizonte largo en modelos frontera (×3.9→×8.6 en
gpt). Debilidades honestas: (a) 7-8/15 en corrida única lite por varianza del
modelo con prefijo mínimo (las fixtures duras exigen más contexto del que el
minimalismo ofrece — re-test diagnóstico pasó las 3); (b) la encerrona del
plan-mode headless (asimetría eval-arnés, fix de una línea pendiente);
(c) con modelos que divagan (qwen3.8-max) la ventaja se invierte.

**codex** — El más fiable en tasa bruta (43-45/45) junto a hermes, y el único
que nunca falló por razones de arnés. Pero paga la bola de nieve de contexto:
4.8x el costo de tlamati en E3c ($0.86 vs $0.18) y 1.9-8.6x en frontera con
horizonte largo. En frontier+cascada, codex NUNCA gana en costo.

**hermes** — 45/45 en E3c, el único perfecto en el corpus ampliado. No expone
tokens/costo (limitación de medición, no virtud). Es el más lento (40 min,
2.4x tlamati). Su perfil: máxima resolución, sin datos de eficiencia —
no comparable en el eje que mide este benchmark (contexto/costo).

**opencode** — Punto medio consistente: 42/45 en E3c, $0.49 (2.7x tlamati),
4.05M tokens (2.9x tlamati), duración similar a tlamati. Sin fallos
sistemáticos propios; su varianza es del modelo.

## 5. Afirmación defendible (una línea)

Con el mismo cerebro (qwen3-coder), tlamati resuelve las tareas al ~21% del
costo de codex y al 37% del de opencode arrastrando 3-5x menos contexto;
con cerebros frontera en horizonte largo forzado, la ventaja de costo crece
(×8.6 en gpt-6.2-sol, ×1.9 en opus-5.5) y se invierte solo cuando el modelo
divaga (qwen3.8-max ×0.98). hermes resuelve todo pero no expone métricas de
eficiencia y es el más lento.

## 6. Caveats (honestidad completa)

- n=1 por celda en lite; E3c ×3; H9-v4 ×3/×2. Las celdas de corrida única
  se mueven ±3 (documentado en EVALS.md).
- Un solo modelo no-frontera (qwen3-coder) en la comparación de 4 arneses.
  La extensión frontera es solo tlamati vs codex.
- hermes corrió con --safe-mode (arnés pelón): no es la configuración de un
  usuario real con skills/memoria.
- Costos = precios OpenRouter del 18-20-nov-2026; cache_read factura ~10%.
- Duración hermes no comparable entre corridas (heurísticas propias).

## 7. Datos externos de otros arneses (propuesta, NO incluida)

Idea del fundador: incorporar al informe benchmarks públicos donde OTROS
arneses (claude code, aider, gemini-cli, grok build...) se midieron contra
codex, y usar codex como puente para posicionar tlamati indirectamente —
marcando cada cifra como EXTERNA. Ancla existente: Terminal-Bench 4.1
(tbench.ai) ya es matriz arnés×modelo; caso dirac (HN 47920787): agente OSS
65.2% vs agente oficial Google 47.8% con el mismo Gemini-3-flash (+17pts
harness-only). Reglas para hacerlo con rigor: (1) NUNCA promediar externo con
propio en la misma tabla; (2) columna "fuente" + fecha + fixture distinta en
cada fila; (3) el puente solo es válido si el codex-externo y el codex-propio
son versiones/fechas comparables — si no, presentar como contexto separado.
Detalle y fuentes: research/08_BENCHMARKS_EXISTENTES.md.
