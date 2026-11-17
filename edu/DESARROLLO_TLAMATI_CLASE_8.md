# CLASE 8 — Delegación con límites: cómo un agente contrata a otro (y no se arruina)

Serie: Desarrollo de Tlamati (capítulo 8). Sesión 12, 17-nov-2026.
Anterior: CLASE_7 (routing.md — cómo el agente decide qué contexto cargar).

---

## 0. DÓNDE VENIMOS

En la Clase 7 le enseñamos a Tlamati a organizar su contexto por "habitaciones"
(workspaces con routing.md): antes de empezar, el agente decide qué archivos
necesita y carga solo esos. Hoy resolvemos el problema hermano: cuando una
tarea requiere leer TANTA cosa que inundaría el contexto del agente aunque
routing funcione, la respuesta no es comprimir — es DELEGAR. Enviar un
ayudante que lea todo, y que regrese con una sola página de resumen.

Esa es la Fase D1: subagentes. Y el reto de ingeniería no es crear el
ayudante (eso es fácil) — es PONERLE LÍMITES.

## 1. EL PROBLEMA (por qué delegar cuesta si no hay topes)

Un subagente es una corrida completa del loop: cada turno llama al modelo, y
cada llamada cuesta dinero. Un agente sin límites que decide "delegar" puede:
- crear cadenas infinitas (el hijo delega a un nieto, el nieto a un
  bisnieto...);
- gastar el presupuesto entero explorando algo que no importaba;
- devolver al padre su conversación COMPLETA, inundando justo el contexto
  que queríamos proteger.

Los tres fallos son reales en harnesses que existen hoy. La spec de Tlamati
(HANDOFF_FASE_D) los ataja con tres reglas duras, y una decisión del fundador
(zanjada, no se re-litiga): "el subagente [es] menos poderoso que el padre".

## 2. LO QUE HICIMOS, PASO A PASO

### Paso 1 — Verificar el piso antes de construir
```
cd ~/code/tlamati && git checkout main && git pull
gh run list --branch main --limit 1     # CI verde confirmado (27s)
uv run pytest tests/ -q                 # 292 verdes ANTES de tocar nada
```
Regla de oro del proyecto: nunca empezar sobre suelo roto. Si un test falla
antes de tu cambio, el fallo es de ayer, no tuyo — y necesitas saberlo.

### Paso 2 — Leer los donors (aprender de los grandes, reimplementar en limpio)
- hermes delegate_task (MIT, donor sancionado): el padre crea el presupuesto,
  el hijo hereda el tope, el padre recibe SOLO el resumen final.
- Raschka #6: límites duros = max_turns + max_cost. Sin ellos no hay
  delegación responsable.
- Código propio reutilizado: PLAN_READONLY_TOOLS (de C5 plan-mode) ya era la
  lista exacta de herramientas de solo lectura — la semilla del toolset del hijo.

### Paso 3 — El archivo nuevo: src/tlamati/subagent/spawn.py (~270 líneas)

Herramientas usadas: write_file para crearlo, patch para correcciones
quirúrgicas, el LSP/pyright del editor para cazar un error de tipos antes de
correr nada (el stream del proveedor envuelto no cumplía el Protocol — se
arregló importando los tipos exactos Event/Message).

Las cuatro piezas del mecanismo:

(a) FILTRO DE PODER — build_child_tools(): de todas las herramientas del
padre, el hijo solo recibe las que están en PLAN_READONLY_TOOLS (leer
archivos, buscar, ver skills, buscar memoria) Y cuyo permiso declarado es
AUTO. Todo lo demás — escribir, editar, terminal, la propia delegate_task —
simplemente NO EXISTE para el hijo. No es que esté "denegado": no aparece en
su catálogo. (Endurecer por construcción es más fuerte que endurecer por
regla: lo que no existe no se puede relajar.)

