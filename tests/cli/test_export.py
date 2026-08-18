from __future__ import annotations

import json

from alphaloop.cli.main import create_parser, main


def test_export_help_is_phase1_placeholder():
    parser = create_parser()
    command_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    export_help = next(
        choice.help
        for choice in command_action._choices_actions
        if choice.dest == "export"
    )
    assert "placeholder" in export_help.lower()
    assert "not an immutable" in export_help.lower()


def test_export_writes_placeholder_marker(tmp_path):
    out = tmp_path / "strategy.asb"
    rc = main(
        [
            "export",
            "c1",
            "--outcome",
            "FOUND",
            "--candidate-ids",
            "c1",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["placeholder"] is True


def test_export_without_found_returns_nonzero(tmp_path, capsys):
    rc = main(
        [
            "export",
            "c1",
            "--outcome",
            "NO_EVIDENCE",
            "--candidate-ids",
            "c1",
            "--output",
            str(tmp_path / "strategy.asb"),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "FOUND" in err
