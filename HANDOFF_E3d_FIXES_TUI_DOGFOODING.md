# HANDOFF E3d — FIXES DE DOGFOODING TUI (ultra-simplicidad para primerizos)
# Generado por Hermes, 19-nov-2026 (sesión 20). Para sesión con CERO contexto:
# leer este archivo completo + skill_view(name='tlamati-harness-project') +
# references/e3b-harness-bench.md. Ejecutar los pasos EN ORDEN, uno por unidad
# (entrega → evidencia de COMPORTAMIENTO en cristiano → OK verbal → merge).
# Protocolo: fundador NO-técnico (nunca diffs; Hermes auto-audita con pytest +
# ruff check + ruff format --check sobre `.` entero + mypy --strict + tests).
# Clase al cierre: edu/PROMPT_CLASE_DIARIA.md v2 (siguiente número tras CLASE_13).

## 0. ESTADO AL CIERRE DE LA SESIÓN 20 (verificado)

- Rama e3b-bench = e3cb7e7 (commit E3c: fix plan-mode headless + 5 fixtures de
  robustez + runner con --runs/--model/cost_usd). NO pusheado todavía en el
  momento de escribir esto — verificar `git status` y pushear la rama.
- main = eb39255+ (pendiente merge de e3b-bench; el handoff E3c sigue vigente
  para lo que falte de sus pasos 2-3).
- FIX PLAN-MODE HECHO Y VERIFICADO (sesión 20): headless sin --plan-mode ya NO
  ofrece enter/exit_plan_mode ni el bloque PLAN_MODE_PROMPT (puerta sin salida
  eliminada; regla de oro C5 intacta con --plan-mode explícito). Prueba real:
  instruccion_en_archivo pasó en 25 turnos / $0.02 (antes quemaba 50 encerrado).
  5 tests en tests/test_plan_mode_headless_e3c.py.
- 5 FIXTURES NUEVAS (propuesta del fundador, todas validadas: semilla FALLA
  pre-fix + solución de referencia PASA, ejecutado real): anti_bucle_imposible
  (abortar limpio = éxito, inventar = fallo), context_rot_20_archivos (20 ruido
  + 3 reales), recuperacion_test_roto (env limpio en verify), edicion_quirurgica
  _grande (591 líneas, hash sha256 sella todo fuera de las 2 funciones),
  rollback_o_regresion (6 tests, 5 pasan 1 falla). 10 tests nuevos en
  tests/test_evals.py. Suite total: 385 verdes.
- BENCH E3c EN CURSO al cierre (background, NO matar si sigue vivo — verificar
  con `ps aux | grep bench/runner`): 4 arneses × 15 fixtures × 3 runs →
  evals/benchmark_2026-11-19_e3c/ (+ run.log). PARCIAL tlamati: 37/45 OK,
  11/15 todas-las-réplicas (14/15 al menos una), $0.18, 1014s±39. anti_bucle
  PASÓ 3/3 en 4-5 turnos (el detector de estancamiento que pidió el fundador
  funciona). anti_bucle/context_rot/edicion_quirurgica/rollback nuevas = datos
  frescos. AL TERMINAR: leer run.log completo, armar tabla EVALS.md §E3c con
  pass@1 (todas-las-réplicas), costo USD real por arnés, y presentar evidencia.
- El binario instalado del fundador (`uv tool install --from ".[tui]" tlamati
  --reinstall --python 3.12`) YA incluye el fix plan-mode. Su shell tenía
  python3.11 activo → por eso falló su instalación manual (pitfall: exigir
  --python 3.12 o deactivate del venv viejo).

## 1. AUTOPSIA DE LA PRIMERA SESIÓN REAL DE DOGFOODING (fundador, TUI, video)

Evidencia forense: sessions.db sesión 20261119-132656-c8ca6a6b (197 msgs) +
audit.db turn_costs (98 llamadas, 2.74M tok_in, 94% cache, $0.33, 31.6 min).
El fundador pidió un video doodle 9:16 estilo NVIDIA (skill
doodle-blackboard-video existente en ~/.hermes/skills). Resultado: REPROBADO —
video mal hecho, audio cortado a 50s de 87.8s, experiencia pesada, se frenó a
los 20 turnos y hubo que reiniciar manual. 5 causas raíz CON EVIDENCIA:

1. SKILLS NUNCA CARGARON (causa madre): el fundador lanzó
   `tlamati --skills-dir ~/.hermes/skills` PERO LA TUI IGNORA ESE FLAG
   (src/tlamati/tui/app.py ~línea 303: SkillLibrary(default_skill_roots(
   self.workdir, [])) — lista extra vacía, hardcodeada). skill_list respondió
   "(sin skills instaladas)" (seq 4 y 62). El modelo intentó arreglarlo con
   `cp -r ~/.hermes/skills/* ./skills/` (seq 15) — carpeta que NO es raíz de
   skills. skill_view con nombre falló y su mensaje de error listó
   "Disponibles: " VACÍO (bug menor del mensaje).
