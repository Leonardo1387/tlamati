from json_loads import loads  # ← no existe; debería ser: from json import loads


def parsear_usuario(texto):
    datos = loads(texto)
    return {"nombre": datos["nombre"].strip(), "activo": bool(datos.get("activo"))}
