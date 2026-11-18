# HANDOFF FASE E3b → E4 → DOGFOODING — orden decidido por el fundador (18-nov-2026, cierre sesión 16)
# Punto de entrada para sesión con CERO contexto: leer este archivo completo,
# cargar skill_view('tlamati-harness-project'), y seguir §3 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal → Hermes auto-audita
# (pytest + ruff check . + ruff FORMAT --check . [¡sobre TODO el repo, ver §5!] +
# mypy --strict + baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle
# revisar código; evidencia de COMPORTAMIENTO en cristiano. Clase del día al
# cierre (v2; la próxima es CLASE_13 — CLASE_12 ya escrita).

## 1. ESTADO ACTUAL (18-nov-2026 ~01:10, verified)
- main = CLASE_12 commiteada, CI VERDE run 44213300417. Fases A+B+C+D+E1+E2+E3a
  COMPLETAS Y FUSIONADAS. 375 tests verdes.
- Baseline vigente: evals/e3a_check.jsonl = 9/10 (ratchet viejas 5/5 cache 94-95%;
  nuevas 4/5 — instruccion_en_archivo falló LEGÍTIMAMENTE por max_turns=12, es el
  techo medido, no bug). RATCHET: las 5 viejas jamás bajan de 5/5.
- E3a (sesión 16): 5 fixtures media-alta moldeadas en bugs reales del historial
  (multi_archivo, output_grande, git_history+setup.sh determinista,
  instruccion_en_archivo, test_driven) + runner corre setup.sh fail-soft.
- Investigación benchmarks: research/08_BENCHMARKS_EXISTENTES.md (Terminal-Bench 4.1
  capturado en vivo: Qwen3.8-Max+CC=27%, Grok Build=38.8%, caso dirac +17pts mismo
  modelo; harbor OSS = pista gratis; costos $200-16.5k son del cerebro frontier).
- CLASE_12 escrita (edu/DESARROLLO_TLAMATI_CLASE_12.md): "cómo se mide un arnés".

## 2. ORDEN ZANJADO POR EL FUNDADOR (18-nov, NO re-litigar)
1. **E3b** — tabla ARNÉS vía OpenRouter (opencode/codex/hermes/gemini-cli +
   Tlamati, mismo qwen3-coder, 10 fixtures). Correr de MADRUGADA (OpenRouter se
   satura de día: 429 DeepInfra/504 Venice; la ventana buena de esta sesión fue
   ~00:30-01:00).
2. **E4** — docs OSS + SECURITY.md completo + AUDITORÍA DE SEGURIDAD FINAL +
   público v0.1 + PyPI (el gatillo final es del fundador).
3. **DOGFOODING** — empezar a USAR Tlamati nosotros: construir features de la
   plataforma edtech (NeoNubeInt/edtech-plat) CON Tlamati, Hermes auditando.
   Verbal del fundador: "empezar a probar tlamati nosotros con un workflow real
   que iba a hacer en hermes" — PREGUNTAR al inicio de esa sesión cuál es ese
   workflow concreto (candidatos en la skill neonube_int_int_int-edtech-platform: pestaña
   CREAR TU APP/harness, Biblioteca RAG, chatbot 4ª pestaña...).
4. **SPARK DESPUÉS** — la campaña DGX Spark (tabla MODELO 120B/80B/35B) va
   DESPUÉS del dogfooding, no antes. Scripts YA LISTOS en ~/code/enverge-pruebas/
   (startup_1spark_bench.sh = pegar en panel al rentar; bench_spark_from_wsl.sh =
   orquestador idempotente desde WSL; UN modelo a la vez NUNCA cohabitan; fila
   ~7 días; pod genérico con RAM suficiente también vale — el 35B cabe en cajas
   más baratas). research/08 §6 tiene el plan completo.

## 3. E3b — PLAN EJECUTABLE (sesión siguiente)
Meta: la cifra publicable estilo dirac — "MISMO modelo (qwen/qwen3-coder vía OR),
distinto arnés": % resueltas, tokens in/out, turnos, duración. Delta = argumento.

