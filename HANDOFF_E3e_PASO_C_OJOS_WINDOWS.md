# HANDOFF E3e — PASO C: OJOS A ARCHIVOS WINDOWS (ultra-simplicidad primerizos)
# Generado por Hermes, 19-nov-2026 (sesión 21). Para sesión con CERO contexto:
# leer este archivo completo + skill_view(name='tlamati-harness-project') +
# HANDOFF_E3d_FIXES_TUI_DOGFOODING.md (autopsia completa). Ejecutar los pasos
# EN ORDEN, uno por unidad (entrega → evidencia de COMPORTAMIENTO en cristiano
# → OK verbal → merge). Protocolo: fundador NO-técnico (nunca diffs; Hermes
# auto-audita con pytest + ruff check + ruff format --check sobre `.` entero +
# mypy --strict). Clase al cierre: edu/PROMPT_CLASE_DIARIA.md v2 (siguiente
# número tras CLASE_13).

## 0. ESTADO AL CIERRE DE LA SESIÓN 21 (verificado)

- main = 0e1e07b (PASO A + PASO B FUSIONADOS con OK verbal del fundador,
  pusheados). 404 tests verdes, lint trio limpio. CI debe verificarse al
  inicio de la próxima sesión (`gh run list --branch main --limit 1`).
- PASO A HECHO (commit 38306a9): TUI recibe --skills-dir + config
  skills.extra_dirs (antes hardcodeaba lista vacía = causa madre del
  dogfooding reprobado). CEREMONIA CERO (opción A del fundador, decisión
  ZANJADA — NO re-litigar): ~/.hermes/skills se añade SIEMPRE-AL-FINAL si
  existe (default_skill_roots en memory/skills.py; proyecto > usuario >
  extra > hermes; primer-root-gana intacto). Prueba real: `tlamati` a secas
  ve las 47 skills de Hermes. skill_view con librería vacía da mensaje
  honesto + hint del flag.
