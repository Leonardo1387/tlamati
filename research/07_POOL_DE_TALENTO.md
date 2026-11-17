# 07 — Pool de talento: perfiles de programador derivados de sesiones de agente
# (diseño de negocio inicial, 17-nov-2026, sesión 13 — planteado por el fundador)

## DECISIÓN DE ALCANCE DEL FUNDADOR (17-nov sesión 13, verbatim: "ahorita no
## vamos a construir ese sistema, lo único que quiero es el que revisa y crea
## el perfil del usuario enfocado en curriculum basado en lo que está
## construyendo, todo lo demás no es necesario ahorita")

SCOPE REAL de la rama (lo único que se construirá, y NO ahora):
- **SOLO el componente PERFILADOR**: el que revisa sesiones y crea un perfil
  de usuario ENFOCADO EN CURRÍCULUM basado en lo que está construyendo.
- FUERA DE SCOPE (por ahora): matchmaking, anonimización tipo Bumble, lado
  empresa, pool de 50k, percentiles contra pool, revelación de identidad.
  Este doc queda como contexto de la visión completa, NO como spec.

PLAN DEL PILOTO ACORDADO (post-Tlamati v0.1):
1. Terminar TODOS los pasos de Tlamati (D3 → Fase E → v0.1 publicado).
2. Construir el perfilador como herramienta que lea el HISTORIAL REAL:
   la base de Hermes (~/.hermes/state.db — VERIFICADO 17-nov: 575 sesiones,
   52,397 mensajes, tablas sessions/messages con FTS) contiene todo lo que
   el fundador ha construido con Hermes (Tlamati, [REDACTED_PROYECTO], App Vial,
   leads B2B, DOF pipeline, videos, decks...).
3. Generar EL PERFIL DEL FUNDADOR con ese historial = prueba real.
4. Con el resultado en mano, decidir: ¿cómo sale el perfil? ¿qué es lo
   importante de medir? (la lista de 5 señales de abajo es hipótesis —
   el piloto la valida o la corrige).
SINERGIA TÉCNICA: cuando exista, el perfilador de sesiones de TLAMATI será
un plugin D2 sobre session store C1 + ledger B5; pero el PILOTO corre sobre
el state.db de Hermes (que ya existe y es rico) — no requiere esperar nada.
RESPUESTA HERMES 17-nov: SÍ ES POSIBLE, datos verificados en vivo.

## LA IDEA (con palabras del fundador)

Rama de negocio nueva: la plataforma la usan programadores (o estudiantes —
no importa). De SUS sesiones de trabajo con el agente se construye un perfil
de talento: historial, juicio para resolver problemas. Con ese pool (el
fundador ya tiene ~50 mil programadores en sus servicios), las empresas
integran lo que buscan para un puesto, y el sistema devuelve candidatos que
cubren el perfil — ANONIMIZADOS hasta que la empresa elige sus 2-3
prospectos. Un "Bumble de contrataciones técnicas" donde la evidencia no es
un CV auto-reportado sino el RASTRO REAL de cómo trabaja la persona.

Por qué esto es fuerte: el CV miente; la telemetría de sesiones no. Nadie
puede inflar "resolví el bug en 4 turnos verificando con tests" si cada
turno quedó registrado.

## QUÉ ES LO MÁS IMPORTANTE A MEDIR (las 5 señales)

Regla de diseño: medir JUICIO, no volumen. Un programador que escribe 500
líneas sin verificar vale menos que uno que escribe 50 y las prueba. Las 5
señales, en orden de valor para un contratador:

1. **RESOLUCIÓN EFECTIVA** — ¿las tareas terminan verificadas?
   Qué mirar: proporción de sesiones con final exitoso VERIFICADO (tests que
   pasan, comando que corre, archivo que existe) vs final declarado sin
   prueba. Fuente: session store (stop_reason) + ledger (tool_events de
   terminal/tests tras el último cambio).
2. **JUICIO** — la señal más difícil de fingir y la más valiosa.
   Qué mirar: (a) ¿verifica ANTES de declarar terminado? (b) cuando algo
   falla, ¿lee el error antes de reintentar o dispara cambios a ciegas?
   (c) ¿explora antes de editar (lee el archivo, busca) o edita de memoria?
   (d) ¿usa el plan-mode / delega cuando la tarea es grande? Fuente: secuencia
   de tool_events (patrones read→edit→test vs edit→edit→edit).
