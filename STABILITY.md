# STABILITY.md — qué promete tlamati (y qué no)

Sin marketing, misma filosofía que SECURITY.md: los límites explícitos son
feature. Este documento dice en qué puede confiar un script, un agente o una
integración construida sobre tlamati, cómo se avisan los cambios que rompen,
y qué queda fuera de la promesa.

Donor: gbrain `docs/STABILITY.md` (adaptado, no copiado — tlamati es más
pequeño y su promesa es proporcional).

## Canales

- **alpha (`main`)**: desarrollo continuo. Puede cambiar cualquier cosa entre
  un commit y el siguiente, con una excepción: los breaking changes de la
  superficie estable se registran en `CHANGELOG.md` (sección "Unreleased")
  antes o en el mismo commit que los introduce.
- **releases (tags `v*`)**: la promesa de abajo aplica de tag a tag. La
  release actual es `v0.1.0`; lo que vive en `main` después del tag es alpha
  hasta el siguiente.

## Qué es estable desde v0.1

1. **Formato de archivos de memoria**: `MEMORY.md` y `USER.md` — markdown de
   entradas separadas por `§`. Son la ÚNICA fuente de verdad de la memoria.
   Un archivo escrito por una versión vieja de tlamati siempre lo lee una
   nueva.
2. **Formato de SKILL.md**: frontmatter YAML (`name`, `description`) + cuerpo
   markdown, compatible con agentskills.io. Campos desconocidos del spec se
   ignoran sin crashear.
3. **La CLI documentada**: comandos y flags que aparecen en `tlamati --help`
   y en el README. Flags no documentadas no entran en la promesa.
4. **Códigos de salida** (headless; contrato E2):

   | código | significado |
   |---|---|
   | 0 | `end_turn` — el agente terminó su trabajo |
   | 1 | `max_turns` — turnos agotados (tarea incompleta, no es error) |
   | 2 | mal uso / arranque fallido (sin api key, config inválida, argparse) |
   | 3 | `budget_exceeded` — presupuesto de contexto excedido |
   | 4 | `error` — fallo de provider o del loop (stop_reason desconocido = fail-closed aquí) |
   | 5 | `aborted` — abortado por el usuario |
   | 6 | `refusal` — el modelo se rehusó |
   | 7 | `max_tokens` — tope de tokens de salida |
   | 8 | `stall` — bucle detectado |

5. **Contrato `--json` (JSONL)**: stdout es EXCLUSIVO del stream (un objeto
   JSON por línea con `ts`, `event` y payload plano); stderr queda humano; el
   evento final es SIEMPRE `result` con `stop_reason`, `usage` y `exit_code`.
   Un consumidor de CI no necesita parsear nada más para decidir.
6. **`render_for_prompt()` byte-idéntico**: el bloque de memoria/instrucciones
   que entra al system prompt no cambia de bytes entre releases si el
   contenido no cambia (prefijo cacheable sagrado — regla del commit
   `7751663`). Ningún metadato nuevo (sidecar, tiers) se renderiza al prompt.
7. **Caps de memoria**: 100 entradas / 24,000 chars por target. Subirlos es
   un cambio compatible; bajarlos, breaking.
8. **Advisory nunca muta**: los gaps del dream (G2), las entradas frías de
   `memory status` (M8b) y los hallazgos de `memory lint` (M8c) son
   informativos. No escriben, no borran, no reordenan archivos de memoria.
   `memory lint` devuelve exit 0 siempre. Nada se borra en silencio.

## Qué NO se promete

- **APIs internas de `src/tlamati/**`**: importables, pero no son contrato.
  La superficie estable es la CLI y los formatos de archivo.
- **Campos del sidecar `.meta.json`**: es DERIVADO de MEMORY.md/USER.md,
  reconstruible, fail-soft (la memoria manda; el sidecar nunca bloquea una
  escritura). Puede migrar con una version key en cualquier release.
- **Wording de mensajes humanos** (todo lo que no es `--json`), flags
  internas/no documentadas.
- **Ranking de búsqueda, velocidad y resultados exactos de features que
  dependen del modelo** (consolidación/dream, routing): son no-deterministas
  por naturaleza.
- **La TUI**: interactiva y en evolución; su layout y keybindings no son
  contrato.

## Cómo se avisan los breaking changes

- Todo cambio que rompa la superficie estable se registra en
  `CHANGELOG.md`, sección "Unreleased", con la etiqueta `BREAKING`.
- **Regla gbrain: los removals necesitan deprecation.** Un comando, flag o
  comportamiento documentado se anuncia primero, sigue funcionando al menos
  1 release menor con aviso, y solo entonces se remueve.
- **Excepción única: seguridad y pérdida de datos.** Un fix de un hueco de
  seguridad o de algo que pierde datos puede cambiar comportamiento de
  inmediato; su entrada en el changelog dice cuál de los dos es y qué hay
  que hacer.
- Un cambio de default cuenta como breaking (ver el registro abajo).

## Registro de breaking changes

- **21-nov-2026 (Unreleased, post-v0.1.0) — SEC.1: default de red OFF→ON.**
  El sandbox ya no bloquea la red por defecto (`config.yaml` gobierna;
  precedencia: flag CLI > config > default `net=True`). Un agente que antes
  decía "no tengo red" ahora la tiene, con la trifecta letal como compensación
  (egreso AUTO→ASK tras consumir contenido no-confiable — ver SECURITY.md).
  Commit `b25745e`. Es un cambio de default deliberado y documentado, no un
  accidente: la red OFF por defecto hacía que el harness mintiera sobre sus
  capacidades.
