# CHANGELOG

Formato: secciones por release; lo no liberado vive en "Unreleased".
Los cambios que rompen la superficie estable (STABILITY.md) se etiquetan
`BREAKING` y siguen la regla de deprecation documentada allí.

## Unreleased

### BREAKING

- SEC.1 (21-nov-2026): el default de red del sandbox cambió OFF→ON. Precedencia
  de config: flag CLI > `config.yaml` > default (`net=True`). Compensación: la
  trifecta letal escala el egreso AUTO→ASK tras consumir contenido no-confiable
  (ver SECURITY.md). Detalle y justificación en STABILITY.md → "Registro de
  breaking changes".

### Agregado

- G2: gap-analysis del dream — el consolidador reporta huecos de memoria
  (advisory, nunca se escriben a archivo).
- M8a: sidecar `.meta.json` (nacimiento/uso por entrada; derivado, fail-soft,
  reconstruible).
- M8b: `tlamati memory status` — uso de caps + entradas frías (advisory).
- M8c: `tlamati memory lint` — near-duplicates cero-LLM (Jaccard, advisory,
  exit 0 siempre).
- SEC.1-3: `config.yaml` gobierna sandbox/red; la TUI cablea sandbox/net; el
  system prompt declara la red efectiva (nunca contradice al tool).

### Documentación

- SECURITY.md: matriz honesta REAL / ILUSORIO-PARIDAD / FRENA.
- STABILITY.md: promesa de estabilidad v0.1 (este contrato).
- README actualizado (red ON por defecto, always/--approve-tool, sandbox).

## v0.1.0

- Primera release taggeada (tag `v0.1.0`, commit 16b234e).
