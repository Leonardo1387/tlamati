# Desarrollo Tlamati — Clase 2
## 14-nov-2026: el robot que arregla bugs y cobra barato

*(v1 — escrita con las reglas nuevas: alumno en camino a técnico, notas replicables.)*

## El problema que nos trajo aquí

Imagina que contratas a un asistente brillantísimo, pero viene encerrado en una
caja: puede pensar, pero no puede abrir un cajón ni tomar un lápiz. Eso es un
modelo de IA sin arnés (harness = el programa que rodea al modelo y le da
"cuerpo": manos para leer archivos, ojos para ver resultados, y una libreta de
control de gastos). Ayer Tlamati tenía cuerdas vocales (los adaptadores que hablan
con los modelos). Hoy le construimos el cuerpo — y funcionó a la primera tarde.

## Qué entendimos hoy

El descubrimiento del día tiene números: nuestro arnés le manda al modelo apenas
**258 tokens** (token ≈ palabra-partida, la unidad que cobran los modelos) de
"manual de instrucciones" antes de tu primera pregunta. Claude Code, el producto
comercial de Anthropic, manda 33,000. Nosotros: el 0.8%. Y no es avaricia — es la
tesis del proyecto, respaldada por evidencia de la investigación previa: cuando
Vercel le QUITÓ herramientas a su arnés, el éxito subió de 80% a 100% con el mismo
modelo. Los manuales gordos estorban: el modelo se distrae con 30 mil tokens de
reglas que casi nunca aplican (a eso se le llama context rot, "pudrición del
contexto": entre más basura hay en la ventana de memoria, peor atiende el modelo).

Tu pregunta de hoy fue la correcta: ¿no perdemos calidad con tan poco manual? La
respuesta honesta: la calidad vive en el history (el historial de la conversación:
el archivo leído, tu instrucción, los resultados), no en el system prompt (el
manual fijo). Y dejamos una decisión abierta con colchón: podemos agregar ~500
tokens de instrucciones conductuales y seguiríamos en ~760, el 2% de Claude Code.
El experimento A7 (los exámenes estandarizados) dirá con números si hacen falta.

## Qué se construyó y cómo (tus notas de laboratorio)

Hoy escribimos cuatro piezas y las probamos de verdad. Los archivos clave, con su
ruta real dentro de ~/code/tlamati:

- `src/tlamati/core/loop.py` (290 líneas) — el ciclo de trabajo: pensar → actuar →
  ver resultado → repetir. Es una función async (asíncrona = que puede esperar al
  modelo sin congelar el programa) llamada `run_loop()`, no una catedral de clases.
  Entiende Ctrl-C: el primero guarda tu interrupción como mensaje para el siguiente
  turno (interjección); el segundo aborta.
- `src/tlamati/context/budget.py` — el contador de la gasolina: mide tokens con
  tiktoken (la librería que cuenta tokens igual que OpenAI) y avisa al 80% y al 95%
  del presupuesto. Cada turno imprime un breakdown (desglose) por sección nombrada:
  system / tools / history.
- `src/tlamati/tools_min/mini.py` — las tres manos PROVISIONALES: `read_file`
  (lee con números de línea), `write_file` (escribe), `terminal` (corre comandos,
  120s máximo). Provisional = deliberadamente temporal; en la Fase B se sustituyen
  por herramientas formales con permisos y sandbox (caja fuerte: el comando corre
  aislado del resto de tu sistema).
- `src/tlamati/cli.py` — la puerta de entrada: `tlamati -p "tu instrucción"`.

Para replicar el demo exacto de hoy, desde la terminal:

```bash
# 1. Crear el repo de prueba con el bug
mkdir -p /tmp/tlamati-demo && cd /tmp/tlamati-demo
cat > calc.py << 'EOF'
def promedio(numeros):
    total = 0
    for n in numeros:
        total += n
    return total / len(numeros) - 1

def test_basico():
    assert promedio([2, 4, 6]) == 4
EOF

# 2. Lanzar al agente contra OpenRouter con qwen3-coder
tlamati -p "El test de calc.py falla: promedio([2,4,6]) debería ser 4. Encuentra el bug, arréglalo y verifica corriendo: python3 -c \"from calc import test_basico; test_basico(); print('TEST OK')\""

# 3. Verificar TÚ MISMO que el arreglo es real (no creerle al robot)
python3 -c "from calc import test_basico; test_basico(); print('TEST OK')"
grep -n "return" calc.py   # debe decir: return total / len(numeros)
```

¿Qué pasó cuando corrimos eso? El modelo: turno 1 pidió leer calc.py; turno 2
encontró el `- 1` traidor y reescribió el archivo; turno 3 corrió el test él solo;
turno 4 dijo TERMINADO. Cuatro turnos, stop=end_turn, 2,993 tokens de entrada y
282 de salida. Y la cereza: `cache_read=2224` — OpenRouter nos cobró 2,224 tokens
como "relectura de caché" (cache = fotocopiado: si el prefijo del prompt no cambia,
el proveedor lo recuerda y cobra mucho menos). Nuestra invariante de diseño —"el
prefijo jamás se toca"— ya es dinero medible, no filosofía.

La verificación de calidad completa del proyecto, en dos comandos:

```bash
cd ~/code/tlamati
uv run pytest -q          # → 54 passed
uv run ruff check . && uv run mypy   # → limpios (mypy --strict = tipeo estricto)
```

Todo quedó en git, el sistema de control de versiones (la máquina del tiempo del
código): commits `71d1211`, `890175f`, `62ad808`, `6cc348e` en la rama main de
~/code/tlamati. Para retomar: leer `HANDOFF_FASE_A2.md` — ahí está el estado
verificado y lo que sigue.

## Qué decidimos NO construir hoy

No metimos permisos ni sandbox en las herramientas: son provisionales y la
seguridad formal es Fase B (con su llave sudo en su momento, no antes). No
probamos Anthropic contra su API directa (sin llave nativa; el adapter ya existe y
está probado con mocks — simulaciones de servidor). Y no tocamos compaction
(resumir el historial cuando se alarga): es exactamente el siguiente paso, A6.

## El error del día

El mejor material didáctico: un test nuestro cazó un bug nuestro. Cuando la
conexión con el modelo moría a medias (stream con error y cero contenido), el loop
intentaba guardar en el historial un mensaje de assistant VACÍO — y nuestro propio
tipo `Message` de A2 lo prohíbe (ValueError: un mensaje vacío no existe). O sea:
una regla de integridad que escribimos hace dos días atrapó un error de hoy.
Arreglo: el loop ahora guarda el placeholder "(sin contenido)". Moraleja
replicable: los tipos estrictos + tests escritos antes son la red que atrapa los
errores de tu yo futuro. De eso se trata pytest (el framework de pruebas) y mypy
strict: no son burocracia, son el QA automático.

Un segundo tropiezo, de seguridad: quise cargar la llave de API con un `export` en
la terminal y el sistema la bloqueó — con razón, esa llave no debe pasar nunca por
la línea de comandos visible. La solución quedó cableada en `cli.py`: el programa
lee la llave desde `~/.hermes/.env` en Python, en silencio.

## Lo que sigue (anotado en el handoff)

A6: compaction — cuando el historial rebalse, resumir con un modelo barato, pero
con la regla de oro: solo se toca el SUFIJO, jamás el prefijo fotocopiado (si no,
rompes la caché y el ahorro de hoy se evapora). Luego A7: los cinco exámenes
estandarizados que responderán tu pregunta de hoy con números en vez de opiniones.

**La pregunta que queda abierta: hoy el robot dijo "TERMINADO" y nosotros lo verificamos corriendo el test... pero cuando Tlamati trabaje solo a las 3 de la mañana en 50 tareas, ¿quién le corre el test al robot? (Pista: la Fase B trae un ledger — libro de actas append-only, "solo-agregar", donde cada acción queda firmada e imborrable.)**
