# CLASE 19 — La potencia estadística: cuando 65 corridas certifican lo que 10 solo sospechaban

*Serie: Desarrollo de tlamati, capítulo 19. Sesión del 22-nov-2026.*

## 1. EL PROBLEMA QUE NOS TRUJO AQUÍ

Imagínate que pruebas una medicina nueva en 3 ratones y los 3 sanan. ¿Funciona
la medicina? No lo sabes: quizá sanaban solos. Ayer cerramos la sesión dejando
exactamente ese problema sobre la mesa, pero con agentes en vez de ratones: el
experimento "skillopt" (donde tlamati propone una versión mejorada de un
SKILL.md — su manual de instrucciones — y la banca contra la original) había
dado 100% de éxito con el skill mutado, pero el test de Fisher decía p=0.24.
En cristiano: "1 de cada 4 veces verías esto por puro azar". No es prueba. La
decisión fue dejar skillopt EN SUSPENSO y correr hoy la batería que faltaba:
la que tiene POTENCIA.

Potencia estadística (power) es la probabilidad de que tu experimento DETECTE
un efecto que de verdad existe. Con n=10 por brazo y un baseline al 80%,
aunque la mutación fuera perfecta (100%), la potencia no llega a 0.8 — el
estándar aceptado. La cuenta previa decía: con n=35 distinguiríamos 80% vs
100% con power ~0.8. Costo cotizado: ~$1.20. El fundador dijo GO.

## 2. QUÉ ENTENDIMOS HOY (los números reales)

La batería S1.2 corrió 116 runs nuevos (heredando los 45 ya pagados de S1.1
como semilla — el script `dev/spike_power.py` lee
`dev/spike_confirm_progress.json` y salta lo ya corrido). Costo acumulado de
TODA la investigación: $2.4045, bajo el tope duro de $3.

| Brazo | flash n=35 | coder n=30 |
|---|---|---|
| v0 (skill original) | 29/35 = 82.9% | 27/30 = 90.0% |
| mut1 (mutación mala) | 26/35 = 74.3% | 24/30 = 80.0% |
| mut2 (mutación buena) | 34/35 = 97.1% | 30/30 = 100% |

El número del día es el Fisher COMBINADO (pool) de los dos modelos: mut2 metió
64 de 65 contra 56 de 65 del baseline → **p = 0.0085**. Menos de 1 en 100 de
que sea azar. Skillopt sale del suspenso: el ciclo propose→bench→keep está
CERTIFICADO como mecanismo.

Tres lecturas honestas que van al README:
1. El efecto es real pero MODESTO (+12-14 puntos) — el n=3 de hace una semana
   prometía +67. La escalera n=3 (mintió) → n=10 (dudó) → n=65 (certificó) es
   la historia completa y se publica así, sin maquillaje.
2. mut2 no solo acierta más: usa MENOS turnos (11.8 vs 14.4 en flash). Se
   enreda menos. Sale más barato.
3. mut1 EMPEORA el baseline en los dos modelos (p=0.20 pooled). Esto prueba
   con evidencia propia lo que harness² (nuestro donor conceptual,
   google-research) asume por diseño: sin el gate "conservar solo si el bench
   mejora", un sistema que se auto-mejora se auto-degrada.

## 3. QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

**A. La batería de potencia.** Archivo nuevo:
`~/code/tlamati-spike/dev/spike_power.py` (worktree de la rama
`spike/skillopt`, commit 6a50338). Reusa TODO lo existente: `run_once` del
spike original (HOME temporal aislado + fixture fresca + verify.py decide),
el Fisher exacto de `spike_confirm.py` (math.comb, sin scipy), y los tres
SKILL.md ya propuestos. Lo único nuevo: las fases `[("qwen/qwen3.8-flash",
35), ("qwen/qwen3-coder", 30)]`, el tope $3 y la semilla que hereda el
progreso de S1.1. Comandos exactos:

```
cd ~/code/tlamati && git worktree add ~/code/tlamati-spike spike/skillopt
ln -s ~/code/tlamati/.venv ~/code/tlamati-spike/.venv   # el script usa .venv/bin/tlamati
cd ~/code/tlamati-spike && .venv/bin/python dev/spike_power.py
```

Reanudable por diseño: cada run se persiste en
`dev/spike_power_progress.json` apenas termina. Hoy lo probamos de verdad —
el fundador pausó por red mala (`pkill -f spike_power.py`), y al reanudar el
script saltó los 34 runs ya hechos y siguió en el 35. Cero gasto duplicado,
cero datos contaminados (un run con red mala habría quedado guardado como
"FALLO legítimo" — pausar a tiempo fue parte del método).

**B. La autopsia del dogfood #7.** El fundador corrió tlamati él mismo
(sesión 20261122-095857 en `~/.local/share/tlamati/sessions.db`, 40 turnos,
nemotron-3.5-super-vl, $0.154). Tarea real: auditar el deploy de Producto A
y abrir el acceso de Supabase para el piloto. Calificación: 7.5/10. El fix 1a
(inyección tardía de AGENTS.md) quedó PROBADO en condiciones reales: el primer
`cd /home/usuario/code/proyecto-legal` (seq22) disparó el system-reminder con
las reglas del repo en el tool result (seq26). Los errores fueron del modelo
(link viejo del handoff, pérdida de hilo en seq64), no del arnés. Receta
completa: `references/dogfooding-session-autopsy.md` del skill — ojo con el
schema: los tool results viven en role='tool', no 'user'; emparejar por
tool_call_id, no por "el mensaje siguiente".