Pasos:
1. $0 primero: verificar arneses headless en esta máquina (claude code 2.1.92 y
   codex 0.133.0 YA instalados; hermes instalado; opencode = vendorizado, falta
   binario `npm i -g opencode-ai` → PREGUNTAR al fundador antes de installs
   globales; gemini-cli opcional).
   - codex: `codex exec` + config.toml model_providers apuntando a OpenRouter
     (verificar que acepte qwen3-coder; sandbox/permissions en modo no-interactivo).
   - hermes: ya corre con OpenRouter nativo (perfil default de esta máquina;
     OJO: usar un perfil/config neutro para que la comparación sea del arnés
     default, no de nuestras skills/memoria — documentar la configuración exacta).
   - opencode: investigar provider OpenRouter + modo no-interactivo (run -p?).
2. Adaptador de corpus: las 10 fixtures son harness-agnostic (instruction.md =
   prompt; verify.py decide). Escribir un runner externo (bash/python, NO toca
   tlamati) que por cada arnés: copia fixture a workspace tmp → corre el arnés
   headless con la instrucción → ejecuta verify.py → JSONL con el MISMO schema
   congelado {task, success, turns?, tokens_in?, tokens_out?, duration_s, error}
   (campos que un arnés no exponga = null honesto, NUNCA inventados).
   Ubicación: bench/ en el repo (nuevo dir, documentar en README).
3. Correr de madrugada con el patrón del vigilante (2 sondas OK seguidas antes
   de suite; donor: /tmp/e3a_watch2.sh de la sesión 16 — reescribirlo, /tmp muere).
   Tlamati con --max-turns 20 en las duras (decisión sesión 16).
4. GASTA centavos por arnés×corrida: OK del fundador ANTES de cada corrida
   completa. Reportar: N arneses × 10 tareas = X corridas.
5. EVALS.md (nuevo, raíz del repo): tabla ARNÉS×modelo con fecha, modelo exacto,
   comando exacto de reproducción, JSONL crudos en evals/benchmark_<fecha>/,
   + sección "contexto público" citando tbench.ai y dirac (research/08).
   Reglas de integridad (anti-cheating documentado en debugml.github.io):
   instruction única, verify decide, cero ayudas inyectadas, timeouts sin tocar,
   versión pública = versión corrida. NUNCA inventar números del competidor:
   si un arnés no corre aquí, se reporta lo que SÍ corrió.
Riesgos: codex/opencode pueden no soportar qwen3-coder vía OR o requerir login
→ investigar ANTES de prometer la tabla completa; hermes con perfil default tiene
skills/memoria que los demás no → documentar o usar perfil limpio; claude code y
grok bot FUERA de la tabla principal (cerebros propietarios — decisión fundador
sesión 16; tabla secundaria out-of-the-box solo si el fundador la pide).

## 4. E4 — CHECKLIST (después de E3b)
1. README.md OSS (install, quickstart, filosofía local-first, tabla de EVALS.md,
   licencia Apache-2.0, comparación honesta).
2. SECURITY.md COMPLETO (stub creado en D2): modelo de confianza (sandbox bwrap,
   escalera de permisos nunca-relaja, trifecta untrusted→ask, MCP produces_
   untrusted SIEMPRE, plugins = código del dueño sin sandbox, ledger audit trail).
