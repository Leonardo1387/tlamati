# Plan de integración: ideas de gbrain + ai-memory + obsidian-skills → tlamati

> **Para Hermes:** usar skill subagent-driven-development para ejecutar tarea por
> tarea (review de spec + review de calidad tras cada tarea).

**Meta:** adoptar las 4 ideas de alto valor detectadas en la revisión del
21-nov-2026 (gbrain 33.4k★, ai-memory, obsidian-skills) SIN traicionar la
tesis de tlamati: local-first, un paquete Python, cero dependencias nuevas,
archivos markdown = fuente de verdad, cero-LLM por defecto.

**Arquitectura:** todo cuelga de lo que YA existe — `memory/store.py` (C2),
`memory/dream.py` (C2), `memory/skills.py` (C3), `bench/runner.py` (H9). Un
único archivo nuevo derivado (`.meta.json` sidecar, reconstruible) y un módulo
nuevo (`memory/lint.py`). Nada de servidor, nada de MCP, nada de Postgres.

**Fuentes (leer antes de cada fase):**
- ai-memory: `docs/ARCHITECTURE.md` (secciones M8 memory tiers, A2 tier-down
  extractivo, A5 dedup) — https://github.com/akitaonrails/ai-memory
- gbrain: `docs/STABILITY.md` y `docs/tutorials/improving-skills-with-skillopt.md`
  — https://github.com/garrytan/gbrain
- obsidian-skills: `plugins/obsidian/skills/*/SKILL.md` + spec agentskills.io
  — https://github.com/obsidianmd/obsidian-skills

**Regla de donores (convención del repo):** cada módulo nuevo cita su donor en
el docstring, como hacen store.py/dream.py. Donores de este plan: ai-memory
(retención/decay/lint cero-LLM), gbrain (STABILITY.md, gap-analysis, skillopt),
obsidian-skills (fixture de compatibilidad agentskills.io).

---

## Prioridades y alcance

| Fase | Qué | Valor | Cuándo |
|------|-----|-------|--------|
| G2 | Gap-analysis en dream.py | Alto, ~30 líneas | ANTES de v0.1 |
| M8a | Sidecar `.meta.json` + reforzamiento por acceso | Alto (pendiente "seeds memoria") | ANTES de v0.1 |
| M8b | Tiers HOT/COLD + reporte de entradas frías (cero-LLM) | Alto | ANTES de v0.1 |
| M8c | `memory lint`: near-duplicates cero-LLM (advisory) | Medio | ANTES de v0.1 |
| G1 | STABILITY.md (promesa escrita de estabilidad) | Alto y barato | ANTES de hacer público |
| O1 | Fixture obsidian-skills → test de compat agentskills.io | Medio (marketing real) | ANTES de v0.1 |
| S1 | skillopt (SKILL.md como parámetro entrenable) | Grande | E+, DESPUÉS de v0.1. Spike primero |

**DESCARTADO explícitamente** (no abrir issues "por si acaso"): servidor
MCP/grafo tipado/schema packs de gbrain (otro producto), handoffs cross-agent
claim-once de ai-memory (tlamati es monosesión; revivir solo si llega
multi-sesión paralela), dream con re-escritura LLM de clusters fríos (el dream
con LLM ya existe; la parte cero-LLM de este plan es complemento, no reemplazo).

**Invariantes que NINGUNA tarea puede romper:**
1. MEMORY.md y USER.md siguen siendo la única fuente de verdad; `.meta.json`
   es derivado y reconstruible (si se borra, todo sigue funcionando).
2. Cero-LLM por defecto: M8a/M8b/M8c no hacen NI UNA llamada a modelo.
3. Nada se borra en silencio: el lint y el decay son advisory (reportan, no
   mutan). Solo el dream con LLM existente y el agente vía `memory` tool mutan.
4. `render_for_prompt()` NO cambia de output: el prefijo cacheable es sagrado
   (pitfall documentado en commit 7751663). Los metadatos NUNCA entran al
   system prompt.
