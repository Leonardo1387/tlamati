# LA CLASE DEL DÍA — 14 de noviembre de 2026 (sesión 4)
## "El día que construimos un robot que arregla sus propios errores... con instrucciones de 258 palabras"

Hola. Siéntate, que hoy sí tenemos algo que presumir: hoy Tlamati dejó de ser
un montón de planos y se convirtió en una máquina que FUNCIONA. Te cuento qué
pasó y qué aprendimos, sin tecnicismos innecesarios.

### El problema de hoy

Teníamos las "cuerdas vocales" del robot (los adaptadores que hablan con los
modelos de inteligencia artificial, que construimos en la sesión anterior),
pero no tenía "cuerpo": no sabía hacer nada. Un modelo de IA por sí solo es
como un cerebro en una caja: piensa, pero no puede abrir un cajón.

Hoy le construimos tres manos: una para LEER archivos, otra para ESCRIBIR
archivos, y otra para CORRER comandos en la terminal. Y lo más importante:
el "ciclo de trabajo" — la rutina de pensar, actuar, ver el resultado y
volver a pensar.

### Lo que demostramos (números reales de hoy)

Le pusimos una trampa a propósito: un archivo con una calculadora descompuesta
(una función que sacaba promedios... y le restaba 1 al resultado, así de
tonta y así de invisible). Le dijimos al robot: "el examen falla, arréglalo".

¿Qué hizo el robot solo, sin ayuda?
1. Pidió leer el archivo (mano #1).
2. Encontró la línea culpable: la línea 6.
3. Reescribió el archivo corregido (mano #2).
4. Corrió el examen él mismo para verificar (mano #3).
5. Reportó: "TERMINADO, quité el -1 de la línea 6".

Cuatro turnos. Nosotros verificamos por separado que el examen pasa de
verdad. No es cuento: está grabado en el historial del proyecto.

### La sorpresa bonita: el robot casi no "estorba"

Recuerda que medimos cuántas palabras de "manual de instrucciones" le enviamos
al robot ANTES de tu primera pregunta. Los competidores cargan hasta 33,000
palabras de manual. ¿Nosotros? 258. Como darle a un cirujano una hoja de
instrucciones en vez de una enciclopedia.

Y aquí viene tu pregunta de hoy, que fue buenísima: "¿no perdemos calidad por
usar tan pocas palabras?" La respuesta es como la de un restaurante: la
calidad no está en el menú impreso, está en la comida. Las 258 palabras son
el menú; la comida (el archivo que leyó, tu instrucción, el examen que corrió)
viaja aparte y sí llega completa. De hecho, la evidencia que investigamos
antes dice que los manuales GORDOS estorban: un competidor subió su éxito de
80% a 100% nada más QUITANDO cosas.

Eso sí, te doy la vuelta completa honesta: si en el futuro vemos que el robot
se porta mal en tareas largas, la solución no es engrandecer el manual para
todos, sino darle la página extra solo cuando la tarea la pida. Eso ya está
planeado (los "skills" de la Fase C).

### Lo que aprendimos a la mala

Un examen automático que escribimos cazó un error nuestro: cuando la
conexión con el modelo fallaba a medias, el robot intentaba guardar un
"mensaje vacío" en su memoria, y la memoria lo rechazaba (con razón: un
mensaje vacío no existe). Arreglo: ahora guarda un mensaje que dice
"(sin contenido)". Moraleja: los exámenes que escribimos ANTES de usar el
programa valen su peso en oro — hoy uno nos salvó de un error que habría
aparecido en el peor momento.

Y un detalle de seguridad: la llave secreta para hablar con OpenRouter nunca
debe aparecer escrita en la pantalla ni en los comandos. Hoy el sistema de
seguridad bloqueó un comando mío que la exponía — y tenía razón. La llave
se lee en secreto, dentro del programa.

### La tarea que queda (para la próxima clase)

1. Enseñarle al robot a RESUMIR su propia memoria cuando la conversación se
   ponga larguísima — pero con una regla sagrada: nunca tocar las primeras
   páginas del cuaderno, porque esas están "fotocopiadas" (la caché que nos
   ahorra dinero: hoy el proveedor nos regaló 2,224 palabras cacheadas).
2. Construir el "examen final": 5 tareas con trampas como la de hoy, para
   medir con números qué tan bueno es nuestro robot contra los de la
   competencia usando EL MISMO cerebro. Ese es el experimento que da sentido
   a todo el proyecto.

### La pregunta abierta para ti

Hoy el robot se verificó a sí mismo corriendo su propio examen. Pero, ¿quién
vigila al vigilante? Si el robot dice "TERMINADO" y miente... ¿cómo lo
atrapamos sin leer todo su trabajo nosotros? (Pista: la Fase B trae un "libro
de actas" donde cada acción queda firmada e imborrable.)

Nos vemos la próxima sesión. Hoy el proyecto dejó de ser una promesa.

— Tu profesor de turno (Hermes), con datos reales de la sesión 4.
