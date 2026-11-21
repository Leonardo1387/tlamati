# H9 v3 — diseño de fixture "cascada ciega" (20-nov-2026)

## Problema que resuelve

La campaña H9 v2 (fixtures anti-batch) NO estiró el horizonte de los frontera:
gpt/opus/qwen-max resolvieron en 4-10 turnos porque (a) las 45 divergencias
eran inferibles estáticamente leyendo tests+docstrings y (b) un modelo listo
puede escribir UN script que corrija todo en un shot y verificar de una vez.
La tesis original ("el ratio codex/tlamati crece con el horizonte") quedó sin
probar en frontera. En una sesión real de programación hasta un frontera se va
a 30-40 turnos; la fixture debe reproducir esa dinámica.

## Mecanismo v3: cascada de fallos runtime (A) + volumen semántico único (C)

Fixture `ducto_cascada_l3`: cadena de ~24-40 módulos Python (pkg `cascada/`)
con CONTRATOS ESTRECHOS ENTRE MÓDULOS: la salida de mNN es parseada/consumida
por mNN+1 con formato exacto (strings con separadores raros, checksums, tipos
estrictos). Cada módulo tiene un defecto sutil distinto sembrado.

Propiedad clave — CASCADA: con la semilla buggy, el primer defecto corrompe o
EXCEPCIONA aguas abajo (ValueError/KeyError en m+k). El runner/verify solo
reporta el PRIMER fallo de ejecución. Cada arreglo revela el siguiente error
→ el agente está obligado a ciclos ejecutar→observar→arreglar, exactamente la
dinámica de una sesión real. No se puede resolver "de un golpe" porque la
información del defecto N solo existe después de ejecutar con N-1 arreglado.

Volumen único (C): la spec de cada módulo vive en su propio archivo
`docs/mNN.md` con semántica idiosincrásica (redondeos propios, órdenes raros,
transformaciones de caracteres con sal por módulo, bordes únicos). Ningún
patrón ni script corrige dos módulos igual. Tamaño objetivo: 500-700 líneas
de solución única — fuera del alcance de un solo turno de salida.

## Estructura de archivos (mismo formato que v2, discover_tasks compatible)

```
fixtures/ducto_cascada_l3/
  instruction.md          # tarea + reglas (no tocar tests/docs/__init__)
  bench_limits.json       # {"max_turns": 150, "timeout_s": 3600}
  docs/m01.md ... mNN.md  # specs únicas por módulo (protegidas por sello)
  cascada/__init__.py     # ejecutar(v) — protegido
  cascada/mNN.py          # módulos con defecto sembrado (EDITABLES)
  tests/test_cadena.py    # tests de cadena con literales precalculados
  verify.py               # tests verdes + sello sha256 de protegidos
```

## Ciclo E3a de validación (obligatorio antes de cotizar)

1. Semilla buggy → verify FALLA (y falla en cascada: primer error temprano).
2. Solución de referencia (generador) → verify OK.
3. Trampa (tocar un protegido) → sello detecta, rc=1.
4. Assert de divergencia: cada defecto cambia la salida de SU módulo vs la
   referencia (patrón v2, 100% divergentes).
5. Anti-batch-check: confirmar que un "fix todo en un script" genérico NO pasa
   (las divergencias son semánticamente únicas).

## Métrica nueva a capturar

Además de turnos/duración/costo: CURVA DE PROGRESO — en qué turno pasó el
agente cada módulo (se puede instrumentar con un wrapper que corra verify
parcial). Esto da la evidencia directa de "horizonte estirado" que H9 v2 no
pudo mostrar. (Opcional; no bloquea la campaña.)

## Estado

- [x] Diseño (este doc)
- [x] Generador /tmp/gen_h9_v3.py (specs + referencias ok/buggy + literales)
  — ensamblado de /tmp/gen_h9_v3_p{1,2,3}.py + /tmp/g3_specs_{a,b,c}.py (verbose);
  literales /tmp/h9_expected_v3.json
- [x] Validación E3a v1 (no escalonada) 5/5 — PERO la calibración reveló que
  gpt-6.2-sol la resolvió en 3 TURNOS: leyó docs+tests con literales y
  reescribió los 34 módulos de un golpe (batch legítimo otra vez).
- [x] REDISEÑO ESCALONADO (anti-batch estructural): /tmp/build_fixture_v3_staged.py
  — docs/m01.md en claro; m02-m34 cifrados (.enc, XOR+sha256 keystream);
  llave de spec N+1 = sha256(jrepr(output correcto de mN)) derivada EN RUNTIME
  por `verify.py --reveal N` tras validar tests unitarios m01..mN;
  tests comparan HASHES (literales fuera del disco); sello NO cubre
  bench_limits.json (runner lo excluye del workdir — bug de la v1);
  límites 250 turnos/5400s. Build se auto-valida ruff post-sello.
- [x] E3a escalonada 4/4: semilla rc=1 / reveal sin arreglar rc=1 / ref VERIFY
  OK rc=0 + reveal 33 imprime spec m34 / trampa rc=1. pytest 440, ruff limpio.
- [x] Registro en tests/test_evals.py (FIXTURE_NAMES)
- [ ] Calibración qwen3-coder sobre versión ESCALONADA (evals/h9_calib_v3b/)
  EN CURSO — la v1 dio 113 turnos/$0.377 (evals/h9_calib_v3/RESUMEN.md)
- [ ] Cotización al fundador ANTES de relanzar (regla de gasto S17)
