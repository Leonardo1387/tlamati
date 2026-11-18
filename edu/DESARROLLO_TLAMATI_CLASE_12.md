# Desarrollo Tlamati — Clase 12
## 17/18-nov-2026: Cómo se mide un arnés — benchmarks ajenos, fixtures propias y la carrera justa

En la clase 11 le dimos dos caras al agente: el modo robot (`--json` para CI) y la pantalla viva (la TUI). Hoy usamos esas dos caras para algo más grande: **medir**. Un arnés que no se mide es una opinión; un arnés con números es un argumento. Esta clase cubre tres cosas que pasaron en una sola sesión: investigar los benchmarks que YA existen en el mundo (para no inventar la rueda ni números), construir 5 tareas de prueba nuevas moldeadas en nuestros propios cicatrices, y armar la infraestructura para correr todo esto barato en un DGX Spark rentado. Y cierra con la corrida real: 9/10.

## 1. PRIMERO, MIRAR QUÉ HICIERON LOS DEMÁS (investigación antes de código)

El fundador pidió: "investiga benchmarks que ya se han hecho sobre estos arneses, incluyendo grok bot y claude code". Regla de ingeniería que aparece una y otra vez en este proyecto: **antes de construir, leer el estado del arte**. Se nos habían adelantado — y eso es buena noticia.

Herramientas usadas y cómo:

```
# 1. El leaderboard oficial (navegador real, datos capturados en vivo)
https://www.tbench.ai  → Terminal-Bench 4.1

# 2. Búsqueda de repos en GitHub vía API (curl + json, sin navegador)
curl -s "https://api.github.com/search/repositories?q=terminal-bench+in:name&sort=stars"

# 3. Historias de Hacker News vía Algolia (API pública, sin scraping)
https://hn.algolia.com/api/v1/search?query=terminal-bench&tags=story
```

Lo que encontramos (todo con fuente y fecha, guardado en `research/08_BENCHMARKS_EXISTENTES.md`):

- El leaderboard oficial YA es una matriz **arnés × modelo**: Claude Code con Opus 5.5 = 65.8%, Codex con GPT-6.1 = 60.9%, Grok Build con Grok 4.7 = 38.8%. Exactamente la tabla que nuestro PRD quiere publicar a escala propia.
- **Nuestra familia de modelos ya tiene número público**: Qwen3.8-Max + Claude Code = 27.0%.
- El costo del leaderboard es del CEREBRO, no de la PISTA: las corridas cuestan $200–$16,500 porque usan modelos frontier carísimos. El corpus de tareas (harbor-framework/terminal-bench) es open source y gratis.
- El caso dirac (HN, días antes de nuestra sesión): un agente OSS sacó 65.2% contra 47.8% del agente oficial de Google **con el mismo modelo** — +17 puntos solo por arnés. Cita del autor: "es asombroso cuánto importa el arnés". Ese es nuestro argumento, vivo y reciente.
- Hay tramposos documentados (debugml.github.io/cheating-agents): agentes que se inyectan archivos de ayuda o modifican timeouts. Moraleja: nuestras pruebas deben ser limpias por diseño — la instrucción es la única ayuda, el verificador decide, y se publica el comando exacto de reproducción.

### LA TEORÍA DETRÁS: benchmark propio vs benchmark estándar

Dos caminos para probar que tu software es bueno. El **benchmark estándar** (Terminal-Bench, SWE-bench) tiene credibilidad externa: cualquiera puede comparar tus números con los del leaderboard porque las tareas son las mismas. El **benchmark propio** (nuestras fixtures) es barato, rápido y mide exactamente lo que te importa — pero nadie externo lo conoce, así que solo vale si publicas el corpus Y el método (por eso nuestras fixtures viven en el repo público). La práctica madura: usar el propio para el día a día (ratchet de Osmani: cada merge debe mantener el baseline) y el estándar para las afirmaciones públicas. Donor del concepto: la propia Terminal-Bench (pista pública) + nuestros baselines A7 (ratchet interno).

## 2. LA CARRERA JUSTA: por qué "mismo modelo" lo es todo

El fundador preguntó "¿a qué te refieres con 'del mismo modelo'?". La respuesta es el corazón metodológico del proyecto:

- El **modelo** es el cerebro (qwen3-coder, un LLM que contesta por API).
- El **arnés** es el cuerpo: cómo le presentas la tarea, qué herramientas le das, cómo recortas el contexto, cómo cuidas la caché.

Si Tlamati corre con un cerebro y Claude Code con otro, una victoria no prueba nada ("ganaste porque tu modelo era mejor"). Si TODOS corren con el mismo cerebro, la diferencia es 100% del arnés. Por eso claude code y grok bot quedan fuera de la tabla principal (viven atados a sus modelos propietarios) y entran opencode, codex y hermes (aceptan cualquier endpoint compatible con OpenAI).

## 3. E3a: CINCO FIXTURES NUEVAS, MOLDEADAS EN CICATRICES REALES

Decisión de diseño de esta sesión (del fundador, tras discutir pros y contras): las tareas nuevas NO se copian del historial de sesiones (arrastraría datos personales al repo público y daría ventaja de local a Tlamati), pero SÍ se **moldean** en la FORMA de los bugs que nos dolieron de verdad. Código limpio, dificultad real. Las cinco, con su cicatriz de origen:

| Fixture | Qué mide | Bug real que la inspiró |
|---|---|---|
| `multi_archivo` | bug repartido en 4 archivos (config normaliza claves a minúsculas; informe usa `.get("Impuesto", 0.16)` con default silencioso) | la colisión `loaded` de D3: el fallo lejos de la causa |
| `output_grande` | log de 3,000 líneas con UNA línea FATAL cerca del final | nuestro truncado M1 — el arnés que no trunca se ahoga |
| `git_history` | repo con 6 commits; identificar al culpable por arqueología git y escribir su hash | arqueología de sesión (git bisect mental que hacemos a diario) |
| `instruccion_en_archivo` | SPEC.md con 6 reglas y orden de prioridad; el validador viola 4 | contratos v2 (PROMPT_CLASE_DIARIA): leer el doc entero y cumplirlo EXACTO |
| `test_driven` | 10 tests unittest, exactamente 4 fallan; iterar edit→test→edit | el off-by-one de `truncar` y el Markdown en ráfaga de E1 |

### Técnica nueva: setup.sh — la semilla programática

`git_history` no puede llevar su repo `.git` commiteado dentro del repo (git no permite anidar repos limpiamente, y los hashes dependerían de la fecha de clonado). Solución: la fixture lleva un `setup.sh` que construye los 6 commits al vuelo, con **fechas fijas** (`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`), autor genérico y mensajes estables → los hashes son IDÉNTICOS en cualquier máquina. Determinismo = reproducibilidad = benchmark serio.

El runner aprendió un truco nuevo (15 líneas): tras copiar la fixture al workspace, si existe `setup.sh`, lo ejecuta con timeout y fail-soft (si falla, la tarea corre igual y verify.py decide con error honesto — nunca rompemos la corrida por la siembra).

```python
# src/tlamati/evals/runner.py (extracto real)
setup = workdir / "setup.sh"
if setup.is_file():
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        subprocess.run(["bash", str(setup)], cwd=workdir,
                       capture_output=True, text=True, timeout=120)
```

### La invariante de toda fixture: la semilla FALLA

Un test recorre las 10 fixtures y verifica que CADA semilla falla antes del arreglo (`test_seeds_all_fail_before_fix`). Si una pasara de entrada, la tarea no mide nada — sería un examen con la respuesta impresa. Además, cada fixture nueva trae su propio test de camino verde (p.ej. `git_history`: sembrar, resolver con el hash correcto, confirmar VERIFY OK, y confirmar que un segundo workspace produce los mismos hashes).

Comandos para reproducir (todo $0, sin red):

```
cd ~/code/tlamati
uv run pytest tests/ -q          # 375 verdes (3 nuevos de E3a)
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy --strict src         # 47 archivos limpios
```

## 4. LA CORRIDA REAL: cuando la red es el enemigo (y cómo no engañarse)

