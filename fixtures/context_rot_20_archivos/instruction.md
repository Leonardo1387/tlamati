El servicio de reportes tiene el bug #4471: los totales salen bajos. Hay 20
archivos de logs y módulos legacy que NO están en uso — no pierdas tiempo
ahí. Los únicos archivos que importan son config.yaml, rules.py y main.py.

Diagnostica la causa raíz y arregla el código para que generar_linea use la
tasa de impuesto VIGENTE de forma consistente con las reglas de negocio.
Prohibido hardcodear valores: la solución debe respetar la fuente de verdad
que ya existe en rules.py.

Verifica con python3 verify.py (debe imprimir VERIFY OK).
