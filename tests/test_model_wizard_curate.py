"""Tests de _curate_models (wizard `tlamati model`).

Regresión del bug 24-nov: el default del wizard mostraba top-15 por
context_length (openrouter/auto con precio negativo, variantes :batch) o
nada útil. La lista curada debe: sin variantes ':' , sin routers
openrouter/*, familias principales primero (anthropic, openai, google,
x-ai, deepseek, qwen, moonshotai, ...), más recientes primero por `created`.
"""

from tlamati.cli import _curate_models


def _m(mid: str, created: int = 100, ctx: int = 1000) -> dict:
    return {"id": mid, "created": created, "context_length": ctx}


def test_descarta_variantes_y_routers():
    models = [
        _m("anthropic/claude-sonnet-5"),
        _m("anthropic/claude-sonnet-5:batch"),
        _m("openai/gpt-6:free"),
        _m("openrouter/auto"),
        _m("openrouter/auto-code"),
        _m("~openai/gpt-6"),
    ]
    out = _curate_models(models)
    ids = [m["id"] for m in out]
    assert ids == ["anthropic/claude-sonnet-5"]


def test_orden_familias_principales():
    models = [
        _m("qwen/qwen4-max"),
        _m("deepseek/deepseek-v4"),
        _m("anthropic/claude-fable-5.2"),
        _m("openai/gpt-6.2-sol"),
    ]
    ids = [m["id"] for m in _curate_models(models)]
    assert ids.index("anthropic/claude-fable-5.2") < ids.index("openai/gpt-6.2-sol")
    assert ids.index("openai/gpt-6.2-sol") < ids.index("deepseek/deepseek-v4")
    assert ids.index("deepseek/deepseek-v4") < ids.index("qwen/qwen4-max")


def test_mas_recientes_primero_por_familia():
    models = [
        _m("anthropic/viejo", created=10),
        _m("anthropic/nuevo", created=99),
        _m("anthropic/medio", created=50),
    ]
    ids = [m["id"] for m in _curate_models(models)]
    assert ids[:3] == ["anthropic/nuevo", "anthropic/medio", "anthropic/viejo"]


def test_vendors_menores_aparecen_al_final():
    models = [
        _m("anthropic/claude-x", created=10),
        _m("perplexity/sonar-x", created=99),
        _m("inclusionai/otro", created=50),
    ]
    ids = [m["id"] for m in _curate_models(models)]
    assert ids[0] == "anthropic/claude-x"
    assert set(ids[1:]) == {"perplexity/sonar-x", "inclusionai/otro"}


def test_lista_vacia_no_rompe():
    assert _curate_models([]) == []


def test_sin_created_usa_cero():
    models = [{"id": "anthropic/a"}, {"id": "anthropic/b"}]
    ids = [m["id"] for m in _curate_models(models)]
    assert sorted(ids) == ["anthropic/a", "anthropic/b"]
