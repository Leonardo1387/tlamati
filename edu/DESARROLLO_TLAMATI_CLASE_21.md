# Desarrollo Tlamati — Clase 21
## 23-nov-2026: Reanudación de un rebuild interrumpido por memoria agotada

En la clase 20 certificamos un experimento con estadística dura (p=0.0085); hoy cambiamos de taller pero no de método: vamos a reanudar una construcción que se murió a la mitad, y la lección central es que **reanudar cuesta más cuidado que empezar**. Fíjate que el escenario te va a sonar cotidiano: dejaste una máquina trabajando, se apagó la luz a media carga, y al volver no sabes qué quedó bien, qué quedó a medias y qué quedó podrido. Lo que hicimos hoy es el protocolo completo para responder esas tres preguntas sin romper nada más.

### El problema: una tubería de documentos que revienta por un PDF gordo

El proyecto proyecto-legal (~usuario/code/proyecto-legal) es un RAG legal: convierte PDFs de leyes en fragmentos (chunks) buscables. Su tubería tiene fases numeradas —fase 3 extrae texto de PDFs, fase 5 trocea, fase 7 calcula embeddings y arma el índice FAISS—. Ayer, la fase 3 de la rama FISCAL-SAT murió DOS veces con EXIT=137 sobre el mismo archivo: Ley_Federal_de_Derechos.pdf, 565 páginas con tablas. EXIT=137 en Linux significa "el kernel te mató por tragón de memoria" (OOM-killer): la máquina tiene 7GB y pdfplumber, la librería que extrae texto Y tablas, necesitó más que eso para digerir ese PDF.

La sesión anterior ya había aplicado el fix: extraer ese PDF con fitz (PyMuPDF), otra librería más frugal que ignora las tablas, y guardar el resultado como JSON en 01-ocr/output/extracted/. El PDF problemático se movió a una carpeta de cuarentena (01-ocr/_holding_LFD/) para que la fase 3 no lo volviera a ver. Pero la sesión se congeló esperando el proceso y todo lo demás quedó en el aire.

### Lo primero: NO creas, VERIFICA el estado del disco

Aquí está la primera herramienta conceptual del día: **el handoff manda, pero el disco tiene la última palabra**. El documento de traspaso (HANDOFF_CORPUS_2026-11-23_5.md) decía "extracted/ tenía solo 2 de 11+ JSON, verificar conteos antes de pasar a fase 4". Un agente perezoso habría relanzado todo a ciegas. Nosotros corrimos primero un inventario:

```bash
cd /home/usuario/code/proyecto-legal
pgrep -af pipeline.py          # ¿quedó algún proceso vivo de ayer? (no)
ls -la 01-ocr/output/extracted/  # ¿cuántos JSON hay? (2: RMF y LFD)
ls 01-ocr/_holding_LFD/        # ¿la cuarentena sigue armada? (sí)
free -h                        # ¿cuánta RAM hay ahora? (6.2GB libres)
```

Y una decisión de lectura de código que ahorró un desastre: el script de rebuild completo (scripts/_build_fiscal_sat_b.sh) empieza con `rm -rf 01-ocr/output/extracted/*` — limpiar intermedios. Correrlo tal cual habría BORRADO el JSON de LFD que costó un OOM producir. Moraleja: **un script de "rebuild limpio" asume que todo se puede regenerar; cuando hay un artefacto irrepetible en el camino, el script ya no sirve y hay que correr las fases a mano**. Leímos fase_3_triage_extraer_convertir en pipeline.py (línea ~1191) para confirmar que re-extrae todo sin saltar: los 11 PDFs sanos se re-procesan (~2 min, aceptable) y el JSON de LFD sobrevive porque su PDF no está en input/.

### Ejecutar sin congelarse: background + notificación

La segunda herramienta del día es operativa. La sesión anterior murió por hacer `process(wait)` sobre un proceso largo. Hoy la regla fue: procesos de más de 5 minutos SIEMPRE en background con notify_on_complete, y seguir trabajando mientras.

```bash
venv/bin/python pipeline.py --fase 3 --ciudad FISCAL-SAT 2>&1 | tee logs/b3_fase3_fiscal_reanudada.log &
# (en Hermes: terminal background=true, notify_on_complete=true)
```

Con la fase 3 corriendo, usamos el tiempo muerto para leer el plan completo (handoffs _3 y _4), el probe de verificación (scripts/_probe_b3_fiscal.py) y el código de fase 7. Cuando fase 3 terminó (EXIT=0, "Extraidos: 11 | Convertidos: 36"), las fases siguientes fueron rápidas:

```bash
venv/bin/python pipeline.py --fase 4 --ciudad FISCAL-SAT   # limpieza: 12 docs, dedup 12→12
venv/bin/python pipeline.py --fase 5 --ciudad FISCAL-SAT   # chunker v2: 20,833 chunks con linaje
venv/bin/python pipeline.py --fase 7 --ciudad FISCAL-SAT   # embeddings locales + FAISS ($0, 28s)
venv/bin/python scripts/_append_fiscal_anexo2.py --commit  # re-append: +1,498 chunks → 22,331
```

Nota el patrón dry-run/--commit del último script: corre primero SIN escribir nada y te muestra qué haría (314 fichas, 1498 chunks, 0 defectos); solo con --commit toca el índice, y antes hace backup (*.bak_anexo2_<timestamp>). Ese patrón —**ensayar, mostrar, confirmar, respaldar, aplicar**— es el mismo de las migraciones de base de datos profesionales.

