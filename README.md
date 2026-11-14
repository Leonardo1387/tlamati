# tlamati — arnés agéntico open-source (Apache-2.0)

Estado 14-nov-2026: investigación + PRD + guía listos. Código: Fase A pendiente de arranque.

```
PRD_TLAMATI.md               producto: qué, por qué, métricas, no-objetivos
GUIA_IMPLEMENTACION.md       fases A-F, inventario máquina, qué falta descargar
research/01_HALLAZGOS_PASO1.md  qué hace sobresalir un arnés (foros/HN/winder)
research/02_ESTUDIO_HARNESSES.md anatomía comparada de 8 arneses (LOC, sandbox, memoria)
research/sources/            capturas crudas citables (winder snapshot, HN comments, lethal trifecta, arxiv harness2)
vendor/                      clones depth-1 para REA/lectura: codex, opencode, qwen-code,
                             gemini-cli, grok-build, DeepSeek-Reasonix, harness2, claude-code
```

## Correcciones de identidad encontradas en la ruta
- "grok bot" → xai-org/grok-build (Rust, Apache-2.0, 27.7k★).
- "dots" → dots.llm1 es un MODELO (studio-dots-ai, MIT), no arnés; el harness de DeepSeek es esengine/DeepSeek-Reasonix (MIT, Go) — descontinuado 12-nov-2026, forks permitidos.
- claude-code y cursor son PRIVATIVOS: REA solo conductual sobre el bundle npm local; reutilizar código únicamente de MIT/Apache (Reasonix, hermes-agent, opencode, codex, gemini-cli, qwen-code).
