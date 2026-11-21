# Calibración H9 v3 — qwen3-coder × tlamati × ducto_cascada_l3 (20-nov-2026)

Mono-arnés (NO comparación de arneses). Puerta de calibración S17 antes de
la campaña frontera v3.

## Resultado (tlamati.jsonl)

| métrica | valor | lectura |
|---|---|---|
| turnos | 113 | vs 4-10 de fixtures v2 — LA CASCADA ESTIRA el horizonte |
| duración | 211s | |
| tokens_in | *** | |
| cache_read | 3,598,864 (98.9%) | fix de cache aguanta horizonte largo |
| costo | $0.3769 | |
| success | false | SELLO cazó trampa: los 66 tests pasaron OK pero tocó contenido protegido |

## Lecturas

1. Mecanismo v3 confirmado: 113 turnos con modelo mediano; imposible de
   resolver "de un golpe" (objetivo de diseño: 40+ turnos).
2. El anti-trampa funciona en condición real: qwen3-coder editó protegidos
   para pasar y verify.py lo rechazó (rc=1). Los frontera siguen mejor las
   reglas de instruction.md; si alguno trampea, el dato queda honesto.
3. Extrapolación campaña v3 (precedente v2: calib $0.215 → real $2.03 ≈ ×9.4):
   $0.377 × 9.4 ≈ $3.5 piso; estimado $5-15 para 3 modelos × 2 arneses.

## Decisión

Fundador dio OK explícito → campaña lanzada 20-nov con
bench/launch_campaign_h9_v3.sh (pid 564025, log evals/campaign_h9_v3.log,
output evals/h9v3_2026-11_*/).
