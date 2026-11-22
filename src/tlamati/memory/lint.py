"""M8c — Lint cero-LLM de memoria (donor: ai-memory A5, adaptado: Jaccard en
vez de embeddings porque tlamati no tiene ni quiere vector store).
ADVISORY: nunca muta archivos (invariante 3).

Similitud Jaccard sobre tokens normalizados (casefold, sin puntuación).
Sin stopword removal en v1 (YAGNI — medir con tests reales primero).
Con los caps actuales (2x100 entradas) el peor caso son ~20k pares:
trivial en CPU, cero dependencias.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_THRESHOLD = 0.55

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Finding:
    kind: str  # "near_duplicate"
    target_a: str
    entry_a: str
    target_b: str
    entry_b: str
    score: float


def _tokens(text: str) -> set[str]:
    return {t.casefold() for t in _WORD.findall(text)}


def lint(entries: dict[str, list[str]], threshold: float = DEFAULT_THRESHOLD) -> list[Finding]:
    """Compara todos-contra-todos (incluido cross-target memory/user).

    entries = {"memory": [...], "user": [...]}. Devuelve findings ordenados
    por score descendente (determinista: empate → orden de aparición).
    """
    flat: list[tuple[str, str]] = []
    for target in sorted(entries):  # sorted = orden determinista de targets
        for text in entries[target]:
            flat.append((target, text))

    tokenized = [(_tokens(text), target, text) for target, text in flat]
    findings: list[Finding] = []
    for i in range(len(tokenized)):
        tok_a, target_a, entry_a = tokenized[i]
        if not tok_a:
            continue
        for j in range(i + 1, len(tokenized)):
            tok_b, target_b, entry_b = tokenized[j]
            if not tok_b:
                continue
            inter = len(tok_a & tok_b)
            if not inter:
                continue
            score = inter / len(tok_a | tok_b)
            if score >= threshold:
                findings.append(
                    Finding(
                        kind="near_duplicate",
                        target_a=target_a,
                        entry_a=entry_a,
                        target_b=target_b,
                        entry_b=entry_b,
                        score=score,
                    )
                )
    # Estable: sort por -score conserva orden de aparición en empates.
    findings.sort(key=lambda f: -f.score)
    return findings
