# Desarrollo Tlamati — Clase 25
## 26-nov-2026: v2 arranca — el arnés aprende a leer links y a hablar HTTP con Unreal

En la clase 24 vimos cómo el ctrl+c dejó de secuestrar tu portapapeles; hoy dejamos las teclas y entramos al primer día de la v2 de tlamati: dos features que cierran los dos dolores que el dogfooding del proyecto puente puso sobre la mesa. El primero era cotidiano: le pegabas un link al arnés y te decía "no lo leo". El segundo era estructural: tu Unreal tiene un servidor MCP vivo en `127.0.0.1:8000/mcp`, pero el cliente MCP de tlamati solo hablaba stdio — el "tubo local" de stdin/stdout por el que el padre le escribe al hijo. Por eso tus sesiones controlaban Unreal con scripts sueltos (`evidencia/mcp_ue.py`, curl desde terminal): el puente funcionaba *alrededor* del arnés, no *dentro*. En todo el `audit.db` había cero tool calls MCP. Hoy eso cambió.

### (a) El problema en una escena

Imagina que tlamati es un oficinista muy capaz pero encerrado: ve todos los archivos de su escritorio (read_file, search_files), puede correr comandos en una cabina sellada sin teléfono (la jaula bwrap con `--unshare-net`), pero cuando le das una tarjeta con una dirección web, no tiene cómo visitarla. Y cuando le dices "habla con el motor de videojuegos que está en la oficina de al lado", solo sabe usar el tubo neumático interno (stdio), mientras que el vecino atiende por teléfono (HTTP). Los dos features de hoy son exactamente eso: darle un mensajero acotado para visitar URLs, y enseñarle a hablar por teléfono.

### (b) Lo que medimos antes de escribir código

Aquí está la lección más importante del día: no construimos el transporte HTTP de memoria ni de la spec — lo **medimos contra tu Unreal vivo** con una sonda urllib de ~30 líneas. Los hallazgos, con números:

- `initialize` → HTTP 200 con `protocolVersion: 2025-06-18` y un header `Mcp-Session-Id` (el "carnet de sesión").
- `tools/list` SIN ese carnet → **400, error JSON-RPC -32600 "Missing required M…"**. O sea: el carnet es obligatorio tras el saludo.
- Respuesta en JSON puro (`application/json;charset=utf-8`), no SSE — pero la spec permite ambas, así que el cliente parsea las dos.
- `tools/list` devuelve **solo 3 tools**: `list_toolsets`, `describe_toolset`, `call_tool(toolset_name, tool_name, arguments)`. Los "53 toolsets" son un registro interno del servidor, no tools MCP.
- Header `Origin`: probado con y sin → 200 ambos. No es obligatorio en 5.8.4, pero lo enviamos igual (la spec lo recomienda; es gratis).

Todo quedó escrito en `HANDOFF_V2_MCP_HTTP.md` antes de la primera línea de código. Dimensionar primero, construir después: el handoff es el plano, el commit es el edificio.

### (c) Qué se construyó y cómo (sección replicable)

**Feature 1 — web_fetch** (rama `v2-web-fetch`, commit `a45054f`, mergeado a main):