Aquí está **el error del día**, y no fue de código: la primera corrida real de la suite dio **0/10**. ¿Bug nuestro? No. Regla del proyecto: *leer el campo `error` del JSONL antes de tocar código*. Las 10 líneas decían lo mismo: `HTTP 504 ... DeepInfra 429: qwen/qwen3-coder is temporarily rate-limited upstream`. OpenRouter (el intermediario que rota entre proveedores) estaba saturado: los requests ni llegaban al modelo (turns=0, tokens=0).

Tres cosas que hicimos, en orden:

1. **Reintentar con espera** (60 s, 180 s): seguía saturado. No quemar la suite completa a ciegas.
2. **Sonda barata**: en vez de reintentar las 10 tareas, sondear UNA (la más barata) para preguntar "¿respiró?".
3. **Vigilante en background** (`/tmp/e3a_watch2.sh`): bucle que sondea cada 3 minutos y exige **2 sondas OK seguidas** antes de lanzar la suite completa (un respiro falso de una sola llamada no basta — aprendimos eso del intento que dio 6/10 con errores intercalados). Tope: 3 intentos de suite; si los fallos NO son de upstream, no reintenta (fallo real = investigar, no repetir).

Resultado final, con upstream sano: **9/10 OK**.

```
task                     ok     turns  stop        in      cache%
conversor                True   4      end_turn    4848    94
crear_modulo             True   3      end_turn    3397    94
git_history              True   9      end_turn    14259   94   ← arqueología real
import_roto              True   4      end_turn    4780    94
instruccion_en_archivo   False  12     max_turns   41431   94   ← fallo por DIFICULTAD
multi_archivo            True   4      end_turn    7635    86
offbyone                 True   4      end_turn    4742    94
output_grande            True   4      end_turn    35968   70   ← aguja en 3k líneas
promedio                 True   5      end_turn    6208    95
test_driven              True   12     max_turns   39331   93   ← iteró hasta pasar los 10
```

Lecturas honestas:

- **Ratchet intacto**: las 5 viejas dieron 5/5 con cache_read 94-95%. Ningún merge bajó el baseline (Osmani).
- **El fallo es el dato**: `instruccion_en_archivo` agotó los 12 turnos con una regla de prioridad mal puesta. No es un bug del arnés ni de la fixture — es exactamente lo que un benchmark debe revelar: dónde queda el techo del conjunto modelo+arnés con turnos limitados. Con `--max-turns 20` quizá pase; eso lo medirá la campaña Spark (que ya usa 20).
- **test_driven se pasó de turnos y AÚN así pasó el verify**: el stop_reason dice max_turns pero success=True, porque lo que decide es verify.py, no el motivo de parada. Separar "por qué paró el loop" de "¿está resuelta la tarea?" es lo que hace confiable al JSONL.

### LA TEORÍA DETRÁS: el benchmark como instrumento, no como examen

Un examen se aprueba o se reprueba; un instrumento mide. Cuando diseñamos la fixture que FALLÓ, no la diseñamos para que Tlamati luciera bien — la diseñamos para encontrar el techo. Si todas las tareas dieran 10/10, la suite no discriminaría nada (por eso el leaderboard real usa tareas que cuestan $2k correrlas: si todo pasara, no mediría). Patrón reusable: **una suite donde todo pasa siempre está desperdiciando resolución**. Donor del concepto: Terminal-Bench (dificultad calibrada para que la tabla discrimine) y el ratchet de Osmani (research/01).

Y sobre los fallos de red: **la evidencia cruda se commitea tal cual** (`evals/e3a_check.jsonl`, 9/10 incluido el fallo). Un benchmark donde solo se publican las corridas bonitas es marketing, no ciencia.

## 5. LA INFRAESTRUCTURA BARATA: DGX Spark + modelos abiertos, uno a la vez

El fundador propuso: rentar un DGX Spark ($0.90/h) y correr las pruebas contra los modelos abiertos cuantizados FP4 que ya servíamos en el enjambre — 120B, coder-80B y 35B. Con una regla explícita: **nunca cohabitan**; se sirve uno, se prueba, se apaga, sigue el siguiente (los 3 juntos ni caben ni son comparables — cada corrida debe tener la caja completa para el modelo medido).

La aritmética que hace esto posible: el costo del leaderboard ($2k-16k) es del cerebro frontier. Con modelos locales en caja rentada, el costo por token es $0 marginal; pagas solo la renta. Una campaña completa (3 modelos × 10 fixtures) cabe en decenas de dólares de alquiler, no miles de dólares de API.