5. Los caps actuales (100 entradas / 24k chars / 2k por entrada) no se tocan.

---

## FASE SEC (PRIORIDAD 0) — Paridad de permisos estilo Hermes + auditoría de restricciones

Decisión del fundador (21-nov): tlamati debe tener los mismos permisos que
Hermes — red completa, filesystem completo, seguridad vía REVISIÓN de lo que
vuelve de la web (marcado untrusted + aprobación de egreso), no vía jaula
ciega. Auditoría del código real: la red ya existe (`--sandbox-net`,
cli.py:183) pero la TUI no cablea los flags (tui/app.py:346 llama
`make_tools(self.workdir)` sin sandbox/sandbox_net) → en TUI la red es
INALCANZABLE. Además sin red no funcionan pip/railway/curl = flujo muerto.

Hallazgos de la auditoría (qué protege de verdad vs qué solo frena):
- REAL: marcado `produces_untrusted` (terminal.py:104) + trifecta letal
  (policy/config.py: egreso AUTO→ASK tras consumir untrusted) + MCP ASK
  innegociable. Esto ES el modelo Hermes. NO se toca.
- ILUSORIO: jaula fs de bwrap — las file tools corren SIN jaula y AUTO,
  `_resolve` (files.py:248-260) deja pasar paths absolutos → write_file
  bypasea la jaula entera. Aceptar paridad-Hermes: files libres (documentar),
  jaula = red-de-accidentes-shell, no frontera de seguridad fs.
- FRENA SIN PROTEGER: net OFF por defecto (redundante con la trifecta) y
  TUI sin acceso al flag.

### Task SEC.1: config.yaml gobierna el sandbox (no solo flags CLI)

**Archivos:** Modify `src/tlamati/cli.py` (~línea 83-95 load_config, ~509-541),
Test `tests/test_sandbox_config.py`.

Añadir sección `sandbox:` a config.yaml:
```yaml
sandbox:
  enabled: true      # jaula bwrap fs (default true)
  net: true          # red dentro de la jaula (default NUEVO: true — paridad Hermes)
```
Precedencia: flag CLI explícito > config.yaml > default (net=True). El
default net cambia de False a True: documentar en el commit como breaking
behavior change (entra en STABILITY.md de G1).

### Task SEC.2: la TUI cablea sandbox/net (el bug raíz)

**Archivos:** Modify `src/tlamati/tui/app.py:346` (+ constructor para recibir
cfg de sandbox), Test `tests/test_tui_sandbox_flags.py` (o verificación manual
documentada si la TUI no es testeable headless — decidir en la tarea).

`make_tools(self.workdir, sandbox=..., sandbox_net=...)` leyendo de la config
resuelta. Sin esto, SEC.1 no llega al fundador (que usa TUI).

### Task SEC.3: el agente SABE lo que puede (lección dogfood #4)

**Archivos:** Modify `src/tlamati/env_info.py` (environment_block) o el system
prompt builder, Test `tests/test_env_info_listdir.py` (extender).

El bloque ambiental declara: "terminal corre con red habilitada/deshabilitada;
sin red, curl/pip/railway fallan — dilo honesto y ofrece alternativa". Un
agente que no sabe que tiene red responde "no puedo" aunque pueda. Byte-estable
por corrida (cache sagrada, regla del commit 7751663).

### Task SEC.4: ergonomía de la trifecta (mantener seguridad, quitar fricción)

**Archivos:** Modify `src/tlamati/tui/app.py` (_approver ~421-430), docs.

La trifecta SE QUEDA (es la defensa real). Cambio: el approver de la TUI ofrece
"aprobar SIEMPRE esta herramienta en esta sesión" (3ra opción junto a sí/no),
para que el flujo web→egreso no pida click en CADA comando. Headless:
documentar `--approve-tool terminal` en README/help como el equivalente.
Test: el approver recuerda la concesión por corrida (Policy mutable por run,
ya existe el mecanismo).

### Task SEC.5: documenting la frontera real (README + SECURITY.md)