2. SIN SKILL = SIN PIPELINE: la skill manda Whisper sobre el MP3 para
   timestamps; el modelo fabricó timing.json a mano (seq 139).
3. AUDIO CORTADO: narración real 87.8s (ffprobe seq 137) pero timeline.json
   decía "50s" desde ANTES de conocer el audio (seq 43) → ffmpeg -t 50 (seq
   184) cortó la voz a la mitad. La skill Hermes tiene pitfall explícito
   contra esto; sin skill cargada, sin defensa.
4. MURO DE 20 TURNOS: src/tlamati/tui/app.py ~línea 210: self.max_turns = 20
   HARDCODEADO (headless sí acepta --max-turns). La sesión lo topó → frenazo
   seco → reinicio manual del fundador.
5. VERBOSIDAD DE PLANEACIÓN: 7 archivos de planeación (script/storyboard/
   production_notes/asset_list/timeline/checklist/build_instructions, seq
   33-46) antes de tocar un pixel — síntoma de modelo sin procedimiento
   cargado (parte es qwen3-coder, parte es la falta de skill).

LO BUENO QUE MOSTRÓ (ser justos, reportar al fundador): se recuperó SOLO del
sandbox EROFS en /tmp (3 intentos → TMPDIR=./tmp, seq 151-163); encontró el
MP3 en /mnt/c/Users/Admin/Desktop solo (seq 131-133); cache 94% en sesión
larga multi-turno; edit fuzzy falló 1 vez (seq 100) y fallback read+write
correcto. El arnés NO perdió por tokens ni herramientas: perdió por 2 bugs de
producto (skills TUI + muro turnos) que causaron la falla en cadena.

## 2. VISIÓN DEL FUNDADOR (declarada sesión 20 — NO re-litigar, es el norte)

Verbatim (resumido fiel): "la idea de este arnés es que sea para personas que
van a usar una herramienta así por primera vez, entonces debe de ser muy
sencillo... más adelante sería interesante integrar una especie de tutorial de
inicio: eliges si eres principiante o no la primera vez, y si eres principiante
el agente te va llevando paso a paso con el setup (es recomendable descargar
tal y tal para navegar libremente, el repositorio REA si quieres trabajar con
aplicaciones...)". Y la prioridad INMEDIATA: "primero necesito que sea ultra
sencillo poder mover el cerebro al que apunta hermes a tlamati, y que tlamati
tenga ojos sobre mis archivos en la computadora, así como aquí contigo: si pego
una dirección de archivo, que la pueda encontrar y ver fácilmente. Aparte los
skills".
TRADUCCIÓN OPERATIVA (3 pilares de adopción, en este orden):
  P1. CEREMONIA CERO CON HERMES: reusar el cerebro/config/skills de Hermes sin
      fricción (migración 1-flag ya probada en headless C3; falta TUI).
  P2. OJOS A LOS ARCHIVOS DEL USUARIO: rutas Windows pegadas tal cual
      (C:\Users\Admin\Desktop\x.txt) deben resolverse a /mnt/c/... — hoy falla
      (seq 21-22: "no such file: /home/usuario/C:\Users\...").
  P3. ONBOARDING/TUTORIAL (DESPUÉS, no ahora): primera corrida pregunta nivel y
      guía setup. Documentar como F16 en PRD (COULD/SHOULD) para no perder la
      idea; NO implementar en esta fase.

## 3. PASO A — SKILLS EN LA TUI + CEREMONIA CERO (P1)

Rama nueva e3d-tui-skills (sale de e3b-bench si aún no mergea a main).

a) TUI: leer --skills-dir y config skills.extra_dirs IGUAL que headless
   (cli.py ~552-568 es la referencia de comportamiento). El app de Textual
   recibe los flags por argv — revisar cómo run_tui recibe args en cli.py
   (main() ~línea 802) y pasar extra_dirs. Sin bandera = raíces default
   actuales (prefijo byte-idéntico, test con FakeProvider).
b) RAÍZ HERMES POR DEFAULT (decisión de diseño propuesta, confirmar con el
   fundador antes de codificar — es comportamiento visible): añadir
   ~/.hermes/skills como raíz de descubrimiento SIEMPRE que exista, al FINAL
   del orden (project > user > hermes), de modo que `tlamati` a secas ya vea
   las skills de Hermes = ceremonia cero real. Alternativa más conservadora:
   `tlamati skills link ~/.hermes/skills` que crea symlink en
   ~/.local/share/tlamati/skills. PREGUNTAR al fundador cuál prefiere con
   explicación en cristiano (opción A recomendada: cero comandos).
c) BUG MENOR: mensaje de error de skill_view cuando la librería está vacía
   ("Disponibles: " sin nada) → texto honesto: no hay raíces configuradas +
   hint del flag.
d) Tests: catálogo visible en TUI con skills-dir extra (patrón test_tui_e1.py,
   run_test headless $0); roots con dir hermes simulado en tmp_path.

