"""SEC.1: config.yaml gobierna el sandbox; default de red = TRUE (paridad Hermes).

Precedencia: flag CLI explícito > config.yaml > default.
Decisión del fundador (21-nov): la red ya existía (--sandbox-net) pero estaba
OFF por defecto y la TUI ni la cableaba (SEC.2). La jaula sin red era un
segundo candado redundante que solo frenaba pip/railway/curl.
"""

from __future__ import annotations

import argparse

from tlamati.cli import build_parser, resolve_sandbox


def _args(*argv: str) -> argparse.Namespace:
    return build_parser().parse_args(list(argv))


class TestDefaults:
    def test_sin_config_sin_flags_red_on(self) -> None:
        """BREAKING (documentado en commit): default net pasa False -> True."""
        sandbox, net = resolve_sandbox({}, _args("-p", "x"))
        assert sandbox is True
        assert net is True

    def test_parser_sandbox_net_default_none(self) -> None:
        """store_true viejo no distinguía 'no puesto' de False; ahora None =
        'el usuario no opinó' y manda la config."""
        args = _args("-p", "x")
        assert args.sandbox_net is None

    def test_no_sandbox_flag_sigue_apagando_jaula(self) -> None:
        sandbox, net = resolve_sandbox({}, _args("--no-sandbox", "-p", "x"))
        assert sandbox is False
        # net es irrelevante sin jaula (el terminal corre libre, con red real);
        # resolve devuelve igual el valor resuelto, make_tools lo ignora.
        assert net is True


class TestConfig:
    def test_config_net_false_apaga_red(self) -> None:
        cfg = {"sandbox": {"net": False}}
        _, net = resolve_sandbox(cfg, _args("-p", "x"))
        assert net is False

    def test_config_enabled_false_apaga_jaula(self) -> None:
        cfg = {"sandbox": {"enabled": False}}
        sandbox, _ = resolve_sandbox(cfg, _args("-p", "x"))
        assert sandbox is False

    def test_config_seccion_incompleta_usa_defaults(self) -> None:
        cfg = {"sandbox": {"enabled": True}}  # falta net
        sandbox, net = resolve_sandbox(cfg, _args("-p", "x"))
        assert sandbox is True and net is True

    def test_config_basura_no_rompe(self) -> None:
        """sandbox: 'sí' (string) / None → defaults, nunca raise."""
        for cfg in ({"sandbox": "sí"}, {"sandbox": None}, {"sandbox": 42}):
            sandbox, net = resolve_sandbox(cfg, _args("-p", "x"))
            assert sandbox is True and net is True


class TestPrecedence:
    def test_flag_no_sandbox_net_pisa_config_true(self) -> None:
        cfg = {"sandbox": {"net": True}}
        _, net = resolve_sandbox(cfg, _args("--no-sandbox-net", "-p", "x"))
        assert net is False

    def test_flag_sandbox_net_pisa_config_false(self) -> None:
        cfg = {"sandbox": {"net": False}}
        _, net = resolve_sandbox(cfg, _args("--sandbox-net", "-p", "x"))
        assert net is True

    def test_flag_no_sandbox_pisa_config_enabled_true(self) -> None:
        cfg = {"sandbox": {"enabled": True}}
        sandbox, _ = resolve_sandbox(cfg, _args("--no-sandbox", "-p", "x"))
        assert sandbox is False

    def test_flags_explicitos_ganan_sobre_todo(self) -> None:
        cfg = {"sandbox": {"enabled": False, "net": False}}
        args = _args("--sandbox-net", "-p", "x")
        # --no-sandbox no está → enabled lo decide la config (False)
        sandbox, net = resolve_sandbox(cfg, args)
        assert sandbox is False and net is True


class TestParserShape:
    def test_ambas_formas_del_flag_parsean(self) -> None:
        assert _args("--sandbox-net", "-p", "x").sandbox_net is True
        assert _args("--no-sandbox-net", "-p", "x").sandbox_net is False
