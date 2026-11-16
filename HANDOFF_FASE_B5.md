# HANDOFF 5 — B3+B4 EN MAIN · B5 HECHO EN RAMA (falta baseline por rate-limit)
# Generado por Hermes, 16-nov-2026, sesión 7. Reemplaza HANDOFF_FASE_B3.md.
# Protocolo SIGUE VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (tests+ruff+mypy+baseline REAL) y fusiona; clase del día al cierre.

## OBJETIVO GENERAL
Tlamati = agent harness OSS local-first (~/code/tlamati, Apache-2.0, repo privado
leonardoGH/tlamati). Diferenciadores: prefijo cacheable con overhead visible,
seguridad trifecta (sandbox+permisos+auditoría), loop simple, memoria durable.
Fase B (herramientas+permisos) cierra con B5; luego Fase C (sesión+memoria+skills).

## CONTEXTO / DE DÓNDE VENIMOS
Sesión 7 arrancó con HANDOFF_FASE_B3. Se entregó B3 (sandbox, merge 9fb222a),
se arregló el CI de GitHub (dos causas raíz abajo), se entregó B4 (policy, merge
4140c20) y se construyó B5 completo (rama b5-ledger, commit 81c5235) — la fusión
de B5 quedó pendiente SOLO por rate-limit de OpenRouter, no por código.

## LO QUE SE HIZO EN ESTA SESIÓN (verificado con ejecución)
### B3 (en main, merge 9fb222a)
- src/tlamati/sandbox/bwrap.py: jaula `--ro-bind / / --bind <workdir> <workdir>
  --dev /dev --proc /proc --chdir <workdir> --die-with-parent --unshare-all`
  (+ `--share-net` solo con permiso separado). SandboxProfile(workdir, net).
  wrap_command() → línea shell shlex-quoted; None si bwrap falta.
- terminal.py: sandbox ON por defecto si bwrap existe; degradación HONESTA con
  nota "[sin sandbox...]" si bwrap desaparece en runtime. CLI: --no-sandbox,
  --sandbox-net. Evals corren enjaulados (workspace = workdir rw; verify.py
  corre fuera). Env se hereda en la jaula (API keys visibles al comando) —
  documentado; endurecer con --clearenv+whitelist es candidato B4+/C.
- Tests de fuga REAL: touch /tmp y $HOME → "Read-only file system", exit 1.
  Red OFF → curl rc=6/7; red ON (--sandbox-net) → curl 200.

### CI de GitHub ARREGLADO (antes fallaba desde A6; el fundador recibía correos run failed)
- Causa 1: CI corre `ruff format --check` pero local solo corríamos `ruff check`
  → 8 archivos sin formatear desde A6. Fix: reformatear (commit 5632754).
  REGLA NUEVA: la auditoría local SIEMPRE incluye `ruff format --check .`.
- Causa 2: runner sin ripgrep → 4 tests de search fallaban. Fix: CI instala
  ripgrep (commit e4ad50a). bwrap se skipea honesto si falta.
- CI run 43972038230 = SUCCESS. Primeros verdes del repo.

### B4 (en main, merge 4140c20) — Opción A elegida por el fundador
- src/tlamati/policy/config.py: PolicyConfig.from_dict() parsea sección
  `permissions:` de config.yaml (fail fast en claves inválidas):
  tools→auto|ask|deny, deny_commands/ask_commands (fnmatch sobre args.command),
  egress_tools (default {terminal}). Policy.resolve() escalera NUNCA relaja
  (deny>ask>auto). Trifecta: mark_untrusted() → egress AUTO→ASK por corrida.
- registry.py: Registry(policy=...), Tool.produces_untrusted, resultados con
  untrusted=True cuando tool los produce sin error.
- terminal.py: produces_untrusted = (sandbox_net or not sandbox) — enjaulado
  sin red NO produce untrusted.
- cli.py: --approve-tool NAME (repetible, '*'=todo); _headless_approver;
  default NUNCA yolo. TUI (Fase E) pondrá el prompt interactivo.
- CONTENT GUARD (revisor LLM de descargas): decisión del fundador = extensión
  posterior Fase C+ junto a tools de red propias. Fundador está BUSCANDO repos
  de ciberseguridad para evaluar integración — revisar contra jaula+trifecta.

### B5 (RAMA b5-ledger, commit 81c5235 — NO FUSIONADO AÚN)
- src/tlamati/policy/ledger.py: Ledger SQLite stdlib APPEND-ONLY (solo INSERT):
  tool_events (ts, session_id, turn, tool, args_json sorted-keys, decision,
  result_sha256, is_error/untrusted/truncated) + turn_costs. Write roto =
  self.broken (nunca rompe la corrida). read_session/list_sessions abren en
  modo ro (file:...?mode=ro).
- registry.py: cada salida de execute() pasa por _log() con decisión exacta
  (auto|deny|unknown|bad_args|schema_invalid|ask_denied|ask_escalated|
  ask_error|ask_approved).