- PASO B HECHO (commit 0e1e07b, DISEÑO DEL FUNDADOR — NO re-litigar):
  * DETECTOR DE ESTANCAMIENTO: misma firma de tool calls (nombre + args,
    json canónico sort_keys) N turnos seguidos → stop_reason="stall" corte
    duro + aviso. Default 3 (--stall-repeats, 0 desactiva). Editar el mismo
    archivo con contenido distinto NO es bucle. Activo TAMBIÉN en yolo.
  * MURO: default 20 → 60; <=0 = yolo (sin muro; presupuesto de contexto
    sigue siendo techo sagrado).
  * TUI al topar: mensaje "Escribe 'continúa' para seguir donde quedamos
    (historia intacta), o 'resumen'". Reanudar = re-entrar al loop con
    history= (sesión C1 persiste). "resumen" → ModelSummarizer de A6
    (donor: Hermes lo FUERZA a los 90 turnos; aquí se OFRECE, nunca se
    fuerza) con gasto contado al ledger (turn=-1).
  * EXIT_STALL=8 en json_events.py. resolve_turn_limits() en cli.py:
    flag > config general.max_turns/stall_repeats > default (60/3).
    Mismos límites headless Y TUI (pitfall #5).
- BENCH E3c qwen3-coder COMPLETO en los 3 arneses medibles
  (evals/benchmark_2026-11-19_e3c/, 45/45 cada uno):
  * tlamati: 37/45 corridas, 11/15 todas-las-réplicas, 14/15 al-menos-una,
    $0.18, 1.39M tok_in (cache 92.1%), 16.9 min. OJO: los 8 fallos son
    TODOS errores de proveedor upstream (rc=4 "Provider returned error"),
    NO del arnés — donde el modelo pudo trabajar, resolvió. anti_bucle 3/3.
  * opencode: 42/45, 13/15, 15/15, $0.49, 4.05M tok_in (cache 95.6%).
    Fallos reales: conversor ×2 (aritmética), crear_modulo ×1.
  * codex: 43/45, 14/15, 15/15, $0.86, 7.35M tok_in (cache 96.1%), 38 min.
    Único fallo: edicion_quirurgica_grande ×2 por timeout >600s.
  * hermes: CORTADO ANTES DE EMPEZAR por el orquestador (decisión fundador)
    — correrá al FINAL de la campaña, solo con qwen-coder.
  * DATO ESTRELLA PROVISIONAL: tlamati resolvió con 5.3× menos tokens que
    codex y 2.9× menos que opencode, y 2.2× más rápido que codex. Los rc=4
    upstream inflan sus fallos — documentar con honestidad en EVALS.md
    (regla: un fallo con campo error de proveedor NO es fallo del arnés).
- CAMPAÑA DE MODELOS EN CURSO al cierre (orquestador VIVO desacoplado:
  bench/campaign_e3c.sh, bitácora evals/campaign_run.log, verificar con
  `pgrep -f campaign_e3c`): flash × tlamati+codex corriendo desde 15:24.
  Después: deepseek → kimi (tlamati+codex), y al FINAL hermes × qwen-coder
  → evals/benchmark_2026-11-19_e3c/hermes.jsonl. IDEMPOTENTE: si murió
  (sesión cerrada), relanzar con `bash bench/launch_campaign.sh` — salta
  los combos ya completos (JSONL con 45 líneas). AL TERMINAR TODO: leer
  run.log de cada dir, armar tabla EVALS.md §E3c (pass@1 todas-las-réplicas
  por arnés×modelo, costo USD real, regla de honestidad de corrida única),
  y presentar evidencia al fundador.
- DECISIÓN ZANJADA DEL BENCH (fundador, sesión 21 — NO re-litigar): la
  campaña es tlamati + codex × {flash, deepseek, kimi} (no opencode);
  hermes SOLO qwen-coder AL FINAL (es el más tardado; tener antes los datos
  de codex/opencode).

## 1. PASO C — OJOS A ARCHIVOS WINDOWS (P2, siguiente unidad a ejecutar)

Rama nueva e3e-win-paths (sale de main = 0e1e07b).

Contexto del problema real (autopsia sesión 20, seq 21-22 del dogfooding):
el fundador pegó una ruta Windows tal cual (C:\Users\Admin\Desktop\...) y
read_file falló con "no such file: /home/usuario/C:\Users\...". El
fundador espera que tlamati "tenga ojos sobre mis archivos en la computadora,
así como aquí contigo" (Hermes WSL resuelve esto de facto).

a) FUNCIÓN DE NORMALIZACIÓN (nueva, proponer src/tlamati/tools/winpath.py o
   dentro de builtin.py — decidir por tamaño):
   - Input empieza con letra + ":" (C:\, D:/, c:\...) → traducir a
     /mnt/<letra-minúscula>/ + backslashes→slashes + colapsar duplicados.
   - IDEMPOTENTE: /mnt/c/... intacto; rutas relativas intactas; ~ intacto.
   - Falla HONESTA si el punto de montaje no existe (no es WSL → mensaje
     que lo diga, nunca un path inventado).
   - Aplicar en read_file/search_files/terminal (tools/builtin.py) — los 3
     tools que reciben paths del modelo. write_file/edit_file TAMBIÉN (el
     modelo puede querer editar un archivo Windows pegado por el usuario).
b) OJO SANDBOX (verificar ANTES de codificar la integración): bwrap monta el
   fs read-only — ¿/mnt/c es visible dentro de la jaula? Prueba real:
   read_file de un archivo Windows con sandbox activo. Si bwrap no lo
   expone, ajustar binds en sandbox/sandbox.py (el bind raíz / / incluye
   /mnt/c en principio — VERIFICAR, no asumir).
c) Tests ($0): unit de la normalización (C:\Users\x.txt, D:/dir, /mnt/c/...
   intacto, relativo intacto, ~ intacto, drive inexistente = fallo honesto)
   + integración read_file con archivo sembrado y monkeypatch del prefijo
   /mnt si hace falta + prueba de sandbox si bwrap disponible (skip si no).