(b) FAIL FAST DE PROFUNDIDAD — si alguien intenta registrar delegate_task
entre los candidatos del hijo, build_child_tools lanza ValueError con mensaje
explícito ("profundidad máxima 1"), y el tool la convierte en un resultado
"ERROR: ..." honesto. Un nieto es imposible por construcción; el intento
queda registrado como error, no como excepción muda ni crash.

(c) TOPE DE GASTO — _CappedProvider: un envoltorio (wrapper) del proveedor
del padre que suma los tokens (entrada+salida) de cada turno del hijo. Antes
de cada turno nuevo compara: si ya se alcanzó el tope, LANZA el error ANTES
de llamar al modelo. Es la misma inversión de control que el Budget de la
Fase A5: primero preguntar, después gastar — nunca al revés. El resultado
que recibe el padre lo dice en cristiano: "detenido por TOPE DE GASTO — el
resumen puede estar incompleto".

(d) RESUMEN-NO-TRANSCRIPT — el padre recibe una cabecera de metadatos
(stop/turnos/tokens/sesión de auditoría) + LoopResult.final_text, el ÚLTIMO
mensaje del hijo. Todo lo que el hijo pensó en el camino se queda en el hijo.

### Paso 4 — Auditoría sin migrar nada (decisión (a) del handoff)
Los eventos del hijo van al MISMO ledger SQLite de B5, pero con una sesión
hija: "<sesión-del-padre>:sub-01", ":sub-02"... El schema no cambia (cero
migraciones, cero riesgo); `tlamati audit --session <padre>:sub-01` muestra
cada lectura del ayudante con su decisión y su costo. Nada invisible: regla
del proyecto desde B5.

### Paso 5 — Cableado al CLI (src/tlamati/cli.py, +27 líneas)
- Bloque de prompt ESTÁTICO (DELEGATE_PROMPT_BLOCK) añadido tras el de
  plan-mode: el prefijo cacheable solo cambia si cambia el código, nunca por
  corrida (cache sagrada).
- La tool va AL FINAL del orden de tools.specs() (append-only: los prefijos
  de caché del gateway se rompen si algo se inserta en medio).
- Snapshot `parent_tools = list(tool_list)` ANTES del append — bug que cacé
  en revisión: si dejaba el alias, la lista se contenía a sí misma y el
  fail-fast de profundidad se disparaba SIEMPRE. (Copiar la lista, no
  aliasarla: un clásico de Python.)
- Flag --no-subagents y sección `subagent:` en tlamati.yaml para los topes.
- Bonus gratis: en plan-mode, delegate_task queda DENEGADA sola (está fuera
  de la whitelist C5) — la escalera de permisos ya hace el trabajo.

### Paso 6 — Tests (16 nuevos, tests/test_subagent_d1.py, cero red, $0)
FakeProvider con guiones de turnos (mismo patrón de la Clase 2). Los tests
clave:
- hijo solo ve {read_file, search_files} de 5 herramientas del padre;
- tope de 15 tokens → el segundo turno se bloquea ANTES de gastar
  (assert len(child_p.calls) == 1 — la prueba de que no se llamó al modelo);
- max_turns=999 pedido por el modelo → capado a 3 (el techo manda);
- el texto intermedio del hijo NO llega al padre (assert "PENSAMIENTO" not
  in out);
- ledger: el hijo deja tool_events y turn_costs bajo ":sub-01", y el segundo
  spawn bajo ":sub-02";
- integración completa: run_loop del PADRE con FakeProvider → tool
  delegate_task → hijo FakeProvider corre → el tool_result que vuelve al
  historial del padre contiene solo el resumen.

### Paso 7 — La auditoría completa y el ratchet
```
uv run pytest tests/ -q        # 308 passed (292+16)
uv run ruff check src tests    # limpio
uv run ruff format --check .   # 2 archivos reformateados (ver error del día)
uv run mypy --strict src       # 39 archivos, sin issues
```
Smoke gratis ($0, técnica de la Clase 7): proyecto falso en /tmp + API key
dummy. La corrida muere en 401 PERO el prefijo ya se construyó: con
subagentes ctx: system=471 tools=1448; con --no-subagents system=340
tools=1252. Delta medido: +131 tokens de system, +196 de tools. La capacidad
cuesta 327 tokens de prefijo — visible y medible, como promete el PRD.

