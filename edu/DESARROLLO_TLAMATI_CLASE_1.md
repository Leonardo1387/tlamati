# Desarrollo Tlamati — Clase 1
## 14-nov-2026: "Los planos, el idioma y las cuerdas vocales del robot"

*(Escrita retrospectivamente bajo las reglas v1: alumno en camino a técnico, notas replicables. Todo número viene de la sesión real.)*

## El problema que nos trajo aquí

Antes de construir una casa, un arquitecto revisa los planos dos veces. Hoy teníamos los planos de Tlamati —el PRD (Product Requirements Document: el documento que dice qué se construye, qué NO y cómo se mide el éxito) y la GUÍA de implementación— y un documento de traspaso (handoff) que decía "ejecuta la Fase A". Pero tu instrucción fue sabia: NO ejecutar de inmediato, primero AUDITAR la estrategia buscando fallas de lógica. Y había fallas. Dos.

**Falla #1 (la gorda):** el examen final de la Fase A era un demo donde el robot arregla un bug real en un archivo. Para eso necesita manos: leer, escribir, ejecutar comandos. ¿El detalle? Las herramientas estaban planeadas hasta la FASE B. O sea, los planos pedían graduarse de nadar... sin haber construido la alberca. Corrección que aprobaste: meter un mini-set de 3 herramientas PROVISIONALES dentro de la tarea A4, marcadas como temporales, que la Fase B reemplazará con las formales (con permisos y sandbox).

**Falla #2 (menor):** la tarea A4 decía "el loop corre hasta agotar el PRESUPUESTO", pero el contador de presupuesto se construía en A5, después. Inversión de dependencia (dependency inversion: cuando algo necesita una pieza que aún no existe, se define un "enchufe" — un protocolo — y la pieza real se conecta después). Arreglo: A4 recibe el presupuesto como interfaz; A5 la implementa.

Moraleja del día: auditar el plan ANTES de ejecutar vale más que ejecutar rápido. Las dos fallas se corrigieron en el documento con 10 minutos de lectura; habrían costado horas de código a mitad de la Fase.

## Qué se construyó hoy (tus notas de laboratorio)

### Pieza 1: el esqueleto (A1) — commit 71d1211

Un proyecto Python moderno se empaqueta con `uv` (gestor de paquetes y entornos virtuales, escrito en Rust, rapidísimo). Los comandos exactos que corrimos, en orden:

```bash
cd ~/code/tlamati
git init -b main                          # control de versiones, rama main
uv init --package --name tlamati          # crea pyproject.toml + src/tlamati/
curl -sf https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
uv sync --extra dev                       # instala deps de desarrollo en .venv/
```

Ojo con el primer tropiezo del proyecto: `uv init --package tlamati` dentro de una carpeta ya poblada creó un SUBdirectorio anidado (tlamati_pkg/) en vez de trabajar en la raíz. Hubo que borrarlo y usar `--name`. Las notas sirven para eso: no repitas mi error.

Qué quedó y para qué sirve cada archivo:
- `pyproject.toml` — la ficha del proyecto: dependencias (httpx = cliente HTTP moderno; tiktoken = contador de tokens; pyyaml = configuración), los dos comandos instalables (`tlamati` y `tlamati-eval`), y las reglas de calidad: ruff (linter = policía del estilo), mypy en modo strict (revisa tipos: que no le pases texto donde va número), pytest (framework de pruebas).
- `NOTICE.md` + `LICENSE` — Apache-2.0. El NOTICE es importante: declara qué aprendimos de quién (hermes-agent MIT donó semánticas; codex/qwen/gemini-cli Apache donaron patrones de compaction). Aprender arquitectura de código abierto es legal CON atribución; copiar líneas de bundles privativos (Claude Code) NO — eso se estudió solo por conducta, con evidencia documentada.
- `.github/workflows/ci.yml` — integración continua (CI: GitHub corre lint+tipos+tests en cada push). Escrita pero dormida: el repo en GitHub se crea después.

### Pieza 2: el idioma interno (A2) — `src/tlamati/core/messages.py`, 223 líneas

Esto es lo que el PRD llama narrow waist ("cintura estrecha"): TODOS los proveedores de IA hablan dialectos distintos (OpenAI dice `tool_calls`, Anthropic dice `tool_use`), pero adentro de Tlamati solo existe UN idioma. Decisiones de diseño que valen clase:

