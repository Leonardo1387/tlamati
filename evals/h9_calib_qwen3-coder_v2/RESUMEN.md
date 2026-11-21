# Calibración qwen3-coder × tlamati — fixtures H9 v2 (20-nov-2026 11:30)

Pre-campaña obligatoria (regla de reporte de gasto) antes de lanzar la campaña
frontera H9 con gpt-6.2-sol / claude-opus-5.5 / qwen3.8-max sobre las fixtures
ANTI-BATCH v2 (cadena_defectos_l1: 45 defectos divergentes; ducto_reglas_l2:
migración no-uniforme).

| fixture | success | turnos | duración | tokens_in | cache_read | costo |
|---|---|---|---|---|---|---|
| cadena_defectos_l1 | true | 36 | 108s | 535k | 508k (95%) | $0.062 |
| ducto_reglas_l2 | true | 67 | 122s | 1.41M | 1.38M (98%) | $0.152 |

Lectura:
- NO hay colapso con qwen3-coder: 36 y 67 turnos reales de trabajo (el techo
  son 120). La fixture v2 anti-batch obliga a iterar defecto por defecto.
- Cache Anthropic/OpenAI-compat funcionando: 95-98% cache_read → el fix del
  20-nov se sostiene en horizonte largo.
- Costo total calibración: $0.215. Extrapolación campaña completa (3 modelos
  × 2 arneses × 2 fixtures): los frontera (gpt/opus) cuestan ~5-15× el qwen →
  cota superior estimada < $15, muy dentro de los $40 aprobados.

Generadores de fixtures (fuera del repo a propósito): /tmp/gen_h9_v2.py,
/tmp/emit_h9.py, verificación /tmp/hermes-verify-l1l2-v2.py (440 tests pytest
+ ruff limpios sobre este árbol).