Baseline REAL (los centavos del día):
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/d1_check.jsonl    # [eval] 5/5 OK
```
cache_read: 74% en la primera tarea (frío, la caché se calienta) → 94-95%
después. Ratchet de Osmani cumplido: ningún merge baja de 5/5.

### Paso 8 — Entrega y merge
Commit 76b12f2 en rama d1-subagent, push, evidencia de comportamiento al
fundador en cristiano (las 4 garantías con su prueba real), OK verbal,
merge --no-ff a main (d67fb60), CI verde verificado (run 44151620765, 21s).
Detalle del commit: los archivos evals/b5_check2/3.jsonl (evidencia untracked
del rate-limit del 16-nov) se colaron con git add -A → corregido con
`git rm --cached` + `git commit --amend` ANTES del push (en la rama, sin
historia pública que reescribir).

## 3. LA TEORÍA DETRÁS

### Patrón: Capability-based delegation (delegación por capacidades)
Principio general reusable: cuando un sistema crea un subsistema para hacer
trabajo en su nombre, el subsistema debe recibir un SUBCONJUNTO ESTRICTO de
las capacidades del padre — nunca el mismo conjunto, y jamás uno mayor. Es
el principio de mínimo privilegio aplicado a la creación de agentes. La
versión fuerte (la que usamos) es "endurecer por construcción": el hijo no
tiene "prohibido" escribir — no tiene la herramienta. Las prohibiciones se
pueden relajar por un bug de configuración; lo que no existe no.

Donor: hermes-agent delegate_task (MIT) — padre crea presupuesto, hijo
hereda tope, padre recibe solo resumen. La semántica completa (incluyendo
"los resúmenes de subagentes son auto-reportes, no hechos verificados") está
en su documentación; Tlamati reimplementa la semántica en limpio, sin copiar
líneas.

### Herramienta: el wrapper como punto de control
_CappedProvider no hereda nada ni sabe nada del proveedor real: lo ENVUELVE
e intercepta un solo método (stream). Es el patrón Decorator/Proxy de toda
la vida aplicado a control de gasto. Mecánica: cualquier invariante que
deba sostenerse "a través de todas las llamadas a X" se puede imponer
envolviendo X en vez de modificando X — el proveedor original ni se entera.
Mismo patrón que el ledger usa para auditar sin tocar las tools.

### Regla anti-speculative aplicada
La spec pedía decidir dos cosas menores (nombre del tool, esquema de
auditoría). Se tomaron las recomendadas (delegate_task alineado con hermes;
prefijo de sesión hija sin migrar schema B5) y se documentaron en el commit.
No se abrió un debate que el handoff ya había cerrado: las decisiones
zanjadas se ejecutan, las abiertas menores se resuelven con la opción
recomendada y se dejan por escrito.

## 4. EL ERROR DEL DÍA

Dos tests nuevos nacieron rojos — y ambos eran tests con SUPUESTOS MALOS, no
código malo (misma lección que la Clase 7):

1. test_tope_de_gasto: puse tope de 20 tokens asumiendo que bloquearía tras
   el primer turno... pero cada turno gasta 15 (10 in + 5 out del
   FakeProvider), y la condición es ">= tope": 15 < 20, así que el segundo
   turno SÍ corría. El test mentía sobre la aritmética. Fix: tope=15, que es
   exactamente lo gastado tras un turno. Lección: cuando pruebes un límite,
   calcula el valor real del fixture; no pongas un número "que se sienta
   cerca".

2. test_no_filtra_transcript: guioné dos turnos de puro texto para el hijo...
   pero el loop termina en end_turn cuando un turno NO tiene tool calls. El
   "segundo turno" nunca existía y el único texto del hijo (el pensamiento
   largo) SÍ era su final_text. Fix: el turno intermedio ahora termina en una
   llamada a tool (search_files), que mantiene el loop vivo, y el resumen
   corto va en el tercer turno. Lección: para probar "el padre ve solo el
   FINAL", el fixture necesita al menos dos finales candidatos.

Y el susto del formato: ruff format --check reprobó 2 archivos al primer
intento (líneas >100 y firma de función partida a mano). `uv run ruff format
src tests` lo resolvió — por eso el cuarteto de auditoría SIEMPRE corre
junto: pytest + ruff check + ruff format --check + mypy --strict. Olvidar el
format-check = CI rojo y un correo de "run failed" que le destruye la
confianza en la alerta al fundador.

## 5. NOTAS REPLICABLES (comandos exactos de hoy)

```
# piso verificado
cd ~/code/tlamati && git checkout main && git pull
gh run list --branch main --limit 1
uv run pytest tests/ -q                      # 292 → tras D1: 308

