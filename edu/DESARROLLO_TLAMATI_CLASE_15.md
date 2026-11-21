# CLASE 15 — El modelo es un enchufe: routers, paletas y la caza de fantasmas en la historia git

Hoy la sesión tuvo dos vidas. En la primera nos vestimos de auditores: el repo
va a ser público y antes de eso hay que jurar que no queda NADA que revele al
humano detrás del teclado. En la segunda construimos F1 fase A: meter y sacar
modelos de una conversación AGÉNTICA en caliente, con un solo comando. Y entre
medio, un incidente que vale la pena diseccionar — porque aquí lo importante no
fue solo lo que construimos, sino cómo nos detuvimos a tiempo.

## 1. El problema en una escena

Imagina que le prestas tu casa a un desconocido. Barres, ordenas, guardas los
documentos en un cajón y le abres la puerta. Todo impecable… hasta que el
desconocido abre EL cajón de los fotos del pasado. Eso es un repo git: borrar
un archivo hoy NO lo borra de los commits de ayer. La sesión arrancó con la
auditoría del cajón: ¿qué sabe el mundo de ti si mañana `tlamati` es público?

## 2. Qué entendimos (hallazgos con número y comprobante)

Primero, la herramienta: `scripts/audit_publicacion.py` escanea dos mundos — el
árbol actual (archivos `tracked`) y TODA la historia (`git rev-list --objects
--all`: cada versión que existió de cada archivo). Busca secretos (`sk-or-…`,
claves privadas), rutas de máquina (`/home/…`), nombres de negocio. Detalle
fino que vale la pena que entiendas: el propio script de auditoría NO puede
contener los nombres que busca (sería esconder la llave dentro de la caja
fuerte); los patrones específicos del dueño viven en un archivo local
ignorado, `scripts/audit_patterns_local.txt`.

Segundo hallazgo, la herramienta que muerde: `git log -S "usuario"` no busca
"commits que HOY contienen la cadena" — busca commits que la AGREGARON O
QUITARON. Los borrados también aparecen. Si te asustas con 14 "fantasmas",
corrobora con `git grep usuario HEAD` (eso sí es el árbol real). Lección de
literalidad de herramientas: el mismo comando te miente si le preguntas otra
cosa.

Tercero, la pregunta del fundador sobre el caché — "si me voy de opus a sonnet
y regreso, ¿pierdo el caché?" — y su respuesta cambió el diseño: NO se pierde
de forma permanente. El prompt caché de Anthropic vive keyed por (modelo + hash
del prefijo + cuenta) y con TTL de 5 minutos que se renueva con cada hit. El
regreso paga cache_write si se enfrió, y casi nada si volviste a tiempo. Por
eso la palette muestra `cache:hot` / `cache:cold` ANTES de picar: honestidad de
costo en el momento de la decisión. (Etiquetado [P] en el handoff: re-verificar
TTLs contra los docs oficiales antes de publicar el texto.)

## 3. Qué se construyó y cómo (replicable)

El patrón estrella del día es la FACHADA (el donor: el Protocol `Provider` del
propio tlamati, y la idea de "el modelo es un plugin" del PRD). El loop de
`core/loop.py` recibe `provider` por turno y solo usa `.model` y `.stream()`.
Entonces creamos `src/tlamati/core/model_router.py`: un objeto que parece un
provider, se registra como provider, pero por dentro tiene un
`dict[model_id → provider]` y un "activo". `set_model()` cambia el activo; el
loop jamás se entera. Cambiar de cerebro en plena sesión sin tocar el loop =
sustituir el enchufe, no la casa.

Los pasos exactos: (1) `list_models()` en ambos adapters (GET /models con
httpx, MockTransport en tests, cero red — patrón heredado de clase 7); (2)
tests primer: 22 nuevos en `tests/test_model_router_f1.py`, incluida la
invariante de que un stream EN VUELTO termina con el modelo saliente (swap solo
en frontera de turno); (3) cablear la TUI: `/model` abre `ModelPalette`
(Escape = cancelar, fail closed como ApproveScreen), el Header muestra
`modelo: X`, y cada swap se anota en el ledger B5 como evento `model_swap` —
las decisiones del usuario también se auditan. (4) Config nueva:
`[models] tiers = {small=, medium=, frontier=}` + `available` + `filter`
(globs; vacío = solo tiers; "*" = todo — OpenRouter lista 400+ modelos y pintar
la lista cruda sería el problema de las 80 tools en miniatura).

Comandos de la casa, tal cual: `.venv/bin/python -m pytest tests/ -q` (462
verdes), `-m mypy src/` (Success), `-m ruff check src/ tests/` (passed). El
commit: f0f47be.

## 4. El incidente y la lección de gobernanza

A media edición de la palette, un patch mío reemplazó la CABECERA de un método
grande y dejó el cuerpo viejo adentro con sangría de anidado: código parseable,
8 errores de "variable sin definir", y yo a punto de seguir parcheando encima.
Tú dijiste "para aquí" y tenías razón. La regla que sale de esto: los bloques
grandes se reescriben ENTEROS en un parche, nunca a medias; y si algo se rompe,
lo primero es parar y ESCRIBIR el estado antes de seguir tocando. De ahí nació
`HANDOFF_SESION_25_F1_Y_AUDITORIA.md`: qué estaba haciendo, qué pasó, qué
faltaba, en qué orden. El handoff ES el seguro contra el accidente.

Ojo con la higiene: filter-repo reescribe la historia, y lo hicimos CON un
stash abierto — los stashes son objetos git que también cuentan (y también se
reescriben… o se re-contaminan). Ritual correcto para la sesión 25: trabajar
limpio, drop stash, reescribir, `git reflog expire --expire=now --all && git gc
--prune=now`, y verificar las tres pasadas del auditor. Queda un pendiente que
el propio script encontró al final: "proveedor-nube" sigue vivo; el nombre real está en el handoff local en HEAD (PRD y CLASE_1)
; la regla existía pero la segunda pasada no cubrió lo commiteado después. Por
eso la verificación final SIEMPRE es `git grep … HEAD`, no confiar en que el
filtro corrió.

## 5. Teoría del día (patrón reutilizable)

**Fachada / Adapter** (donor del diseño clásico de Gamma et al., "Design
Patterns", 1994, y del Protocol de Python — tipado estructural: te basta con
parecerlo para serlo). Cuando un sistema necesita poder CAMBIAR de proveedor en
vivo, no esparzas `if modelo ==` por el código: define una interface mínima
(.model + .stream), mete el estado mutable en UN objeto y deja que el resto del
mundo crea que habla con un provider. Sirve para modelos, para backends de
pago, para bases de datos. La regla de oro hija de esto: el estado de intercambio
vive en la fachada, y quien muta la fachada (la TUI) es el único que puede
hacerlo — un solo pasador de llaves.

## 6. Continuidad

Serie de arquitectura: clase 14 fue autopsia (forense de sesiones pasadas); hoy
forense del PASADO DEL REPO (historia git) — misma disciplina, otro objeto. Y
cerramos con el arnés aprendiendo a mudar de cerebro. Siguiente estación en el
mapa: F1 fase B (el plan recomienda tiers chico/medio/frontera y el ruteo se
activa al aprobar), la auditoría terminada, y el experimento de 3 brazos que
decide si "opus se siente distinto" es ciencia o fe.

— Hermes, sesión 24 (20-nov-2026). Main = f0f47be, 462 tests, mypy/ruff
limpios. Handoff de continuación: HANDOFF_SESION_25_F1_Y_AUDITORIA.md.
