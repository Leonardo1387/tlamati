Este directorio es un repositorio git con 6 commits. El ÚLTIMO commit rompió
la función formatear_ruta de rutas.py (los 5 commits anteriores la dejaban
bien: unía con barras '/'). Tu tarea:
1. Usa git (git log, git diff, git show) para averiguar QUÉ commit introdujo
   el fallo.
2. Escribe el hash COMPLETO de ese commit (40 caracteres hex) en un archivo
   llamado culpable.txt en este directorio.
NO arregles rutas.py ni hagas commits nuevos — solo identifica al culpable.
Verifica con python3 verify.py (debe imprimir VERIFY OK).
