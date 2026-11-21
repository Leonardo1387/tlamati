# CLASE 15 — La especificación ejecutable: arreglar un bug leyendo primero el test, no el código

*Serie: DESARROLLO_TLAMATI. Sesión 25, 20-nov-2026. Anterior: CLASE_14 (autopsia del dogfooding #2: "cuando el modelo es chico, el arnés importa más").*

En la clase 14 hicimos una autopsia y llegamos a una conclusión incómoda: arreglar el arnés no arregla al modelo, solo deja de taparlo. Pero también vimos el otro lado de la moneda: en el bench flash, con tareas bien especificadas y verificadas por máquina, el modelo chico salió 45/45 perfecto. Hoy nos toca estar del otro lado del mostrador: correr NOSOTROS una tarea de bench, la tarea "promedio" del brazo hermes, y usar exactamente ese ingrediente que hizo que el modelo chico rindiera: una especificación ejecutable.

## El problema, en escena cotidiana

Imagina que te entregan una calculadora que promete promedios y un compañero te dice: "está mal, promedio([2, 4]) da 2.0 y debería dar 3.0; arréglala y verifica con verify.py". Nada más. No te dicen dónde está el bug ni por qué. Eso es una tarea de bench: un directorio aislado con un instruction.md (el enunciado) y un verificador automático que decide si ganaste o perdiste. Fíjate que el enunciado te da dos cosas que valen oro: un caso concreto de fallo ([2,4] → 2.0 en vez de 3.0) y un comando de verificación (python3 verify.py debe imprimir VERIFY OK). Cuando un reporte de bug viene así de bien armado, el trabajo de diagnóstico se reduce a la mitad.

Los archivos están en /tmp/tlamati-bench/hermes/promedio/ y son apenas dos: calc.py (3 líneas, la función a arreglar) y verify.py (11 líneas, el juez). El bench completo de este brazo tiene 14 tareas hermanas (offbyone, import_roto, git_history, anti_bucle_imposible, context_rot_20_archivos…), cada una en su carpeta con la misma anatomía.

## Qué entendimos hoy

Lo primero que hicimos fue leer los DOS archivos, en paralelo, antes de tocar nada. Y aquí está el hallazgo didáctico del día: verify.py no es solo el juez, es la ESPECIFICACIÓN. Sus tres casos de prueba definen el contrato exacto de la función:

- promedio([2, 4]) debe dar 3.0
- promedio([10]) debe dar 10.0
- promedio([1, 2, 3, 4]) debe dar 2.5

El segundo caso es el más interesante: la lista de un solo elemento. Cualquier "arreglo" que no devuelva exactamente 10.0 para [10] está mal. Ese caso existe a propósito para matar soluciones tramposas — por ejemplo, alguien que "arregle" el bug sumando 1 en vez de quitar la resta pasaría el primer caso (2.0+1=3.0) y moriría en el segundo (10.0+1=11.0). Un buen test no solo detecta el bug reportado: detecta la clase completa de arreglos incorrectos.

Y el bug en sí, en calc.py:3, era una resta espuria al final de la fórmula:

```python
return sum(nums) / len(nums) - 1
```

El "- 1" le restaba uno a TODOS los promedios. Por eso [2,4] daba 2.0 (la suma 6 entre 2 elementos = 3, menos 1 = 2). Un bug de una sola línea, pero del tipo más traicionero: no truena, no lanza excepción, devuelve números que "casi" se ven bien.

## QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

El flujo completo, comandos exactos tal como se corrieron:

```
# 1. Encontrar los archivos del task (no asumir rutas)
ls /tmp/tlamati-bench/hermes/promedio/

# 2. Leer el código Y el verificador ANTES de editar
cat calc.py
cat verify.py

# 3. El fix: una línea, quitar el "- 1" espurio de calc.py:3
#    antes:  return sum(nums) / len(nums) - 1
#    después: return sum(nums) / len(nums)

# 4. Verificar con el juez que dio el propio enunciado
cd /tmp/tlamati-bench/hermes/promedio && python3 verify.py
```

Salida real del paso 4:

```
VERIFY OK
```

exit_code 0. Tarea completada en 4 pasos: localizar, leer ambos archivos, editar una línea, correr el verificador.

Archivos tocados: solo /tmp/tlamati-bench/hermes/promedio/calc.py (una línea cambiada). verify.py NO se toca nunca — es el juez; editar el juez para pasar es hacer trampa y en un bench invalida la medición.

## LA TEORÍA DETRÁS

Hoy usamos el patrón de **especificación ejecutable** (executable specification): cuando existe un test que define el comportamiento correcto, el test es la fuente de verdad, no el código, no los comentarios, no la memoria de nadie. El orden de trabajo que impone este patrón es fijo y reusable en cualquier proyecto:

1. **Lee el test primero.** Te dice qué significa "bien" con números concretos.
2. **Reproduce el fallo.** Corre el verificador ANTES de arreglar, para confirmar que falla como dice el reporte (hoy nos ahorramos este paso porque el enunciado ya traía el fallo documentado y el código era de 3 líneas, pero en un proyecto real es obligatorio: a veces el bug reportado no reproduce).
3. **Arregla la raíz, no el síntoma.** El síntoma era "promedio([2,4]) = 2.0"; la raíz era el "- 1". Un arreglo por síntoma (sumar 1 al resultado final) habría pasado un caso y fallado otro.
4. **Verifica con la misma máquina que te va a calificar.** Nada de "ya se ve bien"; python3 verify.py imprimió VERIFY OK.

Este patrón es exactamente lo que hace que un bench funcione — y conecta directo con la clase 14: la razón por la que el modelo chico sacó 45/45 en el bench flash es que cada tarea traía su verify.py. La verificación por máquina convierte "¿lo hice bien?" (juicio subjetivo) en "VERIFY OK" (hecho binario). El diseño de tasks aislados con instruction.md + verify.py es hijo directo de SWE-bench y de los benchmarks de agentes tipo Terminal-Bench: un directorio por tarea, cero dependencias entre tareas, grading automatizado. Tlamati se evalúa contra el mismo bench que corremos a mano hoy — por eso entender la anatomía de una tarea importa: es el terreno donde se mide la tesis del proyecto.

## Qué decidimos NO construir

No agregamos manejo de lista vacía (ZeroDivisionError), no agregamos tipos, no escribimos tests extra. Tentador, pero fuera de alcance: el bench califica contra verify.py y nada más, y en un arnés de evaluación cada token y cada segundo cuentan. Añadir comportamiento no pedido se llama scope creep (el proyecto que crece como enredadera) y en un benchmark contamina la medición: si el agente tarda el doble en hacer "de más", la comparación entre arneses deja de ser justa. Decir que no también es clase.

## El error del día

El error no fue nuestro: fue el bug plantado del bench (esa es la naturaleza de un bench — los bugs están sembrados a propósito). Pero el material didáctico está en cómo se detecta esa FAMILIA de bug: una resta/correr-de-uno al final de una fórmula ("off-by-one", que de hecho es el nombre de otra tarea del mismo bench). Su firma es inconfundible: todo resultado sale desplazado la misma cantidad. Si ves que TODOS los valores fallan por exactamente el mismo delta, no busques lógica compleja rota — busca un término constante que sobra o falta.

## Gancho para mañana

El brazo hermes del bench tiene 14 tareas; hoy corrimos una. La campaña S27 sigue con los brazos qwen por relanzar y el análisis del PASO 3 pendiente.

**La pregunta que queda abierta: si una tarea de 3 líneas se resuelve en 4 pasos, ¿en qué punto exacto de las 13 tareas restantes (git_history, context_rot_20_archivos, anti_bucle_imposible) empieza a fallar un agente — y es el modelo o es el arnés el que falla?**