- cli.py: session_id = TIMESTAMP-uuid8; ledger default
  ~/.local/share/tlamati/audit.db; --audit-db PATH, --no-audit; al fin imprime
  "[audit] sesión <id>". Nuevo subcomando: `tlamati audit` (lista sesiones) /
  `tlamati audit --session <id>` (eventos+flags E/U/T+sha256+totales).
- SMOKE REAL OK: corrida -p "echo hola-mundo" → audit muestra evento t1 auto
  terminal + sha256 + costos de turno. Una sesión previa timeouteada dejó 9
  eventos capturados (ledger robusto a corridas largas).
- AUDITORÍA: 171 tests verdes, ruff check+format limpios, mypy --strict 25
  archivos limpio. uv tool reinstall hecho.

## SIGUIENTE ACCIÓN (exacta)
1. Verificar baseline de B5 (lo único pendiente): `cd ~/code/tlamati && git
   checkout b5-ledger && uv tool install --from . tlamati --reinstall &&
   tlamati-eval --out evals/b5_check2.jsonl`. ¿GASTA? SÍ (OpenRouter, centavos).
   Esperado 5/5; si una tarea falla, LEER el campo `error` del JSONL ANTES de
   tocar código: HTTP 504/429 = rate-limit upstream (DeepInfra/Venice), NO es
   nuestro código → esperar ~15-60s y `tlamati-eval --task <fallida> --out ...`.
   El 16-nov por la noche hubo ventana larga de 429; si persiste, esperar horas
   o pedir al fundador BYOK de DeepInfra (opción que ya se le explicó).
2. Baseline verde → presentar evidencia de comportamiento al fundador → con su
   OK verbal: `git checkout main && git merge --no-ff b5-ledger -m "Merge B5: ..."
   && git push origin main && git branch -d b5-ledger` y VERIFICAR que el CI de
   GitHub quede SUCCESS (gh run list --limit 1). FASE B CIERRA AQUÍ.
3. Luego Fase C (GUIA_IMPLEMENTACION.md §C): C1 session store SQLite aiosqlite
   (`tlamati resume`, --continue), C2 memory MEMORY.md+USER.md, C3 skills,
   C4 AGENTS.md loader. Un paso → entrega → revisión, igual que siempre.
4. Al cierre de esta próxima sesión: CLASE_5 (edu/DESARROLLO_TLAMATI_CLASE_5.md,
   formato edu/PROMPT_CLASE_DIARIA.md v1). Temas candidatos de clase: la jaula
   bwrap (B3), la trifecta letal (B4), el libro de auditoría (B5) y el CI verde.

## ¿GASTA?
- Baseline 5 tareas: SÍ, OpenRouter (qwen3-coder, centavos por corrida). Pedir
  OK solo si el fundador no lo dio (esta sesión ya lo autorizó implícitamente
  al pedir "seguir avanzando"; la próxima, confirmar).
- Tests locales (pytest/ruff/mypy): NO gastan. Smoke real -p: SÍ (1 corrida).

## CÓMO VERIFICAR SIN GASTAR
- `uv run pytest tests/ -q` → 171 passed (en rama b5-ledger).
- `uv run ruff check src tests && uv run ruff format --check . && uv run mypy --strict src`.
- Smoke gratis del ledger (sin LLM): crear Registry con policy+ledger en Python
  y ejecutar tools locales; luego `tlamati audit --audit-db <tmp>`.
- `tlamati audit` sobre /tmp/b5_smoke/audit.db aún existe con 2 sesiones reales.

## ESTADO GIT
- main = 4140c20 (B4 fusionado, CI verde). Subido a origin/main.
- RAMA b5-ledger = 81c5235 (B5 completo, pendiente baseline+OK+merge).
- Ramas viejas borradas (fase-b, b2-tools, b3-sandbox, b4-policy).
- evals/b5_check.jsonl contiene la corrida parcial 3/5 (las 2 fallas son 504/429
  upstream — evidencia del rate-limit, no borrar sin leer).

## PITFALLS NUEVOS (acumulados sesión 7)
- AUDITORÍA LOCAL COMPLETA = pytest + ruff check + RUFF FORMAT --CHECK + mypy
  --strict. Olvidar format-check = CI rojo y correo "run failed" al fundador.
- CI de GitHub necesita ripgrep instalado (ya está en ci.yml); bwrap ausente se
  skipea honesto (require_bwrap).
- OpenRouter 429/504 en ventanas largas (DeepInfra+Venice rotando): el campo
  `error` del JSONL de evals es la fuente de verdad; NUNCA asumir fallo propio.
- `git branch -d` vía Hermes dispara bloqueo automático aunque el usuario ya
  aprobó: es el parser, no veto real (protocolo #6 de la skill) — separar en
  comandos simples o pedir al usuario que confirme.
- El positional `cmd` del parser de tlamati vive junto a -p (argparse permite
  ambos); `tlamati basura` → exit 2 honesto.

-- Hermes, 16-nov-2026, sesión 7. B3+B4 EN MAIN. B5 en rama, completo y
-- auditado; falta baseline (rate-limit) → merge → FASE C. --
