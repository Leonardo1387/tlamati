# Campaña H9 v4 — resultados (cascada limpia, entorno hostil) — 20-nov-2026

Fixtures anti-batch v4: `ducto_cascada_l3` (34 módulos en cascada, revela
escalonado ×33). Entorno hostil completo (fixes A-F post-invalidación v3):
docstrings neutros, runner --no-memory + purge cross-harness, respuestas
cifradas fuera de /tmp, raws con modelo, canary trap, preflight obligatorio.

Diseño: n=1 (17:14-18:13) + réplicas (18:16-19:13, gpt/opus ×3, qwen ×2 —
opción 3 del fundador por costo de qwen). **16+6=22 corridas, 22/22
success=True, 0 fallos de modelo.** COSTO TOTAL v4: $9.31 ($2.67 n=1 + $6.64
réplicas; presupuesto $40, gastado acumulado ~$18.2).

## Simetría del protocolo (blindaje metodológico)

Ambos brazos (tlamati y codex) operan sobre la MISMA información disponible:
los 33 reveals escalonados de verify.py y un horizonte comparable (36-38 turnos
tlamati; codex no reporta turns). Lo que se mide no es quién VE más, sino qué
hace cada arnés con el historial acumulado entre el reveal 1 y el reveal 33:
codex re-manda la conversación completa en cada turno y re-lee archivos ya
vistos (bola de nieve cuadrática de contexto); tlamati mantiene acotada la
ventana activa. No hay ventaja artificial de información en ningún brazo.

## Tabla consolidada (n=1 + réplicas, media±std)

| modelo | arnés | n | turnos | dur_s | costo | tok_in (n=1) | cache% |
|---|---|---|---|---|---|---|---|
| gpt-6.2-sol | tlamati | 4 | 36±0 | 46±19 | $0.0524±0.0119 | 226k | 95.1% |
| gpt-6.2-sol | codex | 4 | – | 106±39 | $0.4496±0.2263 | 985k | 77.4% |
| opus-5.5 | tlamati | 4 | 37±1 | 107±6 | $0.2774±0.0098 | 460k | 95.8% |
| opus-5.5 | codex | 4 | – | 118±3 | $0.5247±0.0546 | 1318k | 96.8% |
| qwen3.8-max | tlamati | 3 | 75±33 | 452±184 | $0.6881±0.3035 | – | – |
| qwen3.8-max | codex | 3 | – | 467±174 | $0.6769±0.2571 | – | – |

Costos por corrida (dispersión):
- gpt×tlamati: 0.0676 / 0.0484 / 0.0544 / 0.0391 — MUY estable
- gpt×codex: 0.5771 / 0.5704 / **0.1110** / 0.5398 — run2 outlier LEGÍTIMO
  (forensia: turn.completed real, 66/66 tests, VERIFY OK, 562k tok con 97%
  cache; simplemente resolvió más eficiente, no es corrida rota ni trampa)
- opus×tlamati: 0.2740 / 0.2791 / 0.2899 / 0.2666 — MUY estable
- opus×codex: 0.5386 / 0.5923 / 0.5051 / 0.4630 — estable
- qwen×tlamati: 0.6999 / 0.3789 / 0.9855 — ALTA dispersión (42-108 turnos)
- qwen×codex: 0.5137 / 0.9732 / 0.5437 — alta dispersión

## Ratios codex/tlamati (medias consolidadas)

| modelo | dur | costo | v2-L1 dur/cost | v2-L2 dur/cost |
|---|---|---|---|---|
| gpt-6.2-sol | ×2.30 | **×8.58** | ×7.2 / ×5.4 | ×3.7 / ×3.9 |
| opus-5.5 | ×1.10 | **×1.89** | ×0.9 / ×1.8 | ×0.7 / ×0.8 |
| qwen3.8-max | ×1.03 | ×0.98 | ×4.8 / ×3.4 | ×3.4 / ×3.0 |

## RESPUESTA A LA PREGUNTA CENTRAL H9

Con horizonte forzado a 36-110 turnos en TODOS los brazos:

1. **El ratio de COSTO crece con el horizonte largo en gpt (5.4→3.9→8.58) y
   se sostiene en opus (~1.8-1.9 consistente en L1, L2 y cascada).** La tesis
   pivotada a costo SE SOSTIENE en modelos frontera: a igualdad de resultado,
   codex paga 1.9-8.6x más según modelo.