3. **AUTONOMÍA** — ¿cuánta supervisión necesita?
   Qué mirar: aprobaciones pedidas/concedidas por tarea (ledger: decisiones
   ask_*), intervenciones humanas por sesión, re-delegaciones. Un perfil con
   autonomía alta Y resolución alta = senior; autonomía alta con resolución
   baja = cowboy (alerta para el contratador).
4. **RECUPERACIÓN ANTE EL ERROR** — qué hace cuando truena.
   Qué mirar: turnos que tarda en volver a verde tras un fallo; cuántos
   reintentos ciegos del mismo comando; honestidad (reporta el bloqueo vs lo
   disimula — detectable en patrones de ledger: error seguido de más errores
   idénticos = insistencia ciega).
5. **ECONOMÍA** — eficiencia con recursos.
   Qué mirar: tokens/costo por tarea resuelta (turn_costs del ledger),
   cache_read alto = sabe estructurar trabajo por lotes; contexto inflado =
   trabaja desordenado. Normalizado por tipo de tarea (no comparar un fix de
   1 línea con un refactor).

Más una capa descriptiva (no evaluativa):
6. **HUELLA DE STACK Y DOMINIO** — lenguajes, frameworks, tipos de archivo
   tocados (extensiones en tool_events de read/write), dominios (tests,
   migrations, CI, docs, frontend/backend), tamaño típico de los cambios.
   Esto es lo que la empresa FILTRA primero; las 5 señales son lo que la
   convence después.

## CÓMO SE MIDEN (mecánica honesta)

Tres capas, de barata a cara:

- CAPA 1 — MÉTRICAS DETERMINISTAS (gratis, explicables, en tiempo real):
  contadores y proporciones sobre lo que YA capturamos. El session store (C1)
  guarda cada mensaje; el ledger (B5) guarda cada tool_event con su decisión
  y cada turn_cost. Ejemplos computables HOY sin modelo: % sesiones con
  terminal-exitoso tras último write; ratio read:edit; reintentos ciegos;
  ask_denied por sesión; tokens/tarea. TODA métrica del perfil debe ser
  auditable: el programador puede ver su propia ficha y los números crudos
  detrás (transparencia = confianza = adopción).
- CAPA 2 — PATRONES DE SECUENCIA (reglas, barato): mini-gramáticas sobre la
  secuencia de tool_events. "edit→edit→edit sin read previo" = edita a
  ciegas. "error→read del error→fix→test" = juicio. Se calibran con unas
  cientos de sesiones etiquetadas a mano.
- CAPA 3 — JUEZ LLM SOLO SOBRE MUESTRA (caro, puntual): un modelo con
  rúbrica fija evalúa UNA sesión representativa por periodo (no todas) para
  señales sutiles (calidad del razonamiento, honestidad en el reporte). La
  rúbrica y el score viajan con la ficha. NUNCA el LLM define el ranking
  solo: combina con capa 1-2 (un perfil 100% LLM es caro, ruidoso y
  demandable).

Agregación: cada sesión produce un vector de señales; el perfil es la
ventana móvil (últimas N sesiones) + percentil CONTRA EL POOL (p85 en
juicio significa mejor que el 85% de los 50k). El percentil es lo que la
empresa entiende sin entrenamiento.

## CÓMO SE ARMA EL PERFIL SIN SER UN LIBRO

Formato de ficha para el contratador = **UNA PANTALLA** (30 segundos de
lectura):

```
┌──────────────────────────────────────────────┐
│ CANDIDATO #A7F3 (anónimo)     p82 general    │
│ Radar:  Resolución ████▌  Juicio ████▌        │
│         Autonomía ███▌   Recuperación ████    │
│         Economía ███                          │
│ Stack: Python, FastAPI, Postgres, Docker      │
│ Dominios: APIs backend, pipelines CI          │
│ Evidencia (3 chips, clickeables a métrica):   │
│  · "92% de tareas cerradas con test verde"    │
│  · "p95 en recuperación tras fallo"           │
│  · "usa plan-mode en el 60% de tareas >1h"    │
│ Volumen: 148 sesiones · 4 meses · tendencia ↑ │
│ [Ver detalle de percentiles] [Solicitar match]│
└──────────────────────────────────────────────┘
```