### La teoría detrás: swap atómico y la unidad atómica = documento

¿Por qué tanto baile de backups y rebuilds completos en vez de "editar" el índice? Un índice FAISS es un arreglo de vectores donde la posición N corresponde al registro N del metadata.json. Borrar un vector de en medio (remove_ids) reordena TODO y cuesta O(n). El patrón correcto del proyecto: **reconstruir la rama entera aparte y reemplazar el directorio de un golpe (swap atómico)**, con backup frío previo (_bak_B_FISCAL-SAT_20261123). Y la unidad de reindex es el DOCUMENTO completo, nunca el chunk suelto: una reforma legal renumera artículos dispersos, y actualizar chunk por chunk deja "chunks huérfanos" —texto derogado que sigue apareciendo en búsquedas—. Esto es el equivalente, en datos, de por qué git commitea snapshots completos y no diffs aplicables a medias.

### Verificar es medir, no mirar: el probe y la regresión escondida

El probe del repo dio verde: ntotal==metadata (22331), linaje presente, RESICO 113-E..J con su contexto, LFD 3750 chunks. Pero el harness de recall (tests/harness_slang_recall.py, 26 consultas con respuesta conocida, corre con la API key vacía = $0) contó una historia más interesante: global 13/26 contra 14/26 antes del rebuild. **Un caso había retrocedido**: "cuando caducan las facultades del sat para revisar" antes daba HIT en la posición 4 y ahora MISS.

Aquí viene la parte que quiero que estudies: el diagnóstico por capas. Escribimos cuatro scripts (_diag_caducidad67{,b,c,d,e}.py) que separan el problema por etapa:
1. ¿La huella de texto sigue en el índice? Sí — 6 chunks del CFF art. 67 la contienen.
2. ¿FAISS crudo la encuentra? No — ni antes ni después. El HIT viejo no venía de los vectores.
3. ¿BM25 (el buscador de palabras exactas) la encuentra? Antes: posición 27. Ahora: posición 57.

Causa raíz: el chunk nuevo empieza con `[Capitulo I]\n\n[Art. 67. | Frac. I] —` —el linaje jerárquico que cura la ceguera de metadata— pero esos tokens de encabezado DILUYEN el match de BM25 para una pregunta coloquial. El remedio viejo (HIT@4) era frágil y el nuevo fix (léxico escenario→concepto) ya está identificado. **Un instrumento de medición honesto te muestra las regresiones; la tentación de reportar solo el global verde es lo que pudre los proyectos.**

### El error del día (y la confusión del fundador)

El harness vial (12 casos de tránsito, ~$0.26) dio 8/12 con tres fallos rarísimos: las consultas de CDMX buscaban dentro del índice CORPORATIVO y costaban $0.0000 (ni llamaron al modelo). El fundador lo vio y estalló con razón: "mezclaste todo, vial y escudo legal nunca se cruzaban". Diagnóstico en tres comandos: `git status router/` (limpio — no lo toqué hoy), `grep CIUDAD_DEFECTO router/ciudades.py` (= "CORPORATIVO"), `git log -S` (el cambio es del commit ea3605d, semanas atrás, INTENCIONAL del pivot a MVP). O sea: el harness vial local ya estaba roto ANTES de esta sesión; mi rebuild de FISCAL-SAT no tocó ni un byte del carril vial (07-index/embeddings/: 598 chunks, 100% CDMX, mtime de junio).

La lección doble: (1) cuando el usuario grita "rompiste X", la respuesta no es defenderse ni disculparse — es **fechar el cambio con git** (git log -S "texto" busca en qué commit se introdujo una cadena; es arqueología exacta, no opinión); (2) el fundador tenía razón en el fondo aunque no en la atribución: SÍ hubo una decisión de comunicación fallida —vender que "FASE B arreglaría el retrieval" sin aclarar que Boardy (el examen de escenarios de negocio) no se movería porque mide otra clase de gap. Expectativa mal calibrada = confianza quemada. Se anota y se corrige.

### Lo que NO se construyó hoy

No se arregló el harness vial (decisión explícita del fundador: el producto vial está en pausa, el MVP de Jorge no lo usa). No se implementó el léxico escenario→concepto (opción A, $0, es la siguiente acción del handoff _6). No se re-chunkearon LABORAL/CONSUMIDOR/CONSTITUCION (sus recall ya son 3/3, 2/2 — quizá no urgen). Decir que no con razones es parte del trabajo.

### Cierre con números

Deploy a producción verificado con un endpoint $0 (/bibliografia: 22,331 fragmentos vivos), batería Boardy 7 GREEN/3 GAP ($0.19, mismo perfil que el baseline — los 3 GAP esperan la opción A), batería Boolanga 5-6/6 grounded reales ($0.13) con un hallazgo nuevo: la NOM-004 vive en COMEX pero la consultaron en CONSUMIDOR — gap de colocación cross-rama, fix barato documentado. Costo total del día en APIs: ~$0.45. Todo el rebuild: $0 (embeddings locales).

**Para mañana: el léxico escenario→concepto (opción A) es la palanca que falta para que las preguntas de NEGOCIO sin jerga legal ("queremos traer mercancías de China") encuentren su artículo — ¿lograremos que los 3 GAP de Boardy pasen a GREEN sin tocar el chunker, solo con mapeos deterministas?**