**C. El fix MODO_DIRECTO de proyecto-legal.** El dogfood destapó un bug de
negocio: el frontend en modo directo (el cliente) envía `Authorization: Bearer
directo`, y el backend intentaba parsearlo como JWT de Supabase → 401 en la
primera consulta. Fix en `~/code/proyecto-legal/auth.py` (commit 75e5e0a,
pusheado a remote `mvp`): constante `MODO_DIRECTO = os.environ.get("MODO_DIRECTO", "") == "1"`
y tres ramas gated — verificar_token acepta el literal "directo" como
identidad `cliente-directo`; obtener_usuario devuelve usuario sintético
pro/999999; descontar_query es no-op (no hay fila en Supabase). Sin la
variable de entorno, el comportamiento es byte-idéntico al anterior
(no-regresión por construcción). Verificado con prueba ad-hoc de 3 casos
(OFF rechaza, ON acepta, ON con token basura rechaza). La variable
MODO_DIRECTO=1 ya está puesta en Railway (proyecto soothing-consideration)
vía `railway variables --set`, PERO el contenedor sigue sirviendo código
viejo tras dos redeploy por CLI — queda pendiente el Redeploy manual desde
el dashboard y la prueba e2e con curl.

## 3b. LA TEORÍA DETRÁS

**Patrón 1 — Feature flags por variable de entorno.** El MODO_DIRECTO es un
ejemplo de textbook: código nuevo que duerme detrás de una variable hasta que
el entorno la activa. Propiedad clave: el deploy del código es SEGURO por sí
mismo (sin la variable, nada cambia), y activar/desactivar el feature no
requiere otro deploy. Lo encuentras igual en LaunchDarkly (producto dedicado)
o en el clásico `DEBUG=True` de Django. Regla del proyecto: la rama flaggeada
devuelve comportamiento byte-idéntico cuando está apagada — así la
no-regresión se prueba por construcción, no por esperanza.

**Patrón 2 — El pooled test.** Fisher por modelo no dio significancia en
ninguno por separado (p=0.053 flash, p=0.119 coder), pero el MISMO skill mut2
se comportó igual en ambos modelos — eso justifica combinar las corridas en
una sola tabla de contingencia (64/65 vs 56/65 → p=0.0085). El principio
general: cuando el tratamiento es idéntico y el efecto es consistente entre
grupos, pooling aumenta la potencia sin inflar el falso positivo. Cuando los
grupos responden distinto, pooling miente — por eso primero se mira la
consistencia, luego se combina.

**Patrón 3 — Worktree de git para líneas de trabajo paralelas.**
`git worktree add <dir> <rama>` monta una segunda carpeta con otra rama del
MISMO repo (comparten .git). La batería corría en ~/code/tlamati-spike
mientras main quedaba intacto para el README y el gate. Donor: práctica
estándar de git desde 2.5; nosotros la usamos para "el experimento no bloquea
el producto".

## 4. QUÉ DECIDIMOS NO CONSTRUIR

- NO se mergeó skillopt a main: certificado como EVIDENCIA para v2, no como
  feature de v0.1 (una fixture y dos modelos no bastan para shipping; el
  caveat va escrito en el README).
- NO se integró "v2" a la publicación: v2 no es código, es dirección. Al
  README va la sección "The skillopt experiment" con la historia n=3→n=10→
  n=65 (commit ec18bcd en main, gate verde: ruff limpio + 624 tests).
- NO se insistió en el redeploy de Railway por CLI tras dos intentos fallidos
  (regla del fundador: ~2 intentos → declarar y pasar a manual).
- NO se borró el worktree del spike: queda vivo por si el fundador quiere
  revisar crudos (power.log, results.json).

## 5. EL ERROR DEL DÍA

Tres, en orden de valor didáctico:

1. **Mi autopsia dijo "el fix 1a NO disparó" — y era falso.** Emparejé cada
   `cd` con "el siguiente mensaje tool" de la base, pero con llamadas
   paralelas el siguiente mensaje puede ser el resultado de OTRA llamada. Al
   emparejar por tool_call_id, el reminder apareció donde debía (seq26).
   Misma lección del 3g aplicada a mí: cuando tu verificación dice "falló",
   verifica primero la verificación.
2. **El deploy de Railway no tomó el código nuevo** pese a push correcto +
   variable puesta + dos redeploy por CLI. Sin resolver — se declara y se
   pasa a procedimiento manual (dashboard), que es lo correcto tras 2
   intentos. Diagnóstico abierto para mañana: ¿cache de build o deployment
   apuntando a commit viejo?
3. **pkill -f spike_power mató también a mi propio shell** (el patrón
   matcheaba la línea de comando del terminal que lo corría). Menor, pero
   enseña: `pkill -f` matchea contra TODO el comando, incluido el que lo
   invoca. Usar el PID exacto cuando se conoce.

## 6. CONTINUIDAD

Main queda en ec18bcd (README con sección skillopt, 624 tests verdes). La
rama spike/skillopt en 6a50338 (apéndice S1.2 + script + resultados).
Pendiente del fundador: (1) Redeploy manual de proyecto-legal en Railway + prueba
e2e del modo directo para que el cliente pueda probar Producto A; (2) la
publicación v0.1 de tlamati — checklist §5 del handoff (revisar qué NO se
pushea, decisión filter-repo, push private→public); (3) rotar la service key
de Supabase después del piloto (quedó expuesta en el chat de una sesión de
tlamati, y sessions.db la persiste).

**Pregunta abierta para mañana: con mut2 certificado en UNA fixture, ¿cuál es
el siguiente experimento más barato que te convencería de generalizar —
replicar el mismo skill en 3 fixtures nuevas, o dejar que el proposer genere
skills desde cero para tareas que nunca vio?**