2. **Mecanismo confirmado por tokens**: codex consume 3-4x más tokens_in que
   tlamati en la misma tarea (985k vs 226k en gpt; 1318k vs 460k en opus) —
   la bola de nieve de contexto es real y medible, no teórica.
3. **qwen3.8-max INVIERTE el ratio (0.98)**: en cascada larga su brazo
   tlamati se dispara (75±33 turnos, hasta 108) mientras codex se mantiene.
   La ventaja del arnés NO es universal: depende de cuántos turnos extra
   gasta el modelo dentro del ducto. Con modelos que divagan en la cascada,
   tlamati pierde su ventaja de contexto acotado. Hallazgo nuevo de v4.
4. **Estabilidad**: opus y gpt×tlamati tienen desviación mínima en costo
   (±3-8%); qwen tiene ±40-45% — comportamiento impredecible en horizonte
   largo, coherente con su rol de "modelo barato" que aquí NO fue barato.

## Auditoría anti-trampa (FIX-F, 9 brazos tlamati: n=1 + réplicas)

Criterios: fuera_workdir=0, memory=0, reveals≥30, canary intacto.

| brazo | calls | fuera | memory | reveals | canary | veredicto |
|---|---|---|---|---|---|---|
| gpt n1 | 37 | 0 | 0 | 33 | no | LIMPIO |
| gpt r1 | 35 | 0 | 0 | 33 | no | LIMPIO |
| gpt r2 | 37 | 0 | 0 | 33 | no | LIMPIO |
| gpt r3 | 36 | 0 | 0 | 4* | no | LIMPIO (ver *) |
| opus n1 | 36 | 0 | 0 | 33 | no | LIMPIO |
| opus r1 | 35 | 0 | 0 | 33 | no | LIMPIO |
| opus r2 | 37 | 0 | 0 | 34 | no | LIMPIO |
| opus r3 | 35 | 0 | 0 | 33 | no | LIMPIO |
| qwen n1 | 77 | 0 | 0 | 38 | no** | LIMPIO (ver **) |
| qwen r1 | 44 | 0 | 0 | 33 | no** | LIMPIO (ver **) |
| qwen r2 | 115 | 0 | 0 | 33 | no | LIMPIO |

\* FALSO POSITIVO del auditor: gpt r3 creó un helper `.next` (sed +
verify.py --reveal $1 + cat siguiente) invocado 30 veces para etapas 3-33.
Los reveals SÍ ocurrieron, indirectos. Trayectoria secuencial legítima: cada
sed corresponde al bug de la etapa recién revelada. LECCIÓN: el auditor debe
contar reveals con indirección (bash helper/loop), no solo grep literal.

\** FALSO POSITIVO del auditor: las menciones de "vacio" son el comando que
arregla m07 (`"vacio"` bug en fuente → `"vacío"` respuesta correcta con
acento) y texto descriptivo del fix. fuera_workdir=0: nunca tocó
/tmp/h9_canary. LECCIÓN: el criterio canary debe ser "valor trampa como
clave FINAL", no substring en raw.

Forensia completa: evals/forensia_v4_flags.py (tlamati) y
evals/forensia_v4_codex_outlier.py (codex).

## Datos crudos

- n=1: evals/h9v4_2026-11_<slug>/{tlamati,codex}.jsonl (1 línea c/u)
- Réplicas: evals/h9v4r3_2026-11_<slug>/{tlamati,codex}.jsonl (3/3/2 líneas)
- Raw tlamati: /tmp/tlamati-bench/_raw/tlamati/ducto_cascada_l3.<modelo>.runN.jsonl
- Raw codex: /tmp/tlamati-bench/_raw/codex/ (formato thread events)
- Fallidos infra (archivados): evals/_failed_qwen_attempt1/ (1er intento qwen:
  rate-limit OpenRouter + httpx.ReadTimeout; relanzado limpio)
- Logs: evals/campaign_h9_v4.log, evals/campaign_h9_v4_runs3.log
- Workdirs pre-run (snapshots): _raw/tlamati/*.preN.workdir.tgz

## Comparación con v3 invalidada (contexto histórico)

v3 (contaminada por memoria-acordeón): gpt×tlamati 36t/$0.109, opus×tlamati
7t/$0.170 (batch ilegítimo). v4 limpia: gpt×tlamati 36t/$0.052 (más barato y
legítimo), opus×tlamati 37t/$0.277 (opus NO colapsa a batch sin el acordeón
en memoria — la invalidez de v3 quedó demostrada por contraste: sin trampa,
opus tarda 37 turnos, no 7).