Actualizar SECURITY.md con la matriz honesta post-auditoría: qué protege cada
capa, qué NO protege (file tools libres = paridad Hermes; keys visibles al
comando enjaulado, ya documentado en bwrap.py punto 3), y que la defensa
anti-injection es el marcado untrusted + trifecta + MCP ASK. Sin marketing:
los límites explícitos son feature en un harness OSS.

Orden: SEC.1→SEC.2→SEC.3→SEC.4→SEC.5, todo ANTES de G2. Verificación de fase:
sesión TUI real donde el agente ejecuta `curl -s https://example.com` y
`railway --version` sin que el fundador toque nada, y donde tras leer contenido
web el siguiente comando de egreso pida aprobación UNA vez ("siempre" disponible).

---

## FASE G2 — Gap-analysis en el dream (donor: gbrain `think`)

gbrain responde con "lo que el cerebro NO sabe" (páginas viejas, huecos,
contradicciones). Versión tlamati: el consolidador ya lee la transcripción
completa; pedirle que además reporte huecos cuesta 0 llamadas extra.

### Task G2.1: extender el contrato JSON del dream

**Archivos:**
- Modify: `src/tlamati/memory/dream.py` (DREAM_SYSTEM línea ~28-38, `parse_dream_output` ~73-93, `DreamReport` ~43-51)
- Test: `tests/test_dream_gaps.py` (nuevo)

**Paso 1 — test que falla:**

```python
# tests/test_dream_gaps.py
from tlamati.memory.dream import parse_dream_output, DreamReport


def test_parse_extrae_gaps_junto_a_operations():
    raw = '{"operations": [], "gaps": ["El usuario mencionó Railway pero no hay nada guardado", "Posible contradicción: entrada X dice A, la sesión dijo B"]}'
    ops, gaps = parse_dream_output(raw)
    assert ops == []
    assert len(gaps) == 2
    assert "Railway" in gaps[0]


def test_parse_tolerante_sin_gaps():
    ops, gaps = parse_dream_output('{"operations": []}')
    assert ops == [] and gaps == []


def test_report_humano_incluye_gaps():
    r = DreamReport(applied=1, gaps=("no hay clave OPENAI en memoria",))
    assert "hueco" in r.human().lower() or "gap" in r.human().lower()
```

**Paso 2:** `pytest tests/test_dream_gaps.py -v` → FAIL (parse_dream_output devuelve 1 valor).

**Paso 3 — implementación:**
- `parse_dream_output` pasa a devolver `tuple[list[dict], list[str]]`; extrae
  `data.get("gaps")`, filtra a `list[str]`, tope 3 gaps, cada uno ≤ 300 chars.
- `DreamReport` gana campo `gaps: tuple[str, ...] = ()`; `human()` agrega
  `"; N hueco(s): ..."` cuando hay gaps.
- `DREAM_SYSTEM`: agregar al JSON esperado el campo `"gaps"` con la instrucción:
  «"gaps": 0-3 frases cortas señalando qué NO quedó en memoria y probablemente
  importará después (temas que el usuario mencionó de pasada, decisiones sin
  registrar, posibles contradicciones con entradas existentes). Si no hay
  huecos: lista vacía.»
- En `dream()`: pasar los gaps al report. Los gaps NO se escriben a ningún
  archivo (advisory puro, invariante 3).

**Paso 4:** `pytest tests/test_dream_gaps.py tests/ -k dream -v` → PASS (los tests existentes de dream que desempaquen el retorno viejo deben actualizarse al nuevo contrato de 2 valores — revisar `tests/` con `grep -rn parse_dream_output tests/`).

**Paso 5:** commit `feat(dream): gap-analysis — el consolidador reporta huecos de memoria (donor: gbrain think)`.

### Task G2.2: superficie del reporte

**Archivos:** Modify: donde se imprime `DreamReport.human()` al cierre (buscar:
`grep -rn "human()" src/tlamati/cli.py src/tlamati/tui/app.py`).

Verificar que los gaps se ven en headless Y en TUI al terminar sesión con
`--dream`. Manual: correr una sesión headless corta con dream activo y clave de
modelo barata; confirmar el reporte. Commit separado.

