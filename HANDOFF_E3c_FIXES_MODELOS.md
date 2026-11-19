# HANDOFF E3c — fixes de igualdad + varianza + campaña de modelos
# Generado por Hermes, 19-nov-2026 (sesión 19). Para sesión con CERO contexto:
# leer este archivo completo + skill_view(name='tlamati-harness-project') +
# references/e3b-harness-bench.md, y ejecutar los 3 pasos EN ORDEN, uno por
# unidad (entrega → evidencia → OK verbal del fundador → merge → siguiente).
# Protocolo vigente: fundador NO-técnico (nunca pedirle diffs; evidencia de
# COMPORTAMIENTO en cristiano); Hermes auto-audita (pytest + ruff check +
# ruff format --check + mypy --strict + baseline real); clase al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_13).

## 0. ESTADO AL CIERRE DE LA SESIÓN 19 (verificado)

- Rama e3b-bench = 3f6557f PUSHEADO (ahead 0). Contiene: runner con
  --max-turns 50 + CODEX_HOME fuera de /tmp (5322f47), diagnóstico
  post-tabla (94d0b6f), bench/ + EVALS.md run1 (dfd208c) y la TABLA RUN2
  COMPLETA ya escrita en EVALS.md (3f6557f).
- RUN2 TERMINADA Y LIMPIA (19-nov, 40/40, watchdog bench/bench_watchdog.sh,
  cero 429/504, cero user_id filtrado — grep verificado):
    codex 10/10 (1.09M tok, 87% cache, 476s) · hermes 10/10 (null, 1245s) ·
    opencode 7/10 (383k, 84%) · tlamati 8/10 (735k, 98% cache, 239s).
  JSONL: evals/benchmark_2026-11-18_run2/. Tabla run1-vs-run2 + autopsias en
  EVALS.md §"Tabla RÉPLICA run2".
