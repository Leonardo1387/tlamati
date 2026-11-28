# Desarrollo Tlamati — Clase 24
## 26-nov-2026: La tecla secuestrada — por qué un `priority=True` te robó el copiar, y cómo devolverlo sin romper el detener

Hoy no construimos una función nueva: **devolvimos una tecla**. El fundador reportó que `ctrl+c` en la TUI lo sacaba del sistema cuando el agente no corría, imposibilitando copiar texto seleccionado. Síntoma real, causa de dos líneas, y la lección es un patrón que vas a reusar cada vez que una app de terminal "se pelea" con una combinación de teclas: **quién consume la tecla primero**.

### La regla de oro que explica todo

En una TUI hay dos mundos que quieren la misma tecla:

1. **Editar/copiar texto** (lo que esperas de cualquier terminal).
2. **Controlar la app** (detener, salir, atajos).

Textual 8.2.8 ya eligió por ti: `ctrl+c` **copia** (el `TextArea` y el `Input` lo tienen como binding propio, y la pantalla `Screen` copia la selección hecha con el mouse). Nosotros habíamos añadido, en el commit `0ce5e4e` (B3), este binding:

```python
(Binding("ctrl+c", "interrupt", "Detener", priority=True),)
```

El `priority=True` es el ladrón. Un binding prioritario de la App se evalúa **antes** que cualquier widget: la tecla nunca llegaba a copiar. Y pe-or: en reposo (sin corrida) hacía `self.exit()` — la app se moría en lugar de copiar.

### El fix completo (4 cambios, un archivo de código + un archivo de tests)

En `src/tlamati/tui/app.py`:

1. **Quitar `priority=True`** del binding. Así la cadena de consumo queda:
   `bindings priority de App` → `widget enfocado (TextArea copia; si NO hay selección lanza SkipAction)` → `Screen (copia selección del transcript)` → `bindings NO-priority de App (nuestro interrupt)`.
   Es decir: hay selección → copia; no hay selección → cae a "detener".
2. **`action_interrupt` en reposo ya no hace `exit()`**: muestra una nota `[ctrl+c] nada activo; ctrl+q sale, con selección copia`. Salir es `ctrl+q`, que ya existía y además cierra la sesión honestamente en `on_unmount` (sessions.db queda con `stop_reason` correcto). Perdimos algo de "salir rápido", ganamos la tecla.
3. Actualizar el hint de bienvenida: `"ctrl+c copia selección o detiene al agente…"`.
4. Con corrida activa **nada cambió**: primer golpe aborta (stop_reason=`aborted`), segundo fuerza — los tests B3 de `tests/test_tui_e1.py` siguen verdes sin tocarlos.

En `tests/test_tui_e1.py` — tres tests nuevos que son, en realidad, el contrato del fix:

- `test_ctrl_c_idle_does_not_exit_app`: en reposo, la app **no** muere (`app._exit` sigue False) y el aviso aparece en el transcript.
- `test_ctrl_c_copies_textarea_selection`: teclear texto, `select_all()`, `ctrl+c` → `app._clipboard == "copiame"`. La aserción fuerte: **nuestro binding no-priority pierde contra TextArea vía SkipAction**.
- `test_ctrl_c_no_selection_still_interrupts`: sin selección y con corrida activa → abort (regresión B3 cubierta).

### El error del día (para que no lo repitas)

Escribí la aserción del aviso leyendo `s.renderable` de los `Static` del transcript, y el test falló en silencio. Textual 8 guarda el contenido original en `Static.content` (y lo materializa en `Static.visual` al renderizar). Fix de una línea. Lección transferible: **cuando un test de UI falla en "no encuentro el texto", no asumas el atributo — ábrelo en el package instalado** (`.venv/lib/python3.12/site-packages/textual/widgets/_static.py`, 20 segundos) y lee el property real.

Otra trampa del día: los bloqueos del parser de comandos (dos intentos fallidos con `sed`+subshell) no son el sistema negándose a trabajar — son reglas de seguridad del entorno. Dos reintentos y declaro, como pide el fundador; la salida fue usar `read_file`/`patch` en vez de `sed` en terminal.

### Cómo replicarlo (comandos exactos de la sesión)

```bash
cd ~/code/tlamati
git checkout -b fix/ctrl-c-copy
# editar src/tlamati/tui/app.py y tests/test_tui_e1.py (ver arriba)
.venv/bin/python -m pytest tests/test_tui_e1.py -q   # 24 passed
.venv/bin/python -m pytest -q                        # 642 passed (suite completa)
.venv/bin/ruff check src/ tests/                     # tras partir la línea >100 chars
.venv/bin/mypy src/tlamati/tui/app.py
git add -A && git commit && git push -u origin fix/ctrl-c-copy
gh pr create --fill
```

### La teoría (el patrón reusable, con su donante)

**Patrón "binding por defecto del framework > atajo propio".** Cuando re-mapeas una tecla que el framework ya usa para edición (ctrl+c, ctrl+x, ctrl+v, shift+flechas), pregúntate en este orden: (a) ¿puedo hacerlo **no-priority** para que gane el editor cuando hay selección? (b) ¿mi acción es tan urgente que merece secuestrar la tecla? (c) ¿existe ya otra tecla para lo mío? (`ctrl+q` salir). Aquí la respuesta fue (a)+(c): el secuestro solo se justifica en emergencia, y copiar es la función 10× más frecuente que detener. Donante: **la propia migración de Textual** — su `action_help_quit` existe porque los mantenedores llegaron a la misma conclusión: reflexivamente todo el mundo pulsa ctrl+c para copiar o por costumbre, y la app moderna debe avisar ("Press ctrl+q to quit") en lugar de morir. Nosotros éramos el app vieja que ese commit de Textual corrige.

### Continuidad

- Si el fundador quiere **copiar el transcript completo sin mouse**: añadir un comando `/copy` o `ctrl+shift+c` que junte `self._history` → `app.copy_to_clipboard` (~10 líneas). Pendiente de pedirlo.
- El modo raw también aplica a `cli.py` interactivo (no TUI): allí SIGINT sí llega; no toca nada.
- Merge del PR → CI solo corre en main/PR (regla conocida); después borrar la rama.
