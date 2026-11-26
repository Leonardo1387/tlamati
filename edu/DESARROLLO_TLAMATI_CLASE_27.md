# Desarrollo Tlamati — Clase 27
## 26-nov-2026 (tarde): Visión nativa v2.1 — el arnés por fin puede ENSEÑAR imágenes

En la clase 26 cerramos v2 con el dogfooding de MCP. Hoy atacamos el hueco que
quedó gritando durante ese dogfood: el arnés era CIEGO. `Message.content: str`
es texto puro y `web_fetch` rechaza binarios honestamente ("Binary content is
rejected honestly"). La pregunta del día: ¿cómo le mostramos una imagen al
modelo sin traicionar el narrow waist ni meter un traductor que parafrasee?

## (a) El problema, en una escena cotidiana

Un intérprete en una junta: si el intérprete te DESCRIBE el cuadro en vez de
dejarte verlo, pierdes el cuadro. Eso era exactamente la vía que apareció
primero en la sesión: un VLM local (moondream vía ollama) como herramienta que
devuelve TEXTO sobre la imagen. Funciona, pero el modelo principal nunca ve
los píxeles — ve la opinión de otro modelo. El requisito real era otro: que el
arnés le pase la imagen al modelo, nativa, como Anthropic y OpenAI ya saben
recibirla.

## (b) Qué entendimos hoy

1. El límite duro NO era el modelo: era el waist. `Message.content: str = ""`
   en src/tlamati/core/messages.py. Todo lo demás (adaptadores, loop, budget,
   compaction) deriva de ese tipo. Tocar UN dataclass con un campo nuevo
   (`images: tuple[ImageBlock, ...]`) desbloquea las dos superficies de
   proveedor sin tocar el loop.
2. Magic bytes, no extensión: un archivo llamado .png puede ser JPEG o basura.
   `detect_media_type()` lee los primeros 12 bytes (PNG/JPEG/GIF/WEBP) y las
   dimensiones se parsean del header cuando el formato las expone barato
   (png/gif/jpeg); webp devuelve None honesto en vez de un parser completo.
3. Los píxeles NO se persisten en la sesión SQLite: base64 de 4 MB por mensaje
   reventaría el store. `as_dict()` guarda metadata (media/dims/path/bytes) y
   `from_dict()` recarga desde `source_path` al reanudar; si el archivo murió,
   la imagen se cae y el marker de texto queda como registro honesto.
4. El budget debe contar píxeles o miente justo en el turno más caro:
   fórmula Anthropic w*h/750 (una 1500x1500 = 3000 tokens), fallback
   documentado de 1600 cuando no hay dimensiones.
5. Microcompaction (M2) con imágenes: limpiar SOLO el texto dejaría el bloque
   de visión vivo — una evicción a medias, peor que no evictar. Un tool result
   con imágenes se limpia COMPLETO (texto→placeholder, images→()) porque
   read_file lo re-obtiene; por eso read_file entró a la whitelist
   COMPACTABLE_TOOLS (pitfall del donor qwen-code #4239, otra vez).

## (c) Qué se construyó y cómo (sección replicable)

Capas tocadas (orden = orden del flujo de un píxel):

- src/tlamati/core/images.py (NUEVO): ImageBlock (data base64, media_type,
  width/height, source_path, size_bytes) + load_image() con magic bytes, cap
  MAX_IMAGE_BYTES=4MB (rechazo entero, nunca recorte que rompe el binario) y
  token_estimate().
- core/messages.py: Message.images y ToolResult.images; guarda de
  __post_init__: solo roles user y tool cargan imágenes (los dos lugares donde
  AMBOS proveedores las aceptan).
- tools/registry.py: ToolOutput(content, images) — un tool puede devolver texto
  + payloads nativos; execute() los pasa al ToolResult y los DESCARTA si el
  resultado es error (un error con píxeles es ruido, no señal).
- tools/files.py: read_file detecta imagen por magic bytes y devuelve
  ToolOutput con el marker de texto ("[image · image/png · 300x200 · 707 bytes
  · ~80 tokens — adjunta como bloque de visión]").
- providers/anthropic_messages.py: bloques {"type":"image","source":
  {"type":"base64",...}} en user messages y DENTRO del content-list del
  tool_result.
- providers/openai_compat.py: data-URLs image_url en user y tool messages; el
  breakpoint de cache rolling (patrón verificado 20-nov) ahora también cae
  sobre listas de bloques, no solo strings.
- context/budget.py: _message_tokens suma token_estimate() de imágenes.
- context/compaction.py: microcompact evicta imágenes completas; el transcript
  del summarizer incluye los markers (el resumidor es ciego a píxeles pero el
  resumen debe decir QUÉ imágenes hubo).
- core/loop.py + cli.py: run_loop(user_images=...) y flag `--image PATH`
  repetible; un path roto aborta la corrida con el motivo en stderr (exit 2),
  nunca arranca ciego.

Comandos de verificación (réplica):

    cd ~/code/tlamati
    .venv/bin/python -m pytest tests/test_vision_v21.py -q   # 26 tests, sin red
    .venv/bin/python -m pytest tests/ -q                     # 716 en total
    .venv/bin/python -m ruff check src/ tests/ && .venv/bin/python -m mypy src/tlamati

Dogfood EN VIVO (OpenRouter, gemini-2.5-flash):

    # vía 1: el usuario adjunta
    .venv/bin/tlamati -p "Describe qué ves en la imagen adjunta." \
      --image ~/code/puente-apps-creativas/evidencia/s8_prueba_vision.png \
      --model google/gemini-2.5-flash
    # vía 2: el modelo llama read_file sobre un png
    cd ~/code/puente-apps-creativas && \
    ~/code/tlamati/.venv/bin/tlamati -p "Usa read_file sobre evidencia/s8_prueba_vision.png y dime qué colores ves." \
      --model google/gemini-2.5-flash

Ambas devolvieron la descripción correcta (ocre + gris arriba, azul abajo) con
stop=end_turn. Sesiones: 20261126-161426-ed99e4b8 y 20261126-161755-0b1df02e.

## (d) Errores del día (para que no te muerdan dos veces)

1. `google/gemini-2.0-flash-001` → HTTP 404 "no longer available on OpenRouter".
   Los ids de modelo caducan: verifica contra /models antes de dogfoodear.
2. Colisión de nombres en _run_headless: llamé `loaded` a mi lista de imágenes
   y YA existía un `loaded: StoredSession | None` arriba. mypy lo cazó
   ("Item StoredSession has no attribute append"); el test suite no. Moraleja:
   mypy no es opcional aunque pytest esté verde.
3. Corrí el dogfood de read_file con `cd ~/code/tlamati &&` por delante del
   workdir correcto: el harness ancla rutas relativas al CWD, así que
   "evidencia/..." no existía ahí. El error del tool fue HONESTO ("no such
   file") — el bug era mío, no del arnés. Verifica tu cwd antes de culpar al
   código.

## (e) Continuidad

Pendiente para v2.2: imágenes desde el TUI interactivo (hoy solo --image
headless y read_file); webp con dimensiones reales si alguien lo necesita; y
decidir si `delegate_task` (subagent) hereda user_images o se queda ciego por
diseño. El límite duro que abrió esta clase ya no existe: el waist ve.