Reglas de la ficha:
- Números, no adjetivos ("p95 en recuperación", nunca "excelente recuperándose").
- Máximo 3 chips de evidencia — los mejores percentiles del candidato.
- Tendencia visible (últimas 20 sesiones vs anteriores): el talento crece.
- Perfil PROVISIONAL hasta un mínimo de sesiones (~20): honestidad con la
  empresa ("poca historia aún") en vez de confianza espuria.
- Detalle completo (gráficas, histórico) en segunda pantalla, para el
  contratador técnico que quiera profundizar.

Del lado EMPRESA: publican un perfil de puesto como PESOS sobre las 5
señales + filtros de stack ("juicio ≥ p70, resolución ≥ p80, Python,
backend"). El match devuelve ranking anonimizado. La empresa elige 2-3 →
Doble opt-in de revelación: el candidato ACEPTA revelar identidad para ESA
empresa (nunca revelación automática).

## PRIVACIDAD Y CONSENTIMIENTO (innegociable — sin esto no hay producto)

1. **OPT-IN EXPLÍCITO del programador** para entrar al pool (--talent-export
   o similar). Por default NADA sale de su máquina. Contra-ejemplo: el propio
   OpenCrawl avisa "sessions are team-visible by default and can contain
   sensitive information" — nosotros al revés: local por default.
2. **Las sesiones contienen código, rutas y a veces secretos.** El perfil
   viaja como MÉTRICAS DERIVADAS, nunca contenido crudo. La capa 3 (juez
   LLM) corre local o sobre versiones sanitizadas (secretos redactados).
3. **El programador ve su propia ficha** antes que nadie, y puede excluir
   sesiones concretas del perfil (la sesión del proyecto confidencial de su
   trabajo NO alimenta el pool).
4. **Anonimato real hasta el doble opt-in** (empresa elige + candidato acepta).
5. Cumplimiento: los 50k del pool existente necesitan su propio flujo de
   consentimiento — no se puede perfilar retroactivamente a quien no firmó.

## ANTI-GAMING (si el perfil vale dinero, lo van a intentar manipular)

- Medir juicio, no volumen: hacer 50 sesiones triviales no sube percentiles
  de resolución si las tareas son iguales de fáciles (normalizar por
  dificultad estimada: archivos tocados, tokens, tipo de cambio).
- Los patrones de secuencia son caros de fingir: "leer el error antes de
  reintentar" requiere realmente hacerlo, sesión tras sesión.
- Auditoría muestral (capa 3) como segundo par de ojos sobre perfiles
  outlier (sospechosamente perfectos).
- El candidato ve su ficha → no hay métricas secretas que explotar a ciegas.

## INTEGRACIÓN CON TLAMATI (cuándo y cómo — regla anti-speculative)

NO se codifica ahora. El punto de integración natural cuando el fundador lo
arranque:
- Los datos YA existen: session store C1 + ledger B5 capturan todo lo
  necesario localmente.
- El exporter sería un **PLUGIN D2** (consumidor concreto; cero cambios al
  núcleo) + flag opt-in de CLI. Es exactamente el tipo de extensión que la
  costura de la Clase 9 permite.
- SINERGIA con el asterisco multiplayer (research/06): ambos negocios exigen
  la misma precondición — persistencia rica de sesiones (hoy falta el
  transcript verbatim de subagentes en el session store). Si se aprueban las
  dos ramas, esa precondición se construye UNA vez.
- El perfil percentil contra pool de 50k requiere el lado servidor (agregar
  perfiles exportados, calcular percentiles, ranking) — eso es OTRO proyecto
  (como OpenCrawl era otro proyecto): Tlamati exporta, el servicio del
  fundador agrega. Frontera limpia: el harness local nunca conoce el pool.

## PENDIENTES DE DECISIÓN (para cuando el fundador arranque la rama)

1. ¿Las sesiones de Hermes también alimentan perfiles, o solo Tlamati?
   (mismo formato de datos; Hermes ya tiene session store propio)
2. ¿Dificultad de tarea: estimación automática o la declara el usuario?
3. Modelo de ingreso: ¿la empresa paga por match revelado, por suscripción
   al pool, o por contratación (success fee)? — conecta con el programa
   (skill programa-negocio-2026-11): B2B por seat ya existe como ancla.
4. ¿El estudiante ([REDACTED_PROYECTO]/programa) entra al pool con perfil "junior en
   formación"? Su tendencia ↑ puede valer más que un senior plano.