- `src/tlamati/tools/webfetch.py` (NUEVO): tool `web_fetch` con httpx, GET únicamente, solo contenido textual (text/*, json, xml, yaml, markdown), cap de 200,000 bytes cortado en la fuente con marcador visible, timeout 20s, User-Agent honesto (`tlamati/2.0`), redirects seguidos. `permission=ASK` y `produces_untrusted=True` siempre.
- `src/tlamati/tools/builtin.py`: `make_tools()` ahora incluye web_fetch AL FINAL de la lista (el prefijo cacheable de las tools anteriores queda byte-idéntico — "caching is sacred").
- `src/tlamati/env_info.py`: el bloque ambiental del system prompt le AVISA al modelo que puede leer URLs (lección SEC.3 del dogfood #4: capacidad sin orden = "no puedo" mentiroso).
- `tests/test_webfetch_v2.py`: 26 tests con `httpx.MockTransport` — un cartero falso que contesta lo que le digas sin salir a internet. Cero red en CI.

Verificación real (no mocks, corrida de verdad):

```
== example.com ==      [HTTP 200 · text/html · 577 bytes] <!doctype html>...
== 404 ==              ERROR: HTTP 404 for https://example.com/no-existe-xyz
== binario ==          ERROR: content-type no textual (image/x-icon) — ...
== DNS muerto ==       ERROR: fetch failed — ConnectError: [Errno -2] Name or service not known
```

**Feature 2 — transporte MCP Streamable HTTP** (rama `v2-mcp-http`, commit `a9bf24c`, mergeado a main):

- `src/tlamati/mcp/http_client.py` (NUEVO, ~280 LOC): `MCPHTTPClient` con la MISMA interfaz pública que `MCPClient` (connect/tools/call_tool/close). Captura el carnet `Mcp-Session-Id` del response de initialize y lo manda en toda llamada posterior. Llamadas en serie con `asyncio.Lock` (un candado: la segunda llamada espera a que la primera suelte). Si el carnet caduca porque reiniciaste Unreal → UN renegocio automático (initialize fresco + retry) y si vuelve a fallar, error honesto. `close()` manda DELETE con el carnet, fail-soft.
- `src/tlamati/mcp/client.py`: `MCPServerConfig` gana campo `url: str | None = None`; `parse_mcp_config` acepta `url:` XOR `command:` (los dos juntos = error honesto; scheme solo http/https). `_content_to_text` se extrajo a función de módulo `content_to_text` (lógica de PROTOCOLO, compartida por los dos transportes). Nuevo `Protocol MCPTransport` tipa el duck-typing. `load_mcp_servers` elige transporte por config: `MCPHTTPClient(cfg) if cfg.url else MCPClient(cfg)`.
- `tests/test_mcp_http_v2.py`: 22 tests con un `FakeUEServer` que replica el contrato medido (carnet obligatorio tras initialize, SSE opcional, renegocio, lock en serie, DELETE).

La config nueva en tu `tlamati.yaml` se ve así:

```yaml
mcp:
  servers:
    - name: unreal
      url: "http://127.0.0.1:8000/mcp"
      timeout_s: 120
```

Evidencia REAL contra el Unreal vivo (editor abierto, no mocks):

```
connect → tools: ['call_tool', 'describe_toolset', 'list_toolsets']
envueltas → mcp_unreal_call_tool / mcp_unreal_describe_toolset / mcp_unreal_list_toolsets
            (todas ASK + produces_untrusted)
mcp_unreal_list_toolsets.run({}) → "- ToolsetRegistry.AgentSkillToolset: Provides tools..."
close → DELETE OK
```

Gates del día, los dos features: ruff OK, ruff format OK, mypy strict 0 errores en 56 archivos, **690 tests passed** (668 tras web_fetch, +22 tras MCP HTTP). CI de GitHub en main: verde.

### (c2) La teoría detrás

**1. MockTransport: el doble de riesgo en las pruebas.** httpx permite inyectar un `transport=` — el "cartero" del cliente. En producción es el cartero real (TCP, DNS, TLS); en tests es un `MockTransport(handler)` donde `handler` es una función que recibe el request y devuelve el response que tú quieras. El código de producción no cambia NI UNA línea entre test y realidad: solo cambia el cartero. Este patrón (inyección de dependencias en la frontera de red) es el mismo que usan requests-responses, aiohttp test utils y los wiremocks de Java. Regla general: **todo lo que cruza la red debe poder reemplazarse por un doble**, o tus tests dependerán de internet y del humor del servidor ajeno.

**2. Protocol: el contrato sin herencia (duck-typing tipado).** `MCPClient` (stdio) y `MCPHTTPClient` (HTTP) NO comparten clase base. En su lugar definimos `class MCPTransport(Protocol)` que declara los atributos/métodos que ambos tienen (config, tools, connect, call_tool, close). mypy acepta cualquier objeto que cumpla esa forma. Es el "duck typing" de Python ("si camina como pato…") pero verificado en tiempo de análisis, no en runtime con un AttributeError. En Go se llama interfaz implícita; en TypeScript, structural typing. Cuándo usarlo: cuando dos implementaciones comparten FORMA pero no naturaleza (un subprocess y una conexión HTTP no tienen estado interno común que heredar).

**3. La trifecta de_egreso: ASK + produces_untrusted + cap.** Todo lo que sale del proceso hacia el mundo (web_fetch, tools MCP) lleva los mismos tres sellos: pide permiso antes de salir, marca su contenido como no-confiable (una página web con "ignora tus instrucciones" NO es una instrucción para el modelo), y acota el volumen que entra. Donor declarado: el patrón de Hermes (herramientas web con contenido untrusted) y la propia D3 de tlamati para MCP stdio. La diferencia clave de diseño: NO abrimos la jaula (`net=True` al sandbox daría red a TODO el terminal); añadimos UN verbo acotado (GET) por su propia puerta con su propio candado (ASK). Principio general de seguridad: **preferir puertas angostas y vigiladas a abrir el muro**.

**4. Medir antes de construir (probe-first).** Los 4 hallazgos de la sección (b) costaron ~30 líneas de urllib y 2 minutos. Sin ellos habríamos construido un cliente que asume SSE, o que no renegocia el carnet, y lo habríamos descubierto con el Unreal cerrado y errores misteriosos. En cualquier integración con un sistema externo vivo: primero sonda, después contrato escrito (el HANDOFF), después código, después la evidencia real otra vez contra el sistema vivo.

### (d) Lo que decidimos NO construir

- **El aplanador de toolsets**: convertir los 53 toolsets de Unreal en cientos de tools locales. Requeriría 53 llamadas `describe_toolset` al arrancar, reventaría el prefijo cacheable, y el modelo ya demostró en las sesiones puente que navega bien las 3 meta-tools. YAGNI: si el dogfooding muestra que el modelo se pierde, se reconsidera con evidencia.
- **POST/headers arbitrarios en web_fetch**: solo GET, solo texto. Cada verbo extra es superficie de abuso.
- **Rotación/renegocio infinito del carnet**: UN solo reintento por llamada. Un loop de renegocios contra un servidor roto es peor que un error honesto.
- **Herencia compartida stdio/HTTP**: ver Protocol arriba — forzar una clase base común habría acoplado dos naturalezas distintas.

### (e) El error del día

El más didáctico fue en los tests: 14 de 22 fallaron en cascada con "initialize → HTTP 400 (Missing required Mcp-Session-Id)". El cliente era inocente — el culpable era el `FakeUEServer`: le puse a exigir carnet hasta en `initialize`, cuando en el servidor REAL initialize es justamente el que OTORGA el carnet. O sea: **mi doble de riesgo actuaba distinto al actor real**. La corrección fue una línea (`method != "initialize"` en la guardia del fake). Lección: cuando escribas un mock, cada comportamiento debe salir de la evidencia medida, no de tu intuición de cómo "debería" funcionar el protocolo — el fake solo es útil si es fiel. (Segundo error menor: la rama SSE del fake no devolvía el header del carnet; mismo diagnóstico, misma lección.)

### (f) Continuidad

Hoy el arnés ya tiene las dos puertas abiertas: lee URLs (web_fetch) y habla MCP por HTTP (Unreal conectado DENTRO). La pieza que falta no es código: es **el dogfooding de cierre de v2** — una sesión tlamati real, con `mcp.servers: [{name: unreal, url: ...}]` en el yaml del proyecto puente, trabajando de verdad contra el editor, para que `audit.db` registre por fin tool calls MCP y podamos medir el puente completo (tokens, costo, aprobación de cada llamada ASK) como medimos todo lo demás.

**La pregunta abierta para mañana: cuando corras tu primera sesión puente con Unreal dentro del arnés, ¿el modelo usará las 3 meta-tools con soltura (list_toolsets → describe_toolset → call_tool) o necesitaremos el aplanador que hoy decidimos no construir? La respuesta está en el audit.db, no en la spec.**
