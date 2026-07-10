"""
Integration tests for the OpenBB data source.

These tests would hit the real OpenBB API. Run with:

    OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v

**Status (v1.1.2): OpenBBSource is not yet importable from
`openstrategy.data`. The source file exists at
`src/openstrategy/data/openbb_source.py` but is not exported in
`__init__.py`. These tests are placeholders for v1.1.3 / v2.0
when OpenBBSource is wired in.

If you see these tests fail with "cannot import name 'OpenBBSource'",
that is the expected state at v1.1.2 — they are documented gaps, not
regressions. See the v1.1 路线图 for the planned fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Mark all tests in this file as integration (gated by conftest).
# Run with: OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v
pytestmark = pytest.mark.integration


def test_openbb_source_is_importable():
    """OpenBBSource should be importable from openstrategy.data.

    At v1.1.2, this import is expected to fail. The test is
    marked xfail so the run shows the expected state.
    """
    try:
        from openstrategy.data import OpenBBSource  # noqa: F401
    except ImportError:
        pytest.xfail(
            "OpenBBSource not yet wired in `openstrategy.data.__init__` "
            "(v1.1.2 known gap, see v1.1 路线图)"
        )


def test_openbb_real_network_placeholder():
    """Real-network test placeholder. Will be implemented when
    OpenBBSource is importable."""
    pytest.xfail("OpenBBSource not yet wired (v1.1.2 known gap)")
