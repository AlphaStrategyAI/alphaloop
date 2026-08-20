from __future__ import annotations

from pathlib import Path

import alphaloop
from alphaloop.cli.main import create_parser, main


ROOT = Path(__file__).resolve().parents[1]


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_pyproject_script_points_at_alphaloop_cli():
    text = _pyproject_text()
    assert 'alphaloop = "alphaloop.cli.main:main"' in text
    assert "openstrategy.cli:main" not in text


def test_hatch_wheel_does_not_point_at_missing_openstrategy():
    assert "src/openstrategy" not in _pyproject_text()


def test_dunder_version_matches_pyproject():
    text = _pyproject_text()
    assert f'version = "{alphaloop.__version__}"' in text


def test_package_docstring_says_alphaloop():
    assert "OpenStrategy" not in (alphaloop.__doc__ or "")
    assert "alphaloop" in (alphaloop.__doc__ or "").lower()


def test_live_names_are_not_in_root_all():
    forbidden = {
        "AlpacaAdapter",
        "Broker",
        "BrokerConfig",
        "CONFIRM_LIVE_FLAG",
        "LiveTradingRefused",
    }
    assert forbidden.isdisjoint(set(alphaloop.__all__))


def test_cli_help_uses_alphaloop_not_openstrategy(capsys):
    rc = main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "alphaloop" in out.lower()
    assert "OpenStrategy" not in out


def test_cli_parser_prog_is_alphaloop():
    parser = create_parser()
    assert parser.prog == "alphaloop"


def test_all_exports_exist_on_package():
    missing = [name for name in alphaloop.__all__ if not hasattr(alphaloop, name)]
    assert missing == []


def test_contracts_do_not_import_live():
    root = ROOT / "src" / "alphaloop" / "contracts"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "alphaloop.live" not in text
        assert "from ..live" not in text


def test_cli_help_lists_start(capsys):
    rc = main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "start" in out
    assert "submit" in out


def test_published_home_is_overnight_lab():
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert "find alpha with DSR > 1.0" not in text
    assert "does not promise alpha" in text.lower() or "does **not** promise alpha" in text
    assert "FOUND" in text
    assert "NO_EVIDENCE" in text
    assert "INCONCLUSIVE" in text
    assert "alphaloop start" in text


def test_published_example_yaml_declares_example_dataset():
    from importlib.resources import files

    from alphaloop.contracts.artifacts import hash_bytes

    digest = hash_bytes(
        files("alphaloop.runtime.example_dataset")
        .joinpath("prices.parquet")
        .read_bytes()
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for text in (readme, home):
        assert "dataset_id: ds_example" in text
        assert f"sha256: {digest}" in text
        assert "alphaloop dataset" in text
    assert "If the spec declares a dataset" not in readme
    assert "A spec must declare a content-addressed `dataset`" in readme


def test_loop_help_is_heritage_not_find_alpha(capsys):
    parser = create_parser()
    try:
        parser.parse_args(["loop", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "find alpha with DSR > 1.0" not in out
    assert "heritage" in out.lower()
    try:
        parser.parse_args(["loop", "run", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    run_out = capsys.readouterr().out
    assert "find alpha with DSR > 1.0" not in run_out
    assert "heritage" in run_out.lower()