3. AUDITORÍA DE SEGURIDAD FINAL (última puerta antes del botón público — decisión
   fundador sesión 15, verbatim: "hagamos todo lo demás y ya al finalizar hacemos
   la auditoría completa para publicar"):
   - research/*.md y edu/*.md: barrer datos personales del fundador (correos,
     rutas /home/, nombres de suscripciones, hosts Enverge/SSH, IPs).
   - fixtures/ y evals/: sin datos sensibles (los JSONL tienen user_id de
     OpenRouter en errores 429 — ¡SANITIZAR o regenerar antes de publicar!
     visto en e3a_check.jsonl: "user_id":"user_3Iga...").
   - `git log --all -p` grep de claves (sk-, ghp_, AKIA, xai-, llaves privadas).
   - confirmar vendor/ y rea-out/ JAMÁS subieron:
     `git log --all --diff-filter=A --name-only | grep -E "vendor/|rea-out/"`.
   - .gitignore correcto (.env, *.db, secrets.*, vendor/, rea-out/, *.jsonl grandes?).
   - autor de commits genérico ("Leonardo <leonardo@local>").
   - Evidencia al fundador EN CRISTIANO; el gatillo final es SUYO.
4. tag v0.1.0 + repo público (gh repo edit --visibility public) + PyPI publish
   (nombre tlamati verificado libre el 14-nov; RE-verificar antes).
5. CLASE_13 al cierre de la sesión que toque ("el delta como argumento" si es
   E3b; "publicar sin quemarse" si es E4).

## 5. PITFALLS HEREDADOS + NUEVOS (sesión 16)
- **CI SCOPE (nuevo, dolió 2 runs rojos)**: el CI corre `ruff check . && ruff
  format --check .` sobre TODO el repo — fixtures/*.py Y edu/*.md (ruff formatea
  hasta los bloques ```python dentro del markdown). Auditoría local SIEMPRE con
  `.` completo, NUNCA `src tests`. Tras crear cualquier archivo nuevo:
  `uv run ruff format .` antes del commit.
- Rate-limit OpenRouter: 0/10 con turns=0/tokens=0 = upstream, NO código. Leer
  campo error SIEMPRE. Patrón vigilante: sonda barata (1 tarea) cada 3-5 min,
  exigir 2 OK seguidas, entonces suite; tope de reintentos; si el fallo NO es
  upstream no reintentar. Ventanas buenas observadas: madrugada.
- `tlamati-eval --task X --out Y` SOBRESCRIBE Y completo — evidencia limpia =
  suite entera. Para las duras: --max-turns 20.
- test_driven puede dar stop_reason=max_turns con success=True: decide verify.py,
  no el motivo de parada. No es contradicción, es diseño.
- git add -A atrapa untracked intencionales (evals/b5_check2/3.jsonl — NO
  borrar, NO commitear): paths específicos siempre.
- git_history fixture: .git NUNCA commiteado dentro del repo; setup.sh siembra
  6 commits deterministas (GIT_AUTHOR_DATE fijos → hashes estables entre
  máquinas). El runner lo ejecuta fail-soft tras copytree (timeout 120s).
- Heredados de la skill (lista completa en SKILL.md): prefijo append-only (caché
  sagrada), policy nunca relaja, run_loop budget= kw-only, 429/504 leer antes de
  tocar código, ruff format ANTES del commit, CI solo corre en main/PR, heredocs
  `git commit -F -` = excepción estable, comandos compuestos && disparan bloqueos
  falsos del parser (protocolo #6: separar en llamadas simples).

## 6. BASELINE REAL (tras cualquier merge que toque corrida; gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/<fase>_check.jsonl        # suite completa de 10
```
Esperado: viejas 5/5 SIEMPRE (ratchet); nuevas reportadas aparte (pueden fallar
legítimamente por dificultad — el punto es medir). evals ENJAULADOS con bwrap;
ningún servidor MCP en la suite.

## 7. DOGFOODING (post-E4) — notas para arrancar
- Instalar tlamati de producción: `uv tool install --from . tlamati` (o pipx).
- Primer workflow real de NeoNubeInt: PREGUNTAR al fundador cuál es "el workflow
  real que iba a hacer en hermes" (skill neonube_int_int_int-edtech-platform cargada en
  sesión 16 como contexto; candidatos: spike harness CREAR TU APP, Biblioteca
  RAG proyecto-legal, chatbot 4ª pestaña).
- Regla: Tlamati construye, Hermes AUDITA (tests + lint + evidencia de
  comportamiento) — mismo protocolo fundador/Hermes pero un nivel abajo.
- Cada bug de Tlamati que aparezca en dogfooding → fixture nueva o issue E4+.
  El dogfooding ES el benchmark más honesto.
- Separación de proyectos: convenio ~/code/CONVENIOS_PROYECTOS.md — CERO código
  cruzado; reutilizar = COPIAR con encabezado ORIGEN.

-- Hermes, 18-nov-2026 sesión 16. main = CI verde (run 44213300417), 375 tests,
-- baseline 9/10 (ratchet 5/5). Orden: E3b (madrugada) → E4 (auditoría+público)
-- → dogfooding NeoNubeInt → campaña Spark (scripts listos en ~/code/enverge-pruebas/). --
