from __future__ import annotations

from alphaloop.cli.main import main


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