## 4. PASO B — MURO DE TURNOS EN TUI (P1, experiencia)

a) max_turns configurable: --max-turns en TUI (mismo flag que headless) +
   config general max_turns; default TUI sube de 20 a 50 (igualar headless;
   la decisión vieja de 20 fue arbitrary default de E1).
b) COMPORTAMIENTO AL TOPAR (importante para primerizos): hoy es frenazo seco.
   Cambiar a: mensaje claro en el chat de la TUI — "Límite de N turnos
   alcanzado. Escribe 'continúa' para seguir donde quedamos" — y que el
   siguiente mensaje del usuario reanude la corrida con la historia intacta
   (la sesión C1 ya persiste; es re-entrar al loop con history=). NO auto-
   continuar infinito (presupuesto sagrado).
c) Tests: tope dispara el mensaje (FakeProvider scriptado que quema turnos);
   reanudar tras el tope conserva historia.

## 5. PASO C — OJOS A ARCHIVOS WINDOWS (P2)

a) NORMALIZACIÓN DE RUTAS en read_file/search_files/terminal (tools/builtin.py):
   si el path empieza con letra+":" (C:\, D:/...) → traducir a /mnt/<minúscula>/
   + backslashes a slashes. Idempotente (rutas /mnt/c/... intactas). Falla
   honesta si el punto de montaje no existe (no es WSL).
   OJO: sandbox bwrap monta el fs read-only — verificar que /mnt/c sea visible
   dentro de la jaula (prueba real: read_file de un archivo Windows con sandbox
   activo; si bwrap no lo expone, ajustar sandbox/sandbox.py binds).
b) Bonus mismo paso: ~ del usuario ya funciona; añadir detección de "Desktop"
   NO (fuera de scope — la normalización C:\Users\... resuelve el caso real).
c) Tests: unit de la función de normalización (C:\, D:/, /mnt/c intacto,
   relativo intacto) + integración read_file con archivo sembrado en
   /tmp/mnt-fake (monkeypatch del prefijo /mnt si hace falta).

## 6. PASO D — PRD F16 (documentar el onboarding, NO implementar)

Añadir a PRD_TLAMATI.md la feature F16 "onboarding guiado por nivel" (COULD
v2): primera corrida detecta config ausente → pregunta nivel (principiante/
técnico) → checklist de setup (proveedor+llave, herramientas recomendadas,
REA opcional, skills). Dejar constancia de la visión del fundador (sesión 20)
para que no se pierda. Sin código.

## 7. PENDIENTES HEREDADOS (handoff E3c, seguir vigentes)

- Merge e3b-bench → main tras OK verbal del fundador (evidencia run2 YA fue
  presentada en sesión 19; la sesión 20 añadió el fix plan-mode + fixtures).
- E3c PASO 2 (sonda varianza multi_archivo N=5-10) y PASO 3 (campaña modelos
  flash→deepseek→kimi, presupuesto $5-6 techo $20, precios verificados en la
  tabla PRICES de bench/runner.py).
- Tabla E3c (4×15×3) al terminar el bench → EVALS.md.
- E4 (docs + SECURITY + auditoría cobertura + sanitizar user_id + v0.1.0
  público + PyPI) DESPUÉS de todo lo anterior.
- CLASE_13 "el delta como argumento" pendiente; esta sesión 20 suma material
  (autopsia de dogfooding real: cómo 2 bugs de producto explican un video
  reprobado, con ledger como evidencia).

## 8. PITFALLS NUEVOS (sesión 20, sumar a la skill al cerrar)

1. `uv tool install` con python3.11 activo en el shell → "requires Python>=3.12"
   confuso; fix: --python 3.12 explícito (o deactivate el venv viejo).
2. ruff format `.` REESCRIBE fixtures/*.py → rompe hashes sha256 sellados en
   verify.py (edicion_quirurgica) y strings de reemplazo de los tests de
   solución. REGLA: correr ruff format ANTES de calcular hashes; y si se
   formatea después, recalcular el hash y revalidar el ciclo completo
   (semilla falla / fix pasa / corrupción detectada).
3. `2>dir/log` falla si el dir no existe aún y el proceso lo crea — mkdir -p
   primero (el primer intento del bench murió así, rc=1, sin gastar tokens).
4. shutil.copytree del runner ahora ignora __pycache__/*.pyc (fixtures con
   pycache viejo sembraban ruido en los workspaces).
5. La TUI y el headless COMPARTEN features pero no flags: cada feature de CLI
   DEBE verificarse en ambos caminos (skills-dir existía en headless desde C3
   y la TUI nunca lo recibió — el fundador lo descubrió usándolo).

-- Hermes, sesión 20 (19-nov-2026). e3b-bench = e3cb7e7; bench E3c corriendo;
-- siguiente: PASO A (skills TUI + ceremonia cero, preguntar opción A/B). --
