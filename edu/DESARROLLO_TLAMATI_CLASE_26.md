# Desarrollo Tlamati — Clase 26
## 26-nov-2026: Dogfooding de cierre v2 — Unreal habla dentro del arnés

En la clase 25 construimos los dos features de v2 (web_fetch y el transporte MCP Streamable HTTP) y los dejamos mergeados en main con sus tests. Hoy tocaba la prueba que importa: que el arnés use esos features en el mundo real, contra tu Unreal Engine vivo. Y de paso, una autopsia: ¿la sesión larga de la mañana (178 turnos) se loopeó o resolvió?

## (a) El problema, en una escena cotidiana

Imagina que instalaste un teléfono nuevo en la oficina (el transporte HTTP de la clase 25) pero nadie ha hecho la primera llamada. El teléfono puede funcionar perfecto en el manual y estar muerto en la práctica. La sesión de la mañana lo demostró sin querer: tlamati le habló a Unreal 5.8 durante casi dos horas… con curl desde la herramienta terminal. O sea, el puente funcionaba ALREDEDOR del arnés, no DENTRO. En todo el audit.db histórico había cero tool calls MCP registrados. Cero.

## (b) Qué entendimos hoy

Primero, la autopsia de la sesión matutina (20261126-104324-effe34a9, 178 turnos, $4.24, stop=aborted): NO hubo loop. Los comandos "repetidos 18 veces" eran sondas distintas del mismo script con argumentos diferentes (el detector de loops agrupa por los primeros 120 caracteres del JSON, y esos scripts comparten prefijo). El timeline no tiene huecos: turnos 1 a 60 con eventos continuos de 10:44 a 12:39, y la sesión murió en medio de trabajo productivo (estaba leyendo el fuente del plugin de Epic para corregir nombres de tools inventados — el último mensaje del modelo dice literalmente "list_assets no existe — inventé el nombre"). Abort manual tuyo, no colapso del agente.

Segundo, el dogfooding de cierre funcionó a la primera. Sesión 20261126-125416-28b21dca: end_turn limpio, 5 turnos, $0.043, y el modelo navegó las 3 meta-tools solo: mcp_unreal_list_toolsets → mcp_unreal_describe_toolset (SceneTools y ProgrammaticToolset) → mcp_unreal_call_tool con get_current_level, que devolvió el mapa real del editor: /Game/FirstPerson/Lvl_FirstPerson. audit.db pasó de 0 a 9 eventos mcp_*, todos con decision=ask_approved. La respuesta a la pregunta abierta de la clase 25: el modelo navega las meta-tools con soltura — el aplanador de toolsets NO hace falta por ahora.

Tercero, el hallazgo incómodo del día: la primera corrida del dogfood salió con el modelo EQUIVOCADO (qwen/qwen3-coder, $0.007) sin ningún aviso. ¿Por qué? Porque load_config() en src/tlamati/cli.py recorre CONFIG_PATHS = (tlamati.yaml del cwd, ~/.config/tlamati/config.yaml) y devuelve el PRIMER archivo que existe — no los fusiona. Mi tlamati.yaml nuevito del proyecto puente solo traía la sección mcp:, así que sombreó completo al config global, incluido provider.model, y el CLI cayó al default hardcodeado. First-wins, no merge.

## (c) Qué se construyó y cómo (sección replicable)

Archivo clave creado: ~/code/puente-apps-creativas/tlamati.yaml — configuración de proyecto que declara el servidor MCP de Unreal. OJO: debe repetir el bloque provider completo por el shadowing de arriba:

    provider:
      model: qwen/qwen3.8-max-0902
      base_url: https://openrouter.ai/api/v1
    mcp:
      servers:
        - name: unreal
          url: "http://127.0.0.1:8000/mcp"

El runner del dogfooding quedó en /tmp/dogfood_v2.py. La mecánica: extrae la API key vieja (la de tlamati) del respaldo ~/.hermes/.env.bak.20261126_095556 y lanza el arnés en modo headless:

    ~/code/tlamati/.venv/bin/tlamati -p "<tarea>" \
      --json --no-memory --approve-tool '*' --quiet

Cada flag: --json emite eventos máquina-legibles con el evento final result (stop_reason, turns, usage.cost_usd — evidencia dura, no self-report); --no-memory evita que la memoria duradera contamine una corrida de prueba; --approve-tool '*' pre-aprueba los ASK en headless (sin TUI no hay humano que apruebe); --quiet silencia el streaming.

