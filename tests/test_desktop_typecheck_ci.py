import json
from pathlib import Path


def test_desktop_package_has_typecheck_script() -> None:
    pkg = json.loads(Path("apps/desktop/package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    assert scripts.get("typecheck") == "tsc --noEmit"
    assert "tsc --noEmit" in scripts.get("build", "")


def test_ci_workflow_runs_desktop_typecheck() -> None:
    workflow = Path(".github/workflows/desktop-typecheck.yml").read_text(encoding="utf-8")
    assert "npm run typecheck" in workflow
    assert "npm run build" in workflow
