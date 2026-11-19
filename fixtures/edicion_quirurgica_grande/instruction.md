pedidos.py tiene ~600 líneas. Solo hay que arreglar DOS funciones con bugs
documentados en sus propios docstrings:

1. `calcular_descuento` (ticket #5101) — la tabla de porcentajes quedó mal
   migrada.
2. `aplicar_envio` (ticket #5102) — ignora la zona y aplica express al revés.

Las reglas correctas están en los docstrings de cada función.

IMPORTANTE: el resto del archivo funciona y está cubierto por otras pruebas.
El validador comprueba byte a byte que TODO lo demás quedó INTACTO: cualquier
cambio fuera de esas dos funciones (incluido reordenar, reescribir o tocar
espacios) se cuenta como fallo. Edita solo lo necesario.

Verifica con python3 verify.py (debe imprimir VERIFY OK).