---

## FASE M8a — Sidecar de metadatos + reforzamiento por acceso (donor: ai-memory M8)

ai-memory: «la memoria que se USA decae más lento; abrir/buscar/linkear cuenta
como uso» (`access_count`, `last_accessed_at`, fórmula
`salience·exp(−λΔt) + σ·log(1+access_count)·exp(−μ·days_since_access)`).

**Adaptación honesta a tlamati:** aquí TODA la memoria se inyecta en el prompt
cada turno (no hay retrieve selectivo), así que "acceso" no puede ser
"apareció en el prefijo". Lo que SÍ es señal de uso en tlamati:
- el agente hizo `replace`/`remove` tocando la entrada (la reescribió = viva),
- el dream con LLM la tocó,
- `session_search` o el lint la referenció (v2, no ahora).

Señal de nacimiento: `add` → `created_at`.

### Task M8a.1: módulo `memory/meta.py` (nuevo)

**Archivos:**
- Create: `src/tlamati/memory/meta.py`
- Test: `tests/test_memory_meta.py`

**Contrato (copiar al docstring del módulo, con donor citado):**

```python
"""M8a — Sidecar de metadatos derivados para memoria (donor: ai-memory M8).

memory/.meta.json: {"version": 1, "entries": {"<key>": {...}}}
- key = sha1_16(texto normalizado de la entrada)  # normalizar: " ".join(e.split())
- valor = {"created_at": iso, "last_touched_at": iso, "touch_count": int}
DERIVADO Y RECONSTRUIBLE: si no existe o se corrompe, se regenera vacío sin
tocar MEMORY.md/USER.md (invariante 1). Nunca se renderiza al prompt
(invariante 4). Escritura atómica igual que store._write (tmp + replace).
"""
```

API mínima (YAGNI — solo lo que M8b necesita):

```python
class MemoryMeta:
    def __init__(self, dir_path: Path): ...  # dir = mismo dir del MemoryStore
    def load(self) -> dict: ...  # tolerante: corrupto → {}
    def touch(
        self, entry_text: str
    ) -> (
        None
    ): ...  # crea-o-actualiza: last_touched_at=now, touch_count+=1; si es nuevo, created_at=now
    def forget(self, entry_text: str) -> None: ...  # borra la clave (remove de entrada)
    def save(self) -> None: ...  # atómico
    @staticmethod
    def key(entry_text: str) -> str: ...
```

**Tests clave:**
- roundtrip touch→save→load;
- archivo corrupto (escribir `"{basura"`) → `load()` devuelve `{}` sin raise;
- normalización: `"  hola   mundo "` y `"hola mundo"` → misma key;
- `forget` de clave inexistente = no-op;
- entradas duplicadas en texto (mismo key) no rompen (touch_count sube 2).

**Paso integración:** en `MemoryStore.apply_batch` (store.py:129-182), tras el
`self._write(new_mf)` exitoso: `add` → `meta.touch(content)`; `replace` →
`meta.forget(old)` + `meta.touch(content)`; `remove` → `meta.forget(old)`.
MemoryStore recibe `MemoryMeta` opcional en `__init__` (default: None = conducta
actual byte-idéntica; los tests viejos no se enteran). Fallo del sidecar NUNCA
aborta el batch (try/except → seguir; la memoria manda).

Commits: (1) meta.py + tests, (2) cableado en store.py + tests.

### Task M8a.2: reconciliación al cargar

En `MemoryMeta.load()`: descartar claves que ya no correspondan a ninguna
entrada viva de los dos archivos (basura de entradas borradas a mano). Esto
requiere que load reciba las entradas actuales — hacerlo en un método
`reconcile(entries_vivas: list[str])` llamado desde el punto donde se construye
el store en cli.py (buscar `MemoryStore(` en src/). Test: entrada fantasma en
el sidecar → tras reconcile, desaparece al siguiente save.

---