d) Bonus NO hacer (fuera de scope, decisión handoff E3d §5b): detección de
   "Desktop" genérico. La normalización C:\Users\... resuelve el caso real.

## 2. PASO D — PRD F16 (documentar, NO implementar)

Añadir a PRD_TLAMATI.md la feature F16 "onboarding guiado por nivel" (COULD
v2): primera corrida detecta config ausente → pregunta nivel (principiante/
técnico) → checklist de setup (proveedor+llave, herramientas recomendadas,
REA opcional, skills). Visión del fundador sesión 20 (verbatim en el
handoff E3d §2). Sin código. Unidad pequeña, puede ir junto al PASO C.

## 3. PENDIENTES HEREDADOS (vigentes)

- Tabla EVALS.md §E3c completa al terminar la campaña (arriba §0).
- E3c PASO 2: sonda varianza multi_archivo N=5-10 (heredado handoff E3c).
- E4: docs (README con sección config: general.max_turns/stall_repeats,
  skills.extra_dirs — el README aún NO existe) + SECURITY.md completo +
  auditoría cobertura de features + SANITIZAR user_id OpenRouter en JSONL
  de errores 429 ANTES de publicar + v0.1.0 público + PyPI.
- Dogfooding #2 del fundador TRAS PASO C (quiere hacer más pruebas con
  tlamati; reinstalar binario ANTES: `uv tool install --from ".[tui]"
  tlamati --reinstall --python 3.12` — su shell tiene python3.11 activo).
- CLASE_13 escrita esta sesión (edu/DESARROLLO_TLAMATI_CLASE_13.md); la
  próxima clase es CLASE_14 (tema sugerido: normalización de caminos como
  contrato de entrada, o lo que la sesión produzca).
- Campaña Spark AL FINAL (orden zanjado sesión 16); scripts en
  ~/code/enverge-pruebas/.

## 4. PITFALLS (acumulados, leer antes de tocar nada)

Heredados de sesiones anteriores (skill tlamati-harness-project + handoff
E3d §8): uv tool install exige --python 3.12; ruff format `.` reescribe
fixtures y rompe hashes sha256 sellados (formatear ANTES de sellar);
mkdir -p antes de `2>dir/log`; copytree ignora __pycache__; CADA feature de
CLI verificar en headless Y TUI (pitfall #5, mordió 2 veces).

Nuevos sesión 21:
1. tests/ NO es paquete Python: `from tests.test_loop import ...` revienta
   en colección (ModuleNotFoundError). Cada archivo de tests define SUS
   fakes localmente (patrón duplicado intencional — FakeProvider es corto).
2. Tests viejos que queman turnos con llamadas IDÉNTICAS ahora los corta el
   detector de estancamiento antes que el muro/budget: variar la firma con
   offset (o campo inerte _tick si la salida debe seguir idéntica, como en
   test_compaction donde se llena contexto a propósito).
3. pilot.press(*"texto") NO puede tipear acentos ("continúa" falla): en
   tests TUI usar texto sin acentos para simular la respuesta del usuario;
   el matching en la app es startswith("resumen") sin acento en el comando.
4. El orquestador de bench corta con pkill -f "bench/runner.py --runs":
   el patrón debe ser específico (un pkill -f "runner.py" mataría otros).
   El corte funcionó exacto: hermes solo había creado 1 tarea en vuelo, su
   JSONL no se escribió (se escribe al terminar el arnés completo).
5. gh run list muestra el run ANTERIOR inmediatamente tras push — esperar
   ~1 min o usar `gh run list --limit 3` para ver el nuevo disparado.

-- Hermes, sesión 21 (19-nov-2026). main = 0e1e07b (A+B fusionados).
-- Campaña de modelos corriendo en background. Siguiente: PASO C (ramas
-- e3e-win-paths) → PASO D (F16) → tabla EVALS.md → dogfooding #2. --
