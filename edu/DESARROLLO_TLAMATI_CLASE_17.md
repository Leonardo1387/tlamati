# Desarrollo Tlamati — Clase 17
## 21-nov-2026: Seguridad real vs seguridad de teatro (fase SEC.1–SEC.3)

Serie: Desarrollo de Tlamati (capítulo 17). Sesión 27, 21-nov-2026.
Anterior: CLASE_16 (las cuatro capas de la memoria; capability-sin-orden).

---

## 0. DÓNDE VENIMOS

El dogfooding #4 (Clase 16) nos dejó una autopsia incómoda: el agente dijo
"no puedo usar la red" y tenía razón — pero NO porque la tarea lo pidiera,
sino porque la jaula bwrap nació sin red y el modelo ni siquiera lo sabía.
Eso destapó una pregunta más grande que el fundador resolvió de un tajo:

> "tlamati debe tener los mismos permisos que Hermes — red completa,
> filesystem completo. La seguridad NO es una jaula ciega; es REVISIÓN de
> lo que vuelve de la web."

Hoy ejecutamos esa decisión: las tareas SEC.1, SEC.2 y SEC.3 del plan
`docs/plans/2026-11-21_integracion_gbrain_aimemory_obsidian.md`.

## 1. LA AUDITORÍA ANTES DEL CÓDIGO (teoría: las tres categorías)

Antes de tocar nada se clasificó cada "capa de seguridad" del repo en una
de tres categorías. Este es el patrón reusable de la clase — cuando audites
cualquier sistema de permisos, pregunta de cada candado: ¿en cuál cae?

- REAL: protege de verdad contra la amenaza que dice. En tlamati: el
  marcado `produces_untrusted` (terminal.py:104) + la trifecta letal
  (policy/config.py: si la corrida consumió contenido untrusted, el EGRESO
  pasa de AUTO a ASK) + MCP siempre ASK. Esto ES el modelo Hermes y no se
  tocó.
- ILUSORIO: parece proteger pero tiene una puerta abierta al lado. La
  jaula fs de bwrap: las file tools corren SIN jaula y en AUTO, y
  `_resolve` (files.py) deja pasar paths absolutos → `write_file` bypasea
  la jaula entera. Decisión: NO se "arregla" — se documenta como paridad
  Hermes (SEC.5, pendiente).
- FRENA SIN PROTEGER: costo real, beneficio cero. La red OFF por default:
  redundante con la trifecta (que ya vigila el egreso) y además mataba el
  flujo pip/railway/curl = deploy muerto desde la TUI.

Conclusión de la auditoría: no había que "quitar la jaula" — la red ya
estaba construida (`--sandbox-net`, cli.py:183) pero (a) default OFF y
(b) NUNCA llegó a la TUI. Dos bugs de cableado, no de arquitectura.

## 2. SEC.1 — config.yaml gobierna el sandbox (y el default de red cambia a TRUE)

**El detalle técnico que hace bonita esta tarea:** el flag viejo era
`action="store_true"` → su default es `False`. Pero `False` es AMBIGUO:
significa a la vez "el usuario pidió red OFF" y "el usuario no opinó".
Con esa ambigüedad es IMPOSIBLE implementar la precedencia
flag > config > default: la config nunca gobernaría, porque el flag
"no puesto" ya votó.

El fix es el patrón de los tres estados:

```python
p.add_argument("--sandbox-net", action=argparse.BooleanOptionalAction,
               default=None, dest="sandbox_net", ...)
```

`BooleanOptionalAction` da `--sandbox-net` / `--no-sandbox-net` gratis, y
`default=None` = "no opinó". Ahora la resolución es limpia:

```python
def resolve_sandbox_flags(cfg, *, enabled_flag, net_flag):
    # flag explícito (no None) > cfg["sandbox"][clave] si es bool > default
    ...
    return (_bool(enabled_flag, "enabled", True), _bool(net_flag, "net", True))
```

Ojo al fail-soft: si la config trae `sandbox: "sí"` (basura), se cae a
defaults en vez de crashear — pero defaults SANOS (net=True), no defaults
asustados.

**BREAKING change documentado en el commit:** default de red OFF → ON.
Entrará en STABILITY.md cuando se escriba (fase G1).

## 3. SEC.2 — el bug raíz: la TUI no cableaba nada

`tui/app.py:346` decía `make_tools(self.workdir)` — sin sandbox, sin
sandbox_net. El fundador usa TUI, así que para él la red era inalcanzable
aunque el flag existiera desde hace semanas.

**¿Te suena? Debe:** es EXACTAMENTE el pitfall #5 de la fase E3d
(`--skills-dir` existía en cli.py y la TUI lo ignoraba; el fundador lo
descubrió usándola y reprobó el dogfooding). Mismo síntoma, mismo fix,
segunda vez. Cuando un bug se repite con otra ropa, la lección no es el
bug — es el proceso: **todo flag del CLI debe tener su camino hasta la
TUI, y un test que lo verifique**. El commit de SEC.2 lo dice explícito.

El cableado son 4 toques: `TlamatiApp.__init__` recibe `sandbox`/
`sandbox_net` (None = "resuelve config"), `_setup_run` los pasa a
`make_tools`, `run_tui()` los transporta, `cli.main()` los extrae de
`args`.

