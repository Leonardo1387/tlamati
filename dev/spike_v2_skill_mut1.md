---
name: password-validator-spec
description: Prioriza reglas R1-R6 en validador.py y corrige orden, umbrales y checks para pasar verify.py.
---
# Checklist SPEC

1. Lee SPEC.md completo. No modifiques SPEC.md, datos/comunes.txt ni verify.py.
2. Implementa solo `validar(contra: str) -> str` en validador.py.
3. Fuente de comunes: `datos/comunes.txt`; compara `contra.lower()` contra set lower, ignore blanks. Cache optional.
4. Evalúa EXACTO orden; primer fallo devuelve código:
   - R1 LARGO: `len(contra) < 12`.
   - R2 MAYMIN: falta mayúscula O falta minúscula.
   - R3 DIGITO: falta dígito.
   - R4 SIMBOLO: falta `!@#$%^&*`.
   - R5 COMUN: está en comunes (insensible case) después de R1-R4.
5. Si pasa todo devuelve `OK`.
6. Nunca devuelvas booleanos.
7. Prueba casos: `Corta1!` -> LARGO; `todominusculas12!` -> MAYMIN; `Password12345!` -> COMUN; `Lampara!Azul42` -> OK.
8. Verifica `python3 verify.py` hasta `VERIFY OK`.