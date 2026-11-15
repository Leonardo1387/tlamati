# Desarrollo Tlamati — Clase 3

14-nov-2026 · Sesión 5 · Pasos A-1d (A6 compaction) y A-1e (A7 evals + baseline).
Con esto cierra la FASE A completa. Fase B queda gated (requiere luz verde del fundador).

## El problema

Un agente que conversa mucho tiempo se llena la "memoria de trabajo" (el contexto:
todo lo que el modelo recibe en cada llamada). Dos males: (1) cuando el contexto se
llena, la corrida muere; (2) si para hacer espacio borramos o cambiamos mensajes
viejos, rompemos la caché del proveedor — que cobra de nuevo todo el prefijo.
La regla de oro del proyecto: **"caching is sacred"** — se reconstruye SOLO el
sufijo (la parte de atrás de la conversación), jamás el prefijo cacheable.

## Los hallazgos

- El mapa de ahorro de tokens (research/04) tiene 5 capas, de la más barata a la
  más cara: truncar en la herramienta → microcompactar → chequear presupuesto →
  resumir con modelo barato → tirar la ventana y empezar de nuevo. A6 implementa
  las capas 2, 4 y 5.
- **Microcompactación (M2)**: borrar el CONTENIDO de resultados viejos de
  herramientas que se pueden volver a pedir (read_file, terminal...) y dejar un
  marcador "[Old tool result content cleared]". Cuesta cero (no llama al modelo).
  Donante: qwen-code microcompact.ts. Su lección clave (bug #4239 de ellos): si
  borras contenido sin dejar rastro, es pérdida silenciosa de datos → cada
  resultado limpiado lleva bandera permanente `microcompacted=True`.
- **Resumen con modelo barato**: cuando ya no alcanza, el tramo medio de la
  historia se resume con un modelo económico (cadena de fallback: si el primero
  falla, prueba el siguiente). Si TODA la cadena falla → **degradación honesta**:
  se descartan los mensajes viejos con un marcador visible
  "[COMPACTACIÓN DE EMERGENCIA] ... se descartaron N mensajes". Nunca pérdida
  silenciosa.

## QUÉ se construyó y CÓMO verificarlo (replicable)

### 1. `src/tlamati/context/compaction.py` (288 LOC)

Piezas clave:
- `CompactionConfig`: perillas — `retain_first=2` (ancla de cabeza: el prompt del
  usuario y la primera respuesta no se tocan NUNCA), `retain_recent=8` (cola
  reciente intocable), whitelist de herramientas compactables.
- `microcompact(historia, config)`: idempotente (correrlo dos veces = la segunda
  no limpia nada). Anti-colisión: un texto de usuario que EMPIEZA como el
  marcador NO se confunde con él — la comparación es de igualdad exacta.
- `ModelSummarizer(proveedores)`: cadena de fallback. Un `ProviderError` o un
  resumen vacío avanzan al siguiente modelo.
- `Compactor.compact(...)`: política por estado del presupuesto — `warn` → solo
  M2 (gratis); `exceeded` → M2 + resumen (o ventana-nueva honesta).

Verificar:
```bash
cd ~/code/tlamati
uv run pytest tests/test_compaction.py -q   # 12 tests
```

### 2. Integración en el loop (`core/loop.py`)

El gancho está en el chequeo de presupuesto, ANTES de llamar al proveedor —
entre turnos, nunca a mitad de un stream. `run_loop(..., compactor=...)` es
opcional: sin compactor, el comportamiento viejo (parar en `budget_exceeded`)
sigue igual (test de no-regresión).

### 3. CLI nuevo

```bash
tlamati -p "..." --compact-model "modelo-barato-1,modelo-barato-2"  # lista = fallback
tlamati -p "..." --no-compact
```
Durante la corrida se imprime `[compaction] micro=N resumidos=N tokens X→Y`.

### 4. Evals: `fixtures/` + `tlamati-eval` (A7)

5 tareas tipo terminal-bench-lite, cada una con: semilla con bug +
`instruction.md` + `verify.py` que decide el éxito (exit 0 y "VERIFY OK" —
el éxito se VERIFICA, nunca se supone). Las 5 semillas fallan antes del fix
(hay test que lo garantiza: una fixture que pasa de entrada no mide nada).

Correr el baseline (cuesta centavos vía OpenRouter):
```bash
uv run python -m tlamati.evals.runner --out evals/baseline_NUEVO.jsonl
```

## Los números REALES de esta sesión (baseline 14-nov, qwen/qwen3-coder)

| tarea | turnos | tokens in | cache_read | tiempo |
|---|---|---|---|---|
| conversor | 4 | 2730 | 2000 | 3.8s |
| crear_modulo | 3 | 1822 | 1632 | 1.9s |
| import_roto | 4 | 2692 | 2400 | 2.7s |
| offbyone | 5 | 3947 | 3440 | 3.8s |
| promedio | 5 | 3697 | 3248 | 4.6s |
| **TOTAL** | **5/5 OK** | **14888 in / 870 out** | **12720 (85%)** | **16.7s** |

El 85% de cache_read es EL invariante medido: la caché de prefijo del proveedor
funciona con nuestro arnés. Este archivo (`evals/baseline_2026-11-14.jsonl`) es
el ratchet de Osmani: si una fase futura rompe estos números, se detiene y revisa.

## Qué NO se hizo (y por qué)

- No se tocó el prefijo en ninguna compaction — lo verifica un test que compara
  byte a byte lo que viaja por la red en las 9 llamadas de una sesión larga.
- No se usó la API nativa `cache_edits` de Anthropic (queda documentada como
  extensión; hoy el proveedor OpenRouter cachea solo y funciona).
- Ollama NO entró en el baseline (decisión deliberada del HANDOFF, no re-añadir
  sin preguntar).

## El error del día

El test de sesión larga falló dos veces seguidas, ambas instructivas:
1. **Presupuesto mal calibrado**: cada lectura del archivo de prueba costaba
   ~879 tokens y el budget era 1600 → ni la cola reciente cabía tras compactar.
   Fix: archivo más chico (~300 tokens/lectura) y budget 750.
2. **Comparar IDs internos**: el loop crea un `Message(role="system")` NUEVO en
   cada llamada, y cada Message lleva un id por `time.time_ns()`. El test
   comparaba `as_dict()` completo y los ids diferían. La lección: la caché del
   proveedor ve el CONTENIDO que se serializa por la red (role+content), no los
   objetos internos de Python → comparar `as_dict()` sin el campo `id`.
   (Pista falsa que hubo que descartar primero: ¿`dataclasses.replace`
   regeneraba ids? No — verificarlo tomó 1 comando.)

## Pregunta abierta

Con 5/5 en el baseline, ¿el siguiente experimento útil es correr las MISMAS
5 tareas contra opencode con el mismo modelo para medir el delta de arnés
(la promesa del PRD: menos overhead, igual o mejor éxito)? Eso pertenece a la
comparación F, pero el baseline de hoy ya deja la vara puesta.