# rama + trabajo
git checkout -b d1-subagent
# (escribir src/tlamati/subagent/spawn.py + __init__.py, tocar cli.py,
#  escribir tests/test_subagent_d1.py)

# auditoría = CI local
uv run pytest tests/ -q
uv run ruff check src tests
uv run ruff format src tests                 # si format --check reprueba
uv run ruff format --check .
uv run mypy --strict src

# smoke gratis ($0): prefijo medido con key dummy
mkdir -p /tmp/d1_smoke && cd /tmp/d1_smoke
OPENROUTER_API_KEY=*** uv run --project ~/code/tlamati tlamati -p "prueba" \
  --session-db /tmp/d1_smoke/s.db --audit-db /tmp/d1_smoke/a.db --max-turns 1
# → ctx: system=471 tools=1448 (con) vs system=340 tools=1252 (--no-subagents)
# → muere en 401 DESPUÉS de construir el prefijo = evidencia gratis

# baseline real (centavos)
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/d1_check.jsonl      # [eval] 5/5 OK

# entrega (comandos SIMPLES, uno por llamada — el parser bloquea &&)
git add -A && git commit -F -  <<'EOF' ...   # excepción que sí funciona
git push -u origin d1-subagent
# OK verbal → git checkout main → git merge --no-ff d1-subagent -m "..."
git push origin main
gh run list --branch main --limit 1          # CI verde (21s)
```
Pitfall NUEVO de hoy: `curl ... | python3 -c "..."` dispara el bloqueo del
parser (pipe de red a intérprete). Solución: descargar a archivo y leer con
read_file, o parsear en dos pasos.

## 6. CONTINUIDAD

- D1 FUSIONADO: main = d67fb60, CI verde, 308 tests, baseline 5/5.
- Bonus de la sesión: estudio de OpenCrawl (research/06_OPENCRAWL_MULTIPLAYER_
  CONTEXT.md) — un servidor open source (YC, Apache-2.0) de memoria compartida
  ENTRE agentes. Veredicto: no se integra dentro de Tlamati (choca con el
  no-goal de flota multi-agente), pero cuando D3 (cliente MCP) exista,
  cualquier usuario podrá conectar Tlamati a un OpenCrawl propio como una
  fuente más de contexto no-confiable. Los harness (capa vertical) y las
  capas de memoria compartida (capa horizontal) son complementarios.
- PRÓXIMA CLASE (9): D2 — everything-plugin. El consumidor concreto ya
  existe: la auditoría del ledger vive hoy hardcodeada en dos sitios, y la
  prueba real del mecanismo de plugins será migrarla a un plugin interno sin
  cambiar NADA observable. Hooks: before_tool / after_tool / on_error, y solo
  esos tres — cada uno con un consumidor real, ninguno "por si acaso".
  Entry point: HANDOFF_FASE_D2.md.

— Hermes, sesión 12, 17-nov-2026.
