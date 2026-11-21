# REGLAS del ducto (contrato exacto, R-01 a R-30 en orden de ejecucion)

## R-01 — modulo s01

v['palabras'] = palabras de v['crudo2']['Texto'] en minusculas: solo letras (incluye acentos y apostrofos), sin puntuacion.

## R-02 — modulo s02

v['unicas'] = dedup de palabras CONSERVANDO primera aparicion (orden).

## R-03 — modulo s03

v['contador'] = {palabra: apariciones} contando TODAS las palabras.

## R-04 — modulo s04

v['top3'] = 3 entradas mas frecuentes del contador (lista de tuplas (palabra, n)); desempate -> alfabetico ascendente.

## R-05 — modulo s05

v['iniciales'] = inicial de cada palabra de top3 en mayusculas, unidas con '.'.

## R-06 — modulo s06

v['registro'] = claves de crudo2['Registro'] con strip() Y minusculas.

## R-07 — modulo s07

v['activo'] = True SI Y SOLO SI registro.get('activo') == 'si' (string exacto).

## R-08 — modulo s08

v['monto2'] = Decimal(registro['monto']) 2 dec. HALF_UP, str.

## R-09 — modulo s09

v['con_desc'] = monto2 * (1 - desc/100), desc=registro.get('desc','0'); 2 dec. HALF_UP, str.

## R-10 — modulo s10

v['fechas2'] = crudo2['Fechas'] (YYYY/MM/DD) parseadas a date y ordenadas ASC, salida ISO 'YYYY-MM-DD'.

## R-11 — modulo s11

v['rango'] = dias entre min y max de fechas2: (max - min).days, NO inclusivo.

## R-12 — modulo s12

v['mapa_inv'] = invertir crudo2['Mapa']; colision de valores -> gana la PRIMERA clave.

## R-13 — modulo s13

v['codigo'] = crudo2['Codigo'] sin caracteres no alfanumericos (SOLO [A-Za-z0-9]), MAYUSCULAS.

## R-14 — modulo s14

v['checksum'] = suma(ord(c) * posicion) sobre v['codigo'], posicion EMPIEZA EN 1, mod 97.

## R-15 — modulo s15

v['valido'] = checksum (int) == int(registro.get('check', '-1')); comparacion ENTERA.

## R-16 — modulo s16

v['numeros'] = crudo2['Numeros'] (str) a Decimal 2 dec. HALF_UP, lista de str.

## R-17 — modulo s17

v['suma'] = suma de numeros en Decimal exacto, str 2 dec. HALF_UP (NUNCA float).

## R-18 — modulo s18

v['pares'] = elementos PARES de crudo2['Lista'] (int), en orden original.

## R-19 — modulo s19

v['producto'] = producto de los pares NO nulos; si no queda ninguno -> 1.

## R-20 — modulo s20

v['mayus'] = crudo2['Texto'] en MAYUSCULAS (solo cambiar caso, nada mas).

## R-21 — modulo s21

v['frase'] = unir crudo2['Frases'] con ' | ' haciendo strip() de cada una.

## R-22 — modulo s22

v['acronimo'] = iniciales (mayusculas, sin separador) de las palabras de frase que EMPIEZAN con letra (ignorar '|' y no-alfabeticos).

## R-23 — modulo s23

v['paginas'] = ceil(len(palabras) / 5) — division hacia ARRIBA.

## R-24 — modulo s24

v['matriz'] = trocear crudo2['Lista'] en filas de 3; ultima fila incompleta se RELLENA con 0.

## R-25 — modulo s25

v['traspuesta'] = traspuesta de matriz (filas -> columnas, como listas).

## R-26 — modulo s26

v['diagonal'] = diagonal PRINCIPAL de matriz: [i][i].

## R-27 — modulo s27

v['firma'] = primeros 16 chars del sha256 hex del JSON CANONICO (sort_keys=True, sin espacios) de {'suma': v['suma'], 'checksum': v['checksum']}.

## R-28 — modulo s28

v['resumen'] = {'total': suma str, 'activo': bool, 'valido': bool, 'paginas': int} — TIPOS exactos.

## R-29 — modulo s29

v['claves'] = claves de resumen ordenadas ALFABETICAMENTE.

## R-30 — modulo s30

v['salida'] = {'resumen':..., 'firma':..., 'claves':...} — paquete final del ducto.

## Nota

Cada modulo declara sus propios imports; revisa el
encabezado del modulo si necesitas Decimal/date/re/math/json/hashlib.
