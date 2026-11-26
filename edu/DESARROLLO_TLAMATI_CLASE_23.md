# CLASE 23 — El experimento perdido, el proceso colgado y el botón de pánico que no funcionaba

Sesión 25-nov-2026 (noche). Repo: ~/code/tlamati (rama spike/skillopt-v2, commit e4f93c9) y worktree ~/code/tlamati-ux (rama feat/stop-and-steer).

## (a) El problema: un README que mentía

Imagina que tu libro dice "los apéndices están en el anaquel 3" y el anaquel 3 no existe. Eso pasaba con el README de tlamati: prometía el experimento skillopt "vivo en la rama spike/skillopt con apéndices completos", pero la rama se perdió en el filter-repo (la cirugía que reescribe el historial de git para borrar secretos antes de publicar). El mandato del fundador: reconstruirlo, correrlo de nuevo, y esta vez dejar artefactos reales.

## (b) Qué entendimos hoy

**1. El humo colgado tenía DOS culpables, y el sospechoso principal era inocente.** El handoff apostaba por el sandbox (bwrap, la "jaula" que aísla los comandos del agente). Prueba directa: tlamati headless con y sin `--no-sandbox` → ambos responden en ~2.2s. Inocente. El culpable real: un `threading.Lock` (candado de exclusión: solo un hilo pasa a la vez) que `run_once()` tomaba y, adentro, llamaba a `_add_spend()` que tomaba el MISMO candado. Como Lock no es reentrante (no reconoce que el dueño ya está dentro), el hilo se espera a sí mismo para siempre. Deadlock: el cerrojo que no se abre desde adentro. Fix de una palabra: `threading.RLock()` (candado reentrante, cuenta las entradas del mismo dueño).

**2. La réplica NO reprodujo el efecto — y eso es el resultado.** 135 runs, $1.4383. S1.2 (22-nov) decía: skill mutada 97-100% vs base 83-90%, p=0.0085. La réplica: base flash 25/25 (100%) SIN skill → techo de efecto; mut2 cayó a 65% en coder (7 fallos, todos max_turns: la skill lo empujaba a buclear verificando). Fisher pooled p=0.867/0.955, gate DROP/DROP. La cadena honesta quedó completa: n=3 storytelling → n=10 p=0.24 → n=65 p=0.0085 → réplica DROP. El juez estadístico frenó por segunda vez una mutación que se habría llevado 20 puntos. Un benchmark que nunca puede dar negativo no es benchmark.

**3. Ctrl+C no funcionaba en la TUI porque el teclado estaba "secuestrado".** Textual (la librería de la interfaz) corre el terminal en modo raw: las teclas llegan como EVENTOS, no como señales del sistema. SIGINT nunca existía para el proceso; el contrato "ctrl+c x2 = abort" de loop.py era código muerto en la TUI. Y escribir a mitad de una corrida se descartaba EN SILENCIO (`if self._busy: return`).

## (c) Qué se construyó y cómo (replicable)

Fix del rig (~/code/tlamati, dev/spike_v2.py):
- `threading.Lock` → `threading.RLock` (deadlock)
- `subprocess.run(capture_output=True)` → `Popen` con stdout/stderr a archivos temp + `start_new_session=True` + `os.killpg(SIGTERM→SIGKILL)` en timeout. Regla: NUNCA pipes con timeout si puede haber nietos — el drenaje del pipe se bloquea si otro proceso lo hereda.
- proposer: max_tokens 1200→3000 (los modelos reasoning se gastan el presupuesto pensando y devuelven `content=None`), retry x3, mínimo 300 chars.
- `rate()` comparaba "flash" contra "qwen/qwen3.8-flash" → n=0. Comparar contra `MODELS[mkey]`.

Correr el experimento completo:
```bash
cd ~/code/tlamati && git checkout spike/skillopt-v2
.venv/bin/python dev/spike_v2.py --phase all      # ~$1.5-3, resumible
.venv/bin/python dev/spike_v2.py --phase report   # re-lee progreso, $0
```
Verificación: `dev/spike_v2_results.json` (tabla + Fisher + gate) y `dev/spike_v2_progress.json` (135 runs crudos). Apéndices: `dev/SPIKE_V2.md`.