**El test sin gastar un centavo:** no se puede pedir a CI que haga curl.
Pero `produces_untrusted` del tool terminal se computa como
`sandbox_net or not sandbox` — es la HUELLA observable de la resolución,
legible desde `app.registry.get("terminal")` con el Pilot de Textual
(`run_test()`, $0, sin red real):

```python
async with app.run_test():
    assert app.registry.get("terminal").produces_untrusted is True
```

6 tests cubren: flag ON/OFF, default nuevo, config gobierna, flag pisa
config, sin jaula = siempre untrusted.

## 4. SEC.3 — que el agente SEPÁ lo que tiene (capability sin orden, otra cara)

La lección del dogfood #4 fue "capacidad SIN orden = el modelo no la usa".
SEC.3 es su hermano gemelo: **capacidad SIN CONOCIMIENTO = el modelo la
niega**. Nemotron intentó curl, salió exit 6, y no supo decir "no tengo
red" — se enredó. El fix: el bloque ambiental (`env_info.py`) declara el
estado de red:

- net ON: "El tool terminal SÍ tiene acceso a red: curl/wget/pip install/
  git clone funcionan con normalidad."
- net OFF: "NO tiene acceso a red (jaula bwrap): fallan (exit 6/2). Dilo
  honesto y ofrece una alternativa sin red."

**La consistencia es la parte seria:** la red declarada en el prompt y la
red real del tool no pueden contradecirse jamás, o volvemos al "no puedo"
mentiroso pero invertido. Por eso ambos sitios usan LA MISMA fórmula:
`net_efectiva = sandbox_net or not sandbox`. Y un test de punta a punta
lo bloquea:

```python
assert _untrusted(app) is ("SÍ tiene acceso a red" in app._system_prompt)
```

**La cache sagrada (commit 7751663) sigue intacta:** `net` es un parámetro
estático por corrida (no hay reloj ni estado mutable en el bloque), así que
el prefijo cacheable sigue siendo byte-estable. Test explícito:
`a == b` entre llamadas, `a != bloque_con_otra_red`.

En la TUI hubo que MOVER la resolución de sandbox antes del build del
prompt (antes estaba después) — orden de dependencias, no cosmética.

## 5. VERIFICACIÓN (los comandos exactos)

```
cd ~/code/tlamati
ruff check .                          # All checks passed!
python -m pytest tests/ -q            # 508 passed (antes 501; +7 en SEC.3)
```

Smoke en vivo SIN modelo ($0, heredoc python):

```
default resuelto: True True
curl con default nuevo → [exit 0] 200          # la jaula YA tiene red
curl con --no-sandbox-net → EXIT=6             # y la denegación sigue viva
```

Commits de la sesión:

```
b25745e feat(cli): SEC.1 config.yaml gobierna sandbox + red ON por defecto
2f8a4ce fix(tui): SEC.2 cablear sandbox/net en la TUI (el bug raiz)
49d7833 feat(prompt): SEC.3 el agente SABE si su terminal tiene red
```

## 6. EL ERROR DEL DÍA

Pequeño pero instructivo: en el primer test de SEC.2 escribí
`tool.permission.produces_untrusted` — Pyright me paró en seco:
`produces_untrusted` NO vive en el enum `Permission`, es un campo del
dataclass `Tool` (registry.py:69). El IDE como primer reviewer: el error
apareció ANTES de correr pytest. Segundo tropiezo: ruff F401 por un
`import pytest` que no usé en test_sandbox_config.py — la suite del repo
corre `ruff check .` como gate, así que lint no es opcional.

## 7. TEORÍA REUTILIZABLE DE HOY

1. **Flags de tres estados** (`None` = no opinó) son requisito para cualquier
   precedencia flag > config > default. `store_true` con default `False`
   hace imposible que la config gobierne. (Donor conceptual: el patrón de
   `resolve_turn_limits` que ya existía en cli.py — E3d.)
2. **Auditoría en tres categorías** (REAL / ILUSORIO / FRENA SIN PROTEGER)
   antes de escribir código de seguridad. La jaula sin red caía en la
   tercera: costo (pip/railway muertos) sin beneficio (la trifecta ya
   cubría el egreso).
3. **Huellas observables para testing $0:** cuando no puedes probar el
   efecto real (red), prueba el estado interno que LO CAUSA
   (`produces_untrusted`). Es el mismo truco de los tests E1 con
   FakeProvider.
4. **Los bugs que se repiten con otra ropa piden un test de contrato, no
   otro parche.** E3d (--skills-dir) y SEC.2 (--sandbox-net) son el mismo
   bug: el CLI tiene el flag, la TUI no lo recibe. La regla del repo ahora:
   cada flag nuevo del CLI nace con su camino a la TUI Y su test.
5. **Prompt y herramienta deben decir la misma verdad** (una sola fórmula
   compartida: `sandbox_net or not sandbox`) — si divergen, el agente
   miente con conocimiento de causa, que es peor.

## 8. CONTINUIDAD

Fase SEC al 60%: quedan SEC.4 (ergonomía de la trifecta: "aprobar SIEMPRE
esta herramienta en esta sesión" en el approver TUI — el mecanismo
`_always_allow` YA existe, falta exponerlo mejor) y SEC.5 (SECURITY.md con
la matriz honesta de las tres categorías de hoy). Después: G2
(gap-analysis del dream) y el resto del plan de integración
(M8a/M8b/M8c, G1, O1). Todo en `HANDOFF_FASE_SEC.md` en la raíz del repo.
