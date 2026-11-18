El informe de inventario calcula el impuesto con un valor por defecto (0.16)
en lugar del que viene en datos/config.json (0.19). El fallo NO está en un solo
archivo: recorre inventario/config.py, inventario/informe.py,
inventario/normalizar.py y los JSON de datos/ para encontrar la causa raíz.
Arregla el código para que generar_informe use el impuesto real de la config.
Verifica con python3 verify.py (debe imprimir VERIFY OK).
