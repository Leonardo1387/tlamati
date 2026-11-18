# SPEC — Validador de contraseñas v2.3

## 1. Propósito
Este documento define el contrato EXACTO de `validador.validar(contra)`.
Cualquier implementación que no cumpla todas las reglas R1-R6 está fuera
de especificación y debe corregirse.

## 2. Alcance
- Módulo: `validador.py` (raíz del proyecto).
- Archivo de datos: `datos/comunes.txt` (una contraseña por línea).
- API pública: UNA sola función `validar(contra: str) -> str`.

## 3. Reglas de validación

### R1 — Longitud mínima
La contraseña debe tener al menos 12 caracteres. Si no, el resultado es
el código `LARGO`.

### R2 — Mayúsculas Y minúsculas
Debe contener al menos una letra mayúscula Y al menos una letra minúscula.
Si falta cualquiera de las dos, el resultado es `MAYMIN`.

### R3 — Dígitos
Debe contener al menos un dígito (0-9). Si no, el resultado es `DIGITO`.

### R4 — Símbolos
Debe contener al menos un símbolo del conjunto: `! @ # $ % ^ & *`
Si no, el resultado es `SIMBOLO`.

### R5 — Lista de contraseñas comunes
No debe aparecer en `datos/comunes.txt`. La comparación es
INSENSIBLE a mayúsculas/minúsculas (ej. si la lista tiene
`password12345!`, entonces `Password12345!` también se rechaza).
Si aparece, el resultado es `COMUN`.

### R6 — Orden de evaluación (PRIORIDAD, obligatoria)
Las reglas se evalúan EN ESTE ORDEN y se devuelve el código del PRIMER
fallo encontrado:

    R1 (LARGO) → R2 (MAYMIN) → R3 (DIGITO) → R4 (SIMBOLO) → R5 (COMUN)

Si ninguna regla falla, se devuelve `OK`.

## 4. Tabla de códigos de retorno

| Código    | Significado                          |
|-----------|--------------------------------------|
| LARGO     | menos de 12 caracteres               |
| MAYMIN    | falta mayúscula o falta minúscula    |
| DIGITO    | falta al menos un dígito             |
| SIMBOLO   | falta al menos un símbolo válido     |
| COMUN     | está en la lista de comunes          |
| OK        | contraseña válida                    |

## 5. Ejemplos normativos

- `validar("Corta1!")` → `LARGO` (7 caracteres; aunque también le falten
  cosas, R1 tiene prioridad).
- `validar("todominusculas12!")` → `MAYMIN` (no tiene mayúscula; aunque
  esté o no en comunes, R2 va antes que R5).
- `validar("Password12345!")` → `COMUN` (cumple R1-R4 pero está en la
  lista, comparación insensible).
- `validar("Lampara!Azul42")` → `OK`.

## 6. Notas de implementación
- La lista de comunes se lee del archivo en cada llamada o se cachea;
  da igual, pero el archivo es la fuente de verdad.
- NO se aceptan valores de retorno booleanos: SIEMPRE el código string.

## 7. Changelog (ruido histórico, no normativo)
- v2.0: se añadió R4 (símbolos).
- v2.1: la lista de comunes pasó a archivo externo.
- v2.2: se documentó la prioridad R6 (antes cada quien evaluaba como quería).
- v2.3: ejemplos normativos.
