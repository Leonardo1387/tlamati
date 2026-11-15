# Desarrollo Tlamati — Clase 4
## 15-nov-2026: Contraseña perdida, candados apt y las 5 herramientas formales

Fíjate cómo empezó el día: no con código, sino con una puerta cerrada. Queríamos
instalar bubblewrap y ripgrep (el paso B3-deps del handoff) y `sudo` nos pidió
una contraseña que no aparecía por ningún lado. Aquí va el primer concepto real
del día: Linux nunca guarda tu contraseña, guarda un **hash** — una huella
matemática de un solo sentido, como moler café: del polvo no puedes recuperar
el grano. Está en /etc/shadow y ni root puede leer la original; solo puede
comparar huellas. Por eso buscar la contraseña en archivos es imposible, y por
eso la solución fue otra: **resetear**. WSL tiene una puerta trasera legítima:
desde PowerShell de Windows, `wsl -u root` te da un root sin contraseña (porque
Windows ya te autenticó al arrancar). Desde ahí, `passwd usuario` y listo.

El segundo tropiezo fue más mundano y más instructivo: `apt` dijo "Could not get
lock... held by process 166644". Un **lock** (candado) es un archivo que usa un
solo proceso a la vez para que dos instalaciones no se pisen — como el letrero
de ocupado en un baño. El diagnóstico con `ps -p 166644` mostró un apt-get
update automático colgado desde hacía 26 horas (el actualizador de Ubuntu,
unattended-upgrades, a veces se pasma). Regla de oro: el error te da el PID; se
mata al PID con `kill`, y NUNCA se borran los archivos lock a mano (eso sí
rompe el sistema). Con eso, bubblewrap 0.9.0 y ripgrep 14.1.0 quedaron
instalados, y la prueba de fuego del sandbox pasó:
`bwrap --ro-bind / / --unshare-all echo ok` imprimió "ok".

Con las dependencias listas arrancamos Fase B de verdad. **B1** fue el
`registry.py`: el contrato formal de una herramienta. Ahora cada Tool declara
su nombre, su **schema** (el molde JSON que dice qué argumentos acepta — como
un formulario con campos obligatorios), su permiso (auto | ask | deny) y si es
"sandboxable". La clave de seguridad: la validación con la librería `jsonschema`
ocurre ANTES de ejecutar nada — primero revisas el formulario, luego haces el
trámite. Y hay una regla que me gustó particularmente: un tool con permiso
"ask" que no tiene quién lo apruebe NO se ejecuta en silencio; devuelve un
error honesto. Nunca "yolo silencioso".

**B2** fueron las 5 herramientas formales: read_file (ahora paginado: lee de
500 líneas en 500 con aviso honesto de "sigo en la línea X"), write_file,
terminal, search_files (que llama a ripgrep por debajo: `rg --json`, y ojo con
la semántica — exit code 1 no es error, significa "no encontré nada", y así se
reporta) y la joya: **edit** con matching fuzzy de 9 estrategias. ¿Qué es esto? Una
escalera de tolerancia: S1 busca el texto exacto; si falla, S2 ignora espacios
al final de línea; S3 ignora la indentación... hasta S9 que compara solo la
secuencia de palabras. La primera estrategia que encuentre UN único match,
gana. Si encuentra varios, se niega con un error honesto en vez de elegir al
azar. Está probada con 121 tests verdes (32 nuevos hoy), ruff y mypy --strict
limpios, y lo importante: el **baseline** (las 5 tareas de evaluación contra
OpenRouter) sigue en 5/5 — el ratchet no se rompió. Y un smoke real nuevo: el
agente usó search_files + edit contra un calc.py con bug, corrigió SOLO la
línea enferma (la función vecina quedó intacta) y su verify pasó, con 95% de
cache_read.

### QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

Los archivos nuevos, todos bajo ~/code/tlamati/:
- `src/tlamati/tools/registry.py` — Tool + Permission + Registry.execute (escalera
  unknown→schema→permiso→run; todo error → ToolResult(is_error=True)).
- `src/tlamati/tools/files.py` — read_file/write_file/edit; la escalera fuzzy
  (función pura `fuzzy_replace`) es testeable sin tocar disco.
- `src/tlamati/tools/search.py` — search_files vía subprocess de rg.
- `src/tlamati/tools/terminal.py` — terminal foreground, sandboxable=True.
- `src/tlamati/tools/builtin.py` — compone los 5 tools en orden estable
  (el orden importa: las specs viajan en el prefijo cacheable de cada llamada).
- `tests/test_registry.py` (26 tests) y `tests/test_tools_b2.py` (32 tests).

Comandos para replicar la verificación:
```bash
cd ~/code/tlamati
uv run pytest -q            # → 121 passed
uv run ruff check src tests # → All checks passed!
uv run mypy                 # → Success: no issues found in 21 source files
uv cache clean tlamati && uv tool install --reinstall --force --from . tlamati
uv run tlamati-eval --model qwen/qwen3-coder --out evals/check.jsonl  # → 5/5 OK
```
Git/GitHub (hoy estrenamos remoto):
```bash
gh repo create leonardoGH/tlamati --private --source=. --remote=origin --push
git push -u origin main
gh repo edit leonardoGH/tlamati --default-branch main
```
Estado final: main = commit 7b0a36e (B2), subido a github.com/leonardoGH/tlamati
(privado hasta v0.1, como manda el plan).

### Qué decidimos NO construir
- No metimos el flujo RAG de [REDACTED_PROYECTO] dentro de read_file (idea del fundador,
  registrada en el handoff): mezclar lectura cruda con retrieval semántico
  viola responsabilidades; si se aprueba, serían tools NUEVAS opcionales
  (index_corpus / semantic_search) reutilizando el pipeline de [REDACTED_PROYECTO] como
  librería. Decisión pendiente: ¿extra instalable o plugin Fase C+?
- background+poll en terminal se queda para v1.1 (la GUIA lo dice explícito).

### El error del día
Mi primer test de compaction traía Budget(750) de la sesión pasada. Al pasar
de 3 a 5 tools, el prefijo de specs creció a 566 tokens y el test murió en
budget_exceeded aunque TODO funcionaba. Detección: pytest rojo; diagnóstico:
medir el prefijo real con tiktoken. Arreglo: sonda binaria sobre el budget
(750→1600) para encontrar el mínimo real (1100) y dejar 1200 con margen.
Lección: cuando el prefijo crece, los budgets apretados de los tests se
recalibran MIDENDO, no adivinando. Este pitfall ya estaba documentado en el
handoff de Fase A — y aun así me mordió. Los pitfalls documentados hay que
releerlos ANTES, no después.

También hubo un 429/504 de OpenRouter en la primera corrida de baseline (4/5):
no era nuestro código, era rate-limit del upstream. El retry de la tarea
fallida pasó 1/1. Lección: en evaluaciones contra servicios externos, un fallo
siempre se investiga ANTES de tocar código.

**Pregunta abierta para mañana: en B3, cuando el terminal corra dentro de la
jaula bwrap con todo el filesystem en read-only excepto el workdir, ¿qué pasa
con los evals que corren en /tmp? — o sea, ¿la jaula se activa también en el
runner de evaluaciones o solo en el CLI real? La respuesta decide si el
baseline 5/5 sigue siendo comparable.**