## FASE M8b — Tiers HOT/COLD + reporte de frío (donor: ai-memory M8 tiers + A2)

ai-memory: Episodic 30d hot → 180d cold → evict-o-tier-down. tlamati v1
simplificado y ADVISORY (invariante 3 — aquí no se evicta nada):

- HOT: `touch_count >= 2` o edad ≤ 14 días desde `last_touched_at`.
- COLD: edad > 45 días sin touch.
- Sin sidecar/fecha conocida → treat como HOT (beneficio de la duda; el
  sidecar nace vacío en installs existentes).

### Task M8b.1: `MemoryMeta.cold_entries()`

**Archivos:** Modify `src/tlamati/memory/meta.py`, Test `tests/test_memory_meta.py`.

```python
def cold_entries(
    self, live: dict[str, list[str]], now: datetime | None = None, cold_days: int = 45
) -> list[tuple[str, str, int]]:
    """live = {"memory": [entradas...], "user": [...]}.
    Devuelve [(target, entrada, días_sin_touch)] para entradas COLD.
    now inyectable para tests deterministas."""
```

Test con `now` fijo: entrada creada hace 60 días sin touch → cold; tocada hace
5 días → hot; sin registro → hot.

### Task M8b.2: CLI `tlamati memory status`

**Archivos:** Modify `src/tlamati/cli.py` (sigue el patrón del subcomando
`tlamati model` existente, commit 4b6c9c2).

Salida (ejemplo real esperado):
```
memoria user:    12/100 entradas, 1,830/24,000 chars
memoria project: 3/100 entradas, 412/24,000 chars
frías (>45d sin uso): 2
  [user] "El usuario prefiere vim..." (61 días)
  [memory] "Deploy de prueba en..." (48 días)
Sugerencia: consolida o confirma vigencia en la próxima sesión.
```

Test: capsys sobre la función del subcomando con sidecar temporal sembrado.
Commit: `feat(memory): sidecar de uso + tiers hot/cold + 'memory status' (donor: ai-memory M8)`.

**Nota de diseño (regla del repo, "capacidad SIN orden" no aplica aquí):** NO
agregar decaimiento automático que reescriba MEMORY.md en esta fase. La
presión de consolidación la siguen poniendo los caps + el dream. Si el
fundador quiere eviction real, es decisión explícita posterior con
supersede-not-delete (copiar el patrón `restore-page` de ai-memory).

---

## FASE M8c — `memory lint`: near-duplicates cero-LLM (donor: ai-memory A5)

ai-memory usa embeddings con banda de coseno 0.4-0.75. tlamati no tiene
embeddings ni debe tenerlos (tesis cero-dependencias). Sustituto honesto:
Jaccard sobre tokens normalizados, advisory puro.

### Task M8c.1: módulo `memory/lint.py`

**Archivos:** Create `src/tlamati/memory/lint.py`, Test `tests/test_memory_lint.py`.

```python
"""M8c — Lint cero-LLM de memoria (donor: ai-memory A5, adaptado: Jaccard en
vez de embeddings porque tlamati no tiene ni quiere vector store).
ADVISORY: nunca muta archivos (invariante 3)."""

@dataclass(frozen=True)
class Finding:
    kind: str            # "near_duplicate"
    target_a: str; entry_a: str
    target_b: str; entry_b: str
    score: float

def lint(entries: dict[str, list[str]], threshold: float = 0.55) -> list[Finding]:
    # pares (todos contra todos, ~5k pares máx con caps → trivial)
    # sim = |tokA ∩ tokB| / |tokA ∪ tokB|; tokens = casefold, sin puntuación,
    # descartar stopwords es YAGNI v1 (medir con tests reales primero)
```

Tests: dos entradas casi iguales → finding con score alto; entradas distintas →
sin finding; entrada consigo misma no se compara; determinismo del orden.

### Task M8c.2: CLI `tlamati memory lint`