- PENDIENTE DE FUSIÓN: e3b-bench → main (necesita OK verbal del fundador;
  la evidencia ya le fue presentada en la sesión 19). Verificar antes:
  suite completa verde + `ruff format .` (CI scope = repo entero, incluye
  bloques ```python dentro de .md — pitfall E3a) + CI verde post-merge.
- main = 1821225+ (FASES A+B+C+D+E1/E2/E3a fusionadas; 375 tests).
- Untracked intencionales: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia
  rate-limit 16-nov, NO borrar ni commitear).
- FUNDADOR YA USA TLAMATI EN OTRA TERMINAL (dogfooding iniciado): instaló con
  `uv tool install --from . tlamati --reinstall` + `set -a; source
  ~/.hermes/.env; set +a`. OJO: sin el extra [tui] la TUI truena
  (ModuleNotFoundError textual) → comando correcto para él:
  `uv tool install --from ".[tui]" tlamati --reinstall`. La llave NO se pega
  en chat (redaction se come el $(grep...)): siempre indicar `set -a; source`.

## DIAGNÓSTICOS CLAVE DE LA RUN2 (con evidencia, no especulación)

1. tlamati/instruccion_en_archivo = TRAMPA PROPIA (asimetría eval-arnés):
   el modelo llama enter_plan_mode solo; en headless NO hay aprobador y
   exit_plan_mode es fail-closed por diseño (regla de oro C5) → quedó
   ENCERRADO: 4 intentos de salida fallidos (turnos 6/9/15/22), escrituras
   denegadas, 50 turnos quemados. Evidencia forense: ledger
   ~/.local/share/tlamati/audit.db sesión 20261119-120939-07919bc5
   (columnas: seq,ts,session_id,turn,tool,args_json,decision,result_sha256,
   is_error,untrusted,truncated — OJO nombres exactos, no 'session'/'tool_name').
   DECISIÓN DEL FUNDADOR (sesión 19, NO re-litigar): "no es un bug para uso
   real (la TUI sí tiene aprobador), pero quiero fixes para que el arnés
   empate sin importar el tamaño del cerebro". NO se arregla inflando el
   prompt: se arregla NO ofreciendo una puerta sin salida.
2. tlamati/multi_archivo = fallo de RAZONAMIENTO DEL MODELO (usó impuesto
   0.16 default en vez del 0.19 del config; verify.py lo cazó con valores
   exactos). Misma falla en run1; el re-test diagnóstico del 18-nov la pasó
   (8 turnos). 2 fallos de 3 corridas. El arnés NO ocultó nada: el config
   estaba legible. Prohibido dopar la fixture (reglas anti-cheating E3b).

## PASO 1 — FIX PLAN-MODE HEADLESS (producto + runner + test)

Rama: e3c-planmode-fix (sale de e3b-bench o main según estado del merge).

a) PRODUCTO (src/tlamati/cli.py ~línea 572-576): hoy
   `tool_list.extend(make_plan_tools(Path.cwd(), plan_state, plan_approver=None))`
   expone enter/save/exit_plan_mode SIEMPRE. CAMBIO: solo exponer las plan
   tools cuando exista aprobador humano real (TUI interactiva o --plan-mode
   explícito con tty/aprobador); en headless sin aprobador NO se ofrecen y se
   imprime aviso honesto a stderr ("[plan] tools de plan no ofrecidas: sin
   aprobador humano en esta corrida"). IMPORTANTE cache sagrada: el bloque
   PLAN_MODE_PROMPT del prefijo es ESTÁTICO por diseño (decisión C5 #3) —
   si al quitar las tools el bloque de prompt queda mentiroso, quitar TAMBIÉN
   el bloque solo cuando no hay plan tools, y verificar con smoke $0
   (OPENROUTER_API_KEY=*** el prefijo se construye antes del 401; técnica
   Clase 7) que el prefijo byte-idéntico se conserva entre corridas del
   MISMO modo. Medir el delta de tokens del cambio con el smoke.
b) RUNNER (bench/runner.py _cmd_tlamati ~línea 103): añadir "--no-plan-mode"
   SI el flag existe, o el equivalente que resulte de (a) — el objetivo es
   igualdad de circunstancias: ningún arnés ofrece plan-mode en el bench.
   Documentar en EVALS.md (nota de asimetría corregida + fecha).
c) TEST de reproducción: headless sin aprobador → plan tools ausentes del
   tool_list; con aprobador (script) → presentes. + test de que
   --plan-mode sin aprobador sigue fail-closed (no relajar la regla de oro).
d) Re-corrida de SOLO instruccion_en_archivo con tlamati (centavos):
   `python3 bench/runner.py --harnesses tlamati --tasks instruccion_en_archivo`
   → esperado: corre normal (el diagnóstico del 18-nov la pasó en 12 turnos).
e) Auditoría completa (suite + lint trio sobre `.` entero) → evidencia de
   comportamiento al fundador → OK verbal → merge.

## PASO 2 — SONDA DE VARIANZA multi_archivo (N corridas)

Objetivo: distinguir "mala suerte" de "sistemático" con DATOS antes de tocar
el prefijo. Correr la fixture N=5-10 veces SOLO con tlamati (centavos cada
una; decisión fundador: corridas de centavos NO requieren OK adicional ni
madrugada si upstream sano — sonda --probe primero). Registrar en una tabla
EVALS.md §"Sonda de varianza": pases/fallos + turnos + qué constante usó cada
fallo. SI resulta sistemático (>50% fallos): proponer al fundador una mejora
GENÉRICA de prefijo (p.ej. regla universal "verifica tu cambio con los
tests/verify antes de terminar" — buena práctica, NO pista de fixture),
medir su costo en tokens con smoke $0, re-correr TODA la tabla desde cero
(nunca cherry-pick) y documentar. Si NO es sistemático: no tocar nada, el
dato publicado es la varianza medida.

## PASO 3 — CAMPAÑA DE MODELOS (cotización APROBADA por el fundador, sesión 19)

Misma tabla 4 arneses × 10 fixtures, MISMO runner, solo cambia el modelo.
Precios VERIFICADOS en vivo en OpenRouter (19-nov):

  MODELO                     $/M in   $/M out   $/M cache-read   nota
  qwen/qwen3.8-flash          0.15     0.47       0.016         sonda barata (~$0.05 solo-tlamati)
  deepseek/deepseek-v3.2      0.26     0.38       0.13          671B MoE (DeepSeek NO tiene 1T+)
  moonshotai/kimi-k2.7-code   0.65     3.50       0.16          1T MoE = el "1T+" real

Presupuesto total campaña (3 modelos, tabla completa ×2 réplicas): $5-6;
techo de paranoia $20. ORDEN: sonda qwen3.8-flash solo-tlamati → tabla
completa flash → deepseek → kimi. Directorios:
evals/benchmark_<fecha>_<modelo>/ (nunca mezclar con la tabla qwen3-coder
existente; cada modelo = tabla nueva fechada, regla de honestidad).
Runner: probablemente haya que parametrizar el modelo por arnés
(opencode: -m openrouter/<id>; codex: config.toml model=; tlamati: --model;
hermes: -m). Verificar en bench/runner.py cómo se fija hoy qwen3-coder y
generalizar SIN romper la reproducibilidad de las tablas viejas.
TESIS DEL FUNDADOR (el "golazo"): si tlamati empata 10/10 con un cerebro
mediano/grande Y conserva cache_read >90% (vs 84-87% de los demás), la tabla
publicable = "mismo % resueltas, 2-3× menos tokens, mejor cache" — formato
caso dirac (+17pts harness-only) en versión eficiencia. Bonus: si
multi_archivo la pasa el cerebro grande con nuestro prefijo ligero, queda
segunda evidencia de que el fallo era del modelo, no del arnés.

## PITFALLS NUEVOS DE LA SESIÓN 19 (sumar a la lista de la skill)

1. Nombres de columnas del ledger: session_id/tool (NO session/tool_name) —
   PRAGMA table_info antes de queryear audit.db.
2. `uv tool install --from . tlamati` SIN `.[tui]` → TUI truena con
   ModuleNotFoundError textual (el extra opcional es por diseño, decisión E).
3. La redaction del chat se come `$(grep '^OPENROUTER_API_KEY' ...)` al
   pegarlo al usuario → indicar SIEMPRE `set -a; source ~/.hermes/.env; set +a`.
4. El fundador pega errores de SU terminal en el chat: leerlos antes de
   asumir (el "error" de checkout era EVALS.md sin commitear por Hermes).
5. hermes en el bench run2 tardó 1245s (vs 206s run1) — duración de hermes
   NO es comparable entre corridas (sin telemetría); reportar crudo, sin narrativa.

## AL CIERRE

CLASE_13 "el delta como argumento" (tema natural: run1-vs-run2, la autopsia
del ledger que cazó la encerrona del plan-mode en 3 consultas SQL, y por qué
un benchmark honesto publica sus números feos CON diagnóstico). Tras el merge
de e3b: E4 (docs + SECURITY + auditoría de cobertura feature×arnés-donor —
ver conversación sesión 19, el fundador pidió verificar que se integró todo
lo importante de los 8 arneses; harness2 documentado como v2 COULD) +
sanitizar user_id en JSONL de errores 429 ANTES de hacer público el repo +
tag v0.1.0 + PyPI (nombre libre verificado 14-nov). DOGFOODING en paralelo:
el fundador YA tiene tlamati instalado y lo usa en otra terminal; acordado:
comparar sesiones tlamati-vs-hermes sobre tareas reales de NeoNubeInt midiendo
% resueltas, tokens, cache, turnos, costo, aprobaciones del ledger (métricas
propuestas en sesión 19, el fundador las dio por buenas; research/08 ya cubre
la investigación de "qué miden los benchmarks importantes" — NO hace falta
investigación nueva de blogs, decisión fundador sesión 19).

-- Hermes, sesión 19 (19-nov-2026). e3b-bench = 3f6557f pushed; run2 limpia
-- 40/40; siguiente: merge tras OK verbal → PASO 1 (plan-mode fix). --