Se construyeron dos scripts (en `~/code/enverge-pruebas/`, verificados con `bash -n`):

```bash
# 1. startup_1spark_bench.sh — se PEGA en el panel "+ startup script" al rentar:
#    clocks limitados (fix termal), imagen vLLM pre-descargada, e instala
#    el helper serve_model.sh {stop|supervl|coder|q35|status}

# 2. bench_spark_from_wsl.sh — orquestador desde WSL (túnel SSH vivo):
bash bench_spark_from_wsl.sh user@<host>.spark-NN.ssh.enverge.dev
#    rsync del repo → por cada modelo EN ORDEN (120B→80B→35B):
#      stop anterior → serve → esperar endpoint (hasta 60 min por descargas
#      de 24-78 GB primera vez) → tlamati-eval --base-url http://localhost:8000/v1
#      --max-turns 20 → traer JSONL a evals/benchmark_spark/ → stop
#    idempotente: si el túnel muere, reconectar y relanzar (salta lo hecho)
#    genera RESUMEN.md con la tabla final
```

Detalles que vienen de la experiencia acumulada (esto ES el valor de documentar pitfalls):

- `--enable-prefix-caching` en vLLM: nuestra caché sagrada funciona igual contra servidor local — el cache_read del JSONL seguirá siendo medible.
- `OPENROUTER_API_KEY=*** en la corrida local: vLLM no valida keys, así que NINGÚN secreto real viaja a la caja rentada.
- Clocks limitados 300-2200 MHz ANTES de servir (thermal shutdown documentado en foro NVIDIA para el 120B).
- Recipes de serving copiadas del `startup_4spark_supervl.sh` probado (speculative decoding dflash para el 120B, tool-call-parser qwen3_coder).
- Idempotencia como diseño, no como parche: los túneles Enverge MUEREN (lección de spark-26), así que el orquestador asume que lo van a relanzar a medias.

Sobre "¿puedo rentar cualquier pod, no solo Spark?": sí en principio — lo que ata el diseño no es la marca sino (a) GPU con ~125 GB+ de memoria unificada/VRAM para los modelos FP4, y (b) que acepte nuestro startup script. Un pod genérico con la RAM suficiente sirve igual; si cuesta más por hora, la cuenta sigue siendo buena porque el gasto grande (API frontier) desaparece. Queda anotado como opción de la campaña.

## 6. LO QUE SIGUE (gancho)

E3a está fusionada en main (33e8ca9, CI verde). Falta:

1. **E3b en OpenRouter** (centavos, de madrugada cuando respira): la tabla ARNÉS — Tlamati vs opencode vs codex vs hermes, mismo qwen3-coder, las 10 fixtures. Es el delta publicable estilo dirac, versión nuestra.
2. **Campaña Spark** cuando haya caja: la tabla MODELO — mismo Tlamati, cerebros 120B/80B/35B locales, y (nivel 2) el corpus oficial de Terminal-Bench auto-corrido.
3. **Dogfooding** (decisión nueva del fundador esta sesión): empezar a CONSTRUIR COSAS con Tlamati — los features de la plataforma edtech (NeoNubeInt) hechos por Tlamati, con Hermes auditando. El mejor benchmark de un arnés es que su dueño lo use para trabajar de verdad. Los bugs que aparezcan así valen más que cualquier fixture sintética.
4. **E4**: docs OSS, SECURITY.md completo, auditoría de seguridad FINAL y el botón de público v0.1 (el gatillo es del fundador).

Serie: clase 11 (las dos caras del agente) → **clase 12 (cómo se mide un arnés)** → clase 13 (el delta como argumento: la tabla arnés×modelo con números nuestros).

---
*Números reales de la sesión: 375 tests verdes · suite real 9/10 (ratchet 5/5, cache 94-95%) · 3 intentos de corrida bloqueados por rate-limit upstream · 2 scripts Spark verificados · investigación con 3 fuentes capturadas en vivo (tbench.ai, GitHub API, Algolia HN). Commits: 81a16d8 (fixtures+research), 33e8ca9 (baseline real), fusión a main + CLASE_12.*