Imprime findings en formato `memory status`; exit code 0 siempre (advisory).
Opcional: que el dream SIN LLM disponible (campos skipped_reason de modelo)
corra el lint y lo adjunte al reporte — solo si cabe en ≤15 líneas; si no,
skip (YAGNI).
Commit: `feat(memory): lint cero-LLM de near-duplicates, advisory (donor: ai-memory A5)`.

---

## FASE G1 — STABILITY.md (donor: gbrain docs/STABILITY.md)

### Task G1.1: escribir la promesa

**Archivos:** Create `STABILITY.md` en la raíz (junto a SECURITY.md, NOTICE.md).
Leer primero el de gbrain (raw.githubusercontent.com/garrytan/gbrain/stable/docs/STABILITY.md)
y adaptar, NO copiar. Contenido mínimo:
- Qué se considera estable en v0.1: formato de MEMORY.md/USER.md/SKILL.md,
  flags de CLI documentadas en --help, formato de sessions.db (solo lectura
  vía session_search), códigos de salida.
- Qué NO promete: APIs internas de `src/tlamati/**` (importables pero no
  contrato), campos de `.meta.json` (derivado, puede migrar con version key).
- Cómo se avisa de breaking changes: sección "Unreleased" del changelog +
  deprecation de al menos 1 release menor (regla gbrain: "removals need a
  deprecation").
- Canales: alpha (main) vs releases taggeadas.
Commit: `docs: STABILITY.md — promesa de estabilidad v0.1 (donor: gbrain)`.

---

## FASE O1 — Compatibilidad agentskills.io probada con obsidian-skills

### Task O1.1: vendear el fixture

```bash
cd ~/code/tlamati
git clone --depth 1 https://github.com/obsidianmd/obsidian-skills /tmp/obskills
mkdir -p fixtures/agentskills_compat
cp -r /tmp/obskills/plugins/obsidian/skills/* fixtures/agentskills_compat/
cp /tmp/obskills/LICENSE fixtures/agentskills_compat/LICENSE   # o MIT.md según exista
```

Registrar proveniencia y licencia en `NOTICE.md` (el repo ya tiene NOTICE.md —
seguir su formato). Verificar tamaño: si el total > ~500KB, copiar solo 3
skills representativos (obsidian-markdown, defuddle, json-canvas) y documentar
la selección en el README del fixture.

### Task O1.2: test de compatibilidad

**Archivos:** Test `tests/test_skills_agentskills_compat.py`.

```python
from pathlib import Path
from tlamati.memory.skills import parse_skill  # ajustar import real de SkillLibrary

FIXTURE = Path(__file__).parent.parent / "fixtures" / "agentskills_compat"


def test_todos_los_skills_del_fixture_parsean():
    skills = [d for d in FIXTURE.iterdir() if (d / "SKILL.md").is_file()]
    assert len(skills) >= 3
    for d in skills:
        s = parse_skill(d / "SKILL.md")
        assert s is not None, f"{d.name} no parseó"
        assert s.name and s.description
```

Si algún skill real NO parsea: eso es un bug de tlamati contra el spec —
arreglar `parse_skill` (probablemente frontmatter con campos extra del spec
como `license`, `metadata`, `allowed-tools` que hoy se ignoran; confirmar que
se ignoran sin crashear). Ese es justo el valor del fixture.
Commit: `test(skills): compat agentskills.io verificada con fixture obsidian-skills`.

### Task O1.3 (docs): una línea en README.md

«tlamati lee cualquier skill compatible con agentskills.io (verificado contra
obsidian-skills)» + badge/enlace. Solo si O1.2 pasa limpio.

---

## FASE S1 (E+, POST v0.1) — skillopt: SKILL.md como parámetro entrenable

Donor: gbrain `skillopt` (~20 min, ~$1 por corrida según su tutorial). tlamati
tiene ventaja: `bench/runner.py` + fixtures L1-L3 + la disciplina de evals de
la campaña H9 ya existen.

**NO implementar directo. Spike primero** (writing-plans: exploración → spike).

### Task S1.0 — Spike (descartable, rama `spike/skillopt`)

Pregunta a responder con ≤$2 de API: ¿un ciclo propose→bench→keep mejora
medible y reproduciblemente un SKILL.md real contra su fixture?

Pasos del spike (todo en `dev/skillopt_spike.py`, desechable):
1. Elegir UN skill existente con eval asociada (candidato: un skill cuyo
   ejercicio ya corra en `bench/runner.py`; si ninguno existe, crear fixture
   mínimo de 1 tarea verificable con `verify.py` estilo fixtures/).
2. Baseline: correr el bench 3 veces (seed fija, como campaña H9 runs3) →
   score base + varianza.
3. Mutación: 1 llamada al modelo compacto con (SKILL.md + fallos observados)
   → propuesta de diff del skill.
4. Aplicar en COPIA (nunca el original; skills pineados intocables), re-correr
   bench 3 veces.
5. Criterio de éxito del SPIKE: mejora > varianza baseline en ≥1 de 2
   mutaciones intentadas, costo total < $2, todo reproducible con seed.
6. Escribir `dev/SPIKE_SKILLOPT.md` con números reales (regla del fundador:
   resultados inline + etiquetar brazos corridos; sin números reales no hay
   fase S1).

**Regla S17 del fundador aplica:** campaña grande de mutaciones SOLO con
cotización previa y OK explícito. El spike corre con centavos; la fase S1
completa NO se presupuesta sola.

### Task S1.1+ — Implementación (solo si el spike dice SÍ)

Boceto de alcance (refinar en handoff propio, formato HANDOFF_*.md del repo):
- Módulo `skillopt/`: `benchmark.py` (bootstrap de eval desde SKILL.md vía
  modelo, con gate humano de aprobación — patrón `exit_plan_mode` de C5),
  `optimize.py` (loop propose→apply→bench→keep/revert con tope de iteraciones
  y tope de costo hard-coded), `report.py`.
- CLI: `tlamati skillopt <skill> --bench <fixture> --max-edits 3 --max-cost 1.0`.
- Seguridad: trabajo sobre copia en workdir temporal; el original solo se
  toca con `--apply` explícito tras mostrar diff + scores antes/después;
  skills pineados → rechazo fail-closed.
- Anti-overfit: holdout — el bootstrap separa tareas de eval en train/holdout;
  solo se conserva una mutación que mejore en holdout (donor: skillopt
  "strengthen the judges").

---

## Orden de ejecución sugerido

```
G2  (1 sesión, ~1h)      — victoria rápida, mejora dream existente
M8a (1-2 sesiones)       — sidecar + cableado (el núcleo del pendiente "seeds")
M8b (1 sesión)           — tiers + memory status
M8c (1 sesión)           — lint advisory
G1  (media sesión)       — STABILITY.md (leer el de gbrain primero)
O1  (media sesión)       — fixture + test de compat
────── v0.1 público ──────
S1.0 spike (1 sesión, ≤$2) → decisión → S1.1+ si y solo si el spike pasa
```

Cada fase: handoff corto al estilo del repo si la sesión se corta
(HANDOFF_M8_MEMORY_AGING.md etc.), tests verdes (`pytest tests/ -q`) y
commit por tarea. Dogfooding obligatorio: correr al menos una sesión real de
tlamati con `--dream` tras G2 y tras M8b, y autopsiar sessions.db si algo se
rompe (patrón references/dogfooding-session-autopsy.md).

## Verificación final de la integración (definición de "hecho")

1. `pytest tests/ -q` verde, sin tests viejos rotos (store byte-idéntico sin
   sidecar: diff de MEMORY.md antes/después de una corrida sin meta = vacío).
2. `tlamati memory status` y `tlamati memory lint` corren en la máquina del
   fundador sobre la memoria real (~/.local/share/tlamati/memory) sin errores.
3. Sesión real con `--dream`: el reporte muestra ops + gaps (o lista vacía
   honesta).
4. STABILITY.md existe y el README lo enlaza.
5. Fixture obsidian-skills parsea 100% y NOTICE.md registra la licencia.
6. `dev/SPIKE_SKILLOPT.md` con números reales (post-v0.1).