- Dataclasses frozen (congeladas: una vez creadas, no se pueden modificar — como una placa de metal grabada, no una hoja de lápiz). Inmutabilidad = menos bugs.
- `ToolCall` guarda DOS versiones de los argumentos: el dict parseado Y el string crudo (`raw_arguments`). ¿Para qué el crudo? Auditoría byte-estable: el ledger de Fase B guardará exactamente lo que dijo el modelo.
- `ToolResult` trae banderas `untrusted` (contenido que vino de fuera: web, archivos ajenos — insumo de la regla de seguridad "trifecta letal") y `truncated` (marcador honesto de recorte).
- `Usage` es ADITIVO (se puede sumar turno tras turno) y trae campos de caché desde el día 1: si no lo mides, no lo puedes defender.
- Reglas de integridad en `__post_init__`: un mensaje assistant vacío = ValueError. (Acuérdate de esta regla; en la clase 2 verás cómo nos salva la vida.)

### Pieza 3: las cuerdas vocales (A3) — `src/tlamati/providers/`, 602 líneas en 3 archivos

- `base.py`: el Protocol (contrato de tipeo: "cualquier clase con estos métodos cuenta") + `ProviderError` tipado (kind/retryable/status/raw — un error con ficha médica, no un grito genérico) + parser de SSE (Server-Sent Events: el formato de "chorrito" con que los modelos responden palabra por palabra).
- `openai_compat.py`: cubre OpenRouter/Ollama/vLLM/Enverge con puro `base_url`. El truco fino: los argumentos de una herramienta llegan FRAGMENTADOS (`'{"pa'` ... `'th": "a.py"}'`) y hay que acumularlos por índice antes de parsear.
- `anthropic_messages.py`: tool_use/tool_result nativos, y los breakpoints de `cache_control` (marcadores que le dicen a Anthropic "de aquí para atrás, fotocópialo"). Semántica donada por hermes (MIT), líneas reescritas nuestras.

La prueba de que todo funciona — replicable con MockTransport (servidor simulado dentro del test, cero red, cero costo):

```bash
cd ~/code/tlamati && uv run pytest -q        # → 35 passed
uv run ruff check . && uv run mypy           # → limpios, strict
```

Y el smoke test REAL (la primera vez que Tlamati habló con un modelo de verdad):

```bash
uv run python dev/smoke_openrouter.py
# salida real de ese día:
#   tool llamado: read_file
#   args: {"path": "main.py"}
#   stop_reason: tool_use
#   usage: Usage(input_tokens=281, output_tokens=22, ...)
```

Lee bien lo que pasó ahí: qwen3-coder, desde el otro lado de internet, decidió LLAMAR UNA HERRAMIENTA, y nuestro adapter tradujo su dialecto a nuestro idioma interno perfectamente. 281 tokens de entrada, 22 de salida. Las cuerdas vocales funcionan.

## Qué decidimos NO construir hoy

Ninguna herramienta real todavía (van en A4 con el loop, corrección #1 mediante). Nada de GitHub remoto. Y el modelo de Anthropic NO se probó contra su API directa — no hay llave nativa y es deliberado: en esta máquina Anthropic se consume vía OpenRouter (la llave nativa pisa la configuración de Hermes). Los mocks cubren el adapter; la red real se validará vía OpenRouter.

## El error del día (y fueron varios, honestamente)

1. El `uv init` anidado (arriba).
2. `uv tool install` instaló un wheel EN CACHÉ obsoleto: faltaba un módulo recién creado. Síntoma confuso (ModuleNotFoundError de algo que SÍ existe en src/). Arreglo: `uv cache clean tlamati && uv tool install --reinstall --force --from . tlamati`.
3. El slug `qwen/qwen3-coder:free` murió en OpenRouter (HTTP 404 honesto: "use la versión pagada"). El adapter lo reportó como ProviderError tipado con status=404 — o sea, el error se portó como lo diseñamos.
4. El de seguridad: intenté cargar la llave de API con `export $(grep ...)` en la terminal y el parser de Hermes lo BLOQUEÓ sin apelación. Tenía razón: una llave jamás debe pasearse por la línea de comandos. Solución permanente: `dev/smoke_openrouter.py` lee la llave desde `~/.hermes/.env` dentro de Python, en silencio.

**La pregunta que queda abierta para la clase 2: ya tenemos un cerebro que habla por teléfono (adapters) y un idioma interno (messages)... pero nada los conecta todavía en un ciclo. ¿Quién decide "el modelo pidió herramienta → ejecuto → le devuelvo el resultado → repito"? Eso es el loop agéntico — el corazón de 290 líneas que construiríamos al día siguiente, y con él, el primer bug arreglado por una máquina nuestra.**
