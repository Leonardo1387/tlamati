# SPIKE v2 — réplica del experimento skillopt (25-nov-2026)

Veredicto en una línea: **el efecto +12-14 puntos de S1.2 NO replica — pero el
mecanismo que importa (proposer + juez estadístico + gate) funcionó al pie de
la letra y frenó una mutación que habría degradado el rendimiento 20 puntos.**

## 1. Por qué existe este documento

El spike original (rama `spike/skillopt`, commit 6a50338) se perdió en el
filter-repo de sanitización pre-publicación de v0.1.0. El README siguió
prometiendo una rama y unos apéndices que ya no existían. Mandato del fundador
(25-nov): reconstruir el spike desde el diseño documentado (CLASE_18/19),
correrlo de nuevo, y dejar artefactos REALES y reproducibles.

Esto es una réplica de DISEÑO, no de código: las SKILL.md mutantes las volvió a
proponer el modelo desde cero (las originales no sobreviven). El protocolo es
fiel: misma fixture, mismos modelos, mismos brazos, mismo juez, mismo Fisher.

## 2. Protocolo

- Fixture: `fixtures/instruccion_en_archivo` — validador.py con 4 bugs contra
  SPEC.md (umbral 8→12, R2 sin minúsculas, R5 fuera de orden, falta R4).
- Juez: `python3 verify.py` en workdir fresco → "VERIFY OK" + exit 0. Nunca el
  self-report del agente.
- Harness: `tlamati -p ... --json` headless, HOME aislado, --no-memory,
  --approve-tool '*' (fixture propia y confiable), --no-subagents, sandbox ON
  (default; se verificó que no afecta: 2.2s con y sin --no-sandbox en la prueba
  de humo).
- Brazos: v0 (sin skill) · mut1 (checklist por regla: condición→fuente→código→
  prioridad) · mut2 (spec-first: leer SPEC completo y verificar contra verify.py
  antes de declarar éxito). Skills inyectadas vía `<workdir>/.tlamati/skills/`.
- Modelos: qwen/qwen3.8-flash (n=25/brazo, incluye 6 seeds) y qwen/qwen3-coder
  (n=20/brazo, incluye 4 seeds). max_turns=40, timeout 420s/run, concurrencia 3.
- Estadística: Fisher exacto unilateral (stdlib math.comb), por modelo y pooled.
  Gate: KEEP solo si p<0.05 Y el brazo no es peor que v0 en NINGÚN modelo.
- Resume: cada run se appendea a `spike_v2_progress.json`; corridas por fase
  (collect → propose → bench → report) reanudables.

## 3. Resultados (135 runs, ledger $1.4383)

| brazo | flash | coder | pooled | Fisher pooled (vs v0) | gate |
|---|---|---|---|---|---|
| v0 | 25/25 = **100%** | 17/20 = 85% | 42/45 = 93.3% | — | — |
| mut1 | 24/25 = 96% | 16/20 = 80% | 40/45 = 88.9% | p=0.867 | **DROP** |
| mut2 | 25/25 = 100% | 13/20 = **65%** | 38/45 = 84.4% | p=0.955 | **DROP** |

Turnos medios (éxito o no): flash v0 9.7 / mut1 9.4 / mut2 10.5; coder v0 20.1
/ mut1 21.9 / mut2 23.1. Anatomía de las 15 fallas: 14 max_turns + 1 error de
stream. Las 7 de mut2/coder son TODAS max_turns: la skill empujó al modelo a
bucles de verificación en vez de resolver.

Costos por fase: smoke $0.008 · seeds (10) $0.103 · propose (2 llamadas)
$0.004 · bench (125) $1.324. Duración media por run: 81s. Timeouts: 1 (run
legítimo, registrado como fallo). Errores de infraestructura: 0.

### Comparación con S1.2 (22-nov, n=65)

| métrica | S1.2 original | réplica v2 |
|---|---|---|
| v0 flash/coder | 82.9% / 90.0% | **100% / 85%** |
| mut ganadora | mut2 97.1%/100%, p=0.0085 | ninguna — gate DROP/DROP |
| mut perdedora | mut1 74.3%/80% (DROP correcto) | mut2 65% en coder (DROP correcto) |
| costo | $2.40 | $1.44 |

## 4. Lectura honesta

1. **Techo de efecto, no regresión del arnés.** flash resuelve 25/25 SIN
   skill; no hay espacio arriba donde una skill pueda demostrar mejora. La
   base se fortaleció entre el 22 y el 25 de noviembre (mismos modelos, mismo
   protocolo) — el efecto medido en S1.2 existía contra una base más débil.
2. **El gate es la tesis y se re-validó.** S1.2 demostró que el gate frena una
   mutación mala (mut1). La réplica demuestra que también frena una mutación
   que venía certificada como ganadora la semana anterior (mut2 habría costado
   20 puntos en coder). Sin juez estadístico, un arnés que se "automejora" se
   autodegrada — dos veces medido, dos veces cierto.
3. **Las skills tienen costo cuando la base ya es buena.** mut2/coder no solo
   falló más: tardó más turnos (23.1 vs 20.1). Instrucciones redundantes con
   lo que el modelo ya sabe hacer bien = fricción, no ayuda.
4. **Un benchmark que nunca puede dar negativo no es un benchmark.** La cadena
   completa n=3 ("+67 pts", storytelling) → n=10 (p=0.24, no significativo) →
   n=65 (p=0.0085, real pero modesto) → réplica (DROP: la base alcanzó el
   techo) ES el resultado. El rig costó $1.44 y dijo la verdad las 4 veces.

## 5. Bugs de infraestructura encontrados y arreglados (el spike como dogfood)

El smoke original se colgaba 500s sin dejar evidencia. Diagnóstico con
faulthandler: DOS bugs, ninguno era el sandbox (sospecha descartada con prueba
directa):

1. **Deadlock de lock no reentrante**: `run_once()` tomaba `threading.Lock` y
   adentro llamaba a `_add_spend()` que tomaba el MISMO lock → toda corrida
   con costo se colgaba al terminar. Fix: RLock.
2. **Riesgo de pipe-drain** (defensivo): `subprocess.run(capture_output=True,
   timeout=...)` puede bloquearse drenando pipes si un nieto los hereda. Fix:
   Popen + stdout/stderr a archivos temp + start_new_session + killpg.
3. **proposer con content=None**: qwen3.8-flash es modelo reasoning; con
   max_tokens=1200 se gastaba TODO el presupuesto pensando y devolvía
   content=None → crash. Fix: max_tokens=3000 + guarda defensiva + retry x3 +
   mínimo 300 chars para dar una propuesta por válida (mut2 salió truncada a
   181 chars en el primer intento).
4. **bug de claves en phase_report**: `rate()` comparaba la clave ("flash")
   contra el modelo completo guardado en progress ("qwen/qwen3.8-flash") →
   todo n=0. Fix: comparar contra MODELS[mkey].

## 6. Reproducir

```bash
cd ~/code/tlamati && git checkout spike/skillopt-v2
.venv/bin/python dev/spike_v2.py --phase all   # ~$1.5-3, ~2h, resumible
.venv/bin/python dev/spike_v2.py --phase report  # solo re-leer progreso
```

Requiere OPENROUTER_API_KEY (o ~/.hermes/.env). Artefactos:
`spike_v2_progress.json` (135 runs crudos), `spike_v2_results.json` (tabla +
Fisher + gate), `spike_v2_skill_mut{1,2}.md` (las propuestas del modelo),
`spike_v2_run.log`, `spike_v2_spend.json` (ledger por ítem).