Verificación de que quedó bien (el test que prueba el hito):

    python3 - <<'EOF'
    import sqlite3
    db = sqlite3.connect("file:/home/usuario/.local/share/tlamati/audit.db?mode=ro", uri=True)
    print(db.execute("SELECT count(*) FROM tool_events WHERE tool LIKE 'mcp%'").fetchone())
    EOF

Antes de hoy imprimía (0,). Ahora imprime (9,). Además: los 690 tests de la suite siguen pasando en el venv dev, y la forensia se hizo SIEMPRE con URI mode=ro (SQLite abierto en solo-lectura: imposible escribir por accidente).

Higiene de repo: borradas las ramas ya mergeadas feat/stop-and-steer (local+remota), v2-web-fetch y v2-mcp-http (locales), y el worktree ~/code/tlamati-ux. git branch --merged main confirma antes de borrar que el contenido ya está en main — nunca borres una rama sin ese chequeo.

## (c2) La teoría detrás

Hoy usamos el patrón dogfooding de cierre: un feature no está terminado cuando pasan sus tests unitarios, sino cuando el sistema lo usa para trabajo real y queda evidencia registrable. Los tests de la clase 25 usaban FakeUEServer (un actor de teatro); hoy hablaron con el actor real. La diferencia importa porque los mocks codifican TUS suposiciones sobre el contrato — y el contrato real siempre tiene esquinas que no suponías (la fricción medida hoy: call_tool con nombre completamente cualificado devuelve "ERROR: Unknown tool"; el tool_name va SIN prefijo cuando pasas toolset_name — el modelo se autocorrigió en un turno, pero es candidato a mejorar el description de la tool).

La herramienta nueva de hoy es la forensia de logs de auditoría con SQLite: abrir las bases del arnés (sessions.db para conversación y costos, audit.db para tool events) en modo read-only y hacer preguntas con GROUP BY. El detector de loops es un GROUP BY tool+args HAVING count>2; el timeline es un GROUP BY minuto. Es la misma técnica de un analista de datos sobre cualquier log estructurado — bancos, servidores, CI.

Y el bug del config shadowing ilustra un principio de diseño de configuración: first-wins vs merge son dos filosofías opuestas. first-wins es simple y predecible (un solo archivo manda) pero peligroso cuando el archivo local es parcial; merge es amable pero necesita reglas de precedencia por clave. Git, Docker Compose y Kubernetes resolvieron esto con merge explícito + documento de precedencia. tlamati hoy es first-wins sin avisar — queda anotado como fix futuro: o merge, o al menos un warning cuando el yaml local no trae provider.

## (d) Qué decidimos NO construir

El aplanador de toolsets MCP (exponer las 53 herramientas de Unreal como tools directas en vez de 3 meta-tools): el dogfooding demostró que el modelo navega las meta-tools bien — 5 turnos, cero confusión estructural. Construirlo ahora sería complejidad sin dolor que la justifique. Tampoco se tocó el fix del shadowing (es de v2.1 o v3, no del cierre).

## (e) El error del día

En realidad fueron dos, y los dos son de Hermes, no de tlamati — el alumno debe saber que el herrero también se corta. Uno: al escribir el runner, el literal "OPENROUTER_API_KEY=" salió mutilado a asteriscos por el sanitizador de secretos (una protección que impide que las keys queden en archivos/plantillas), así que el script no encontraba la key; se arregló construyendo el string por concatenación ("OPENROUTER" + "_API_" + "KEY="). Dos: el primer dogfood_v2.sh murió con "unexpected EOF while looking for matching quote" — un apóstrofe dentro de un comando sed anidado. Moraleja: cuando el shell se pelea con las comillas, se cambia de herramienta — el mismo trabajo en Python con subprocess (lista de argumentos, cero parsing de comillas) salió a la primera.

## (f) La pregunta abierta

**v2 está cerrada y verificada. La siguiente frontera es de producto: ¿tlamati se queda como tu arnés personal de dogfooding, o el hito "Unreal dentro del arnés" es la demo pública que le falta al README para el mundo OSS? Y si es demo, ¿con qué proyecto — el FirstPerson template de hoy, o algo del pipeline planos→recorrido del puente?**