Ctrl+C y steering (worktree ~/code/tlamati-ux, commit 0ce5e4e):
- `core/loop.py`: dataclass nueva `LoopControl` (abort: bool, pending_interjection: str|None) — canal UI→loop. `run_loop(..., control=ctrl)`. El abort se chequea entre deltas del stream (rescata el texto parcial), antes de cada tool y al inicio de turno → `stop_reason="aborted"`. El steering entra como user message al inicio del siguiente turno; si el modelo cierra con steering pendiente, se entrega y sigue (donor: mid-turn steering de Hermes).
- `tui/app.py`: `Binding("ctrl+c", "interrupt", priority=True)`; con corrida activa marca abort, en reposo cierra la app. Submit con `_busy` ya no descarta: encola + nota visible.
- Tests: +7 (ControlProvider scripteado en test_loop.py; Pilot + gate asyncio en test_tui_e1.py). Gate: 640 passed, ruff/mypy limpios.
- Instalar la versión nueva: `uv tool install --reinstall --force --python 3.12 "$HOME/code/tlamati-ux[tui]"` — sin `[tui]` pierde textual; sin `--python 3.12` resuelve con 3.11 y falla.

## (c2) La teoría detrás

**Rig resumible con evidencia cruda** (patrón de benchmarks serios, donor: terminal-bench): cada run se appendea a un JSON antes de seguir; si algo muere a mitad, se reanuda sin repetir gasto. El judge es un script externo (verify.py), nunca el self-report del agente.

**Fisher exacto pooled**: el test de Fisher pregunta "¿dadas las orillas de la tabla 2×2, qué tan extremo es este reparto?" sin aproximar (a diferencia de chi-cuadrada). "Pooled" junta ambos modelos en una tabla para ganar potencia. Lo implementamos con `math.comb` de la stdlib: 15 líneas, cero dependencias.

**LoopControl como "narrow waist"**: el loop no sabe que existe la TUI; la TUI solo muta un dataclass compartido (mismo hilo asyncio, sin locks). Es el mismo patrón de las señales, pero portable entre UIs: headless usa SIGINT, TUI usa LoopControl, los dos desembocan en el mismo campo `pending_interjection`.

**Worktree de git**: `git worktree add ~/code/tlamati-ux -b feat/stop-and-steer main` monta un segundo directorio de trabajo sobre el mismo repo — desarrollamos el feature UX SIN tocar el repo donde corría el bench de 2 horas. Pitfall confirmado: el symlink `.venv` se cuela al `git add -A` (el gitignore trae `.venv/` que no matchea symlinks); se saca con `git rm --cached` + amend, o se excluye en `.git/info/exclude`.

## (d) Qué decidimos NO construir

- NO arreglar el sandbox (era inocente — la prueba de 2 minutos nos ahorró "arreglar" lo que funcionaba).
- NO mergear feat/stop-and-steer a main sin que el fundador la pruebe primero (decisión pendiente, la rama está pusheada).
- NO re-benchear con más n para "rescatar" el efecto: con base 100% no hay efecto que rescatar; subir n solo gastaría dinero en confirmar el techo.
- CLASE_22.md quedó untracked a propósito: no es de esta sesión, no la tocamos.

## (e) El error del día

El smoke de la sesión anterior corrió 500s sin dejar NADA. Esta sesión, el primer intento de arreglarlo (Popen+killpg) NO bastó: se colgó otra vez. Lo que lo reveló: `faulthandler.dump_traceback_later(20, repeat=True)` — un vigilante que imprime el stack de Python cada 20 segundos si el proceso no termina. El stack señaló `_add_spend` línea 89 esperando un futex (el candado). Sin faulthandler habríamos seguido adivinando. Lección: cuando un proceso Python se cuelga sin evidencia, faulthandler es la autopsia en vivo. Y el meta-error: el handoff apostaba por el sandbox; la prueba barata primero (2 corridas de 2s) habría desmentido la sospecha el día anterior.

## (f) La pregunta abierta para mañana

mut2/coder falló 7/20 por bucles de verificación (max_turns). ¿Es la skill, o es que coder necesita SU propia variante de skill (las dos se propusieron desde fallos de flash)? Segunda fixture (ducto_reglas_l2, la pregunta de CLASE_19: ¿mut2 generaliza?) sigue sin respuesta. Y: ¿mergemos feat/stop-and-steer a main?
