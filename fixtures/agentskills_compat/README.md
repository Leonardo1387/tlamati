# Fixture: compatibilidad agentskills.io

Copia vendada (verbatim) de los 7 skills del plugin oficial de Obsidian:
`github.com/obsidianmd/obsidian-skills` → `plugins/obsidian/skills/*`,
clonado `--depth 1` el 21-nov-2026. Licencia MIT, © 2026 Steph Ango
(@kepano) — texto completo en `LICENSE-OBSIDIAN-SKILLS`. Proveniencia
registrada también en el NOTICE.md de la raíz.

Contenido: defuddle, json-canvas, knap, obsidian-bases, obsidian-cli,
obsidian-headless, obsidian-markdown (los 7, 140KB — por debajo del tope de
~500KB del plan O1, no hizo falta selección).

Propósito: `tests/test_skills_agentskills_compat.py` certifica que
`parse_skill` de tlamati lee skills REALES del ecosistema agentskills.io sin
crashear y sin perder name/description. El vendado es deliberado: si el
upstream cambia o desaparece, el test sigue midiendo contra el spec que
certificamos el día del vendado.

NO editar estos archivos: son evidencia. Refrescar el fixture = decisión
explícita + re-vendado completo + entrada en CHANGELOG.md.
