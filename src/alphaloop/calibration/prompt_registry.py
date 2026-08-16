"""Prompt version registry for v0.8 (PRD § 2 R-Prompt, Stories 11–12).

The registry tracks every shipped judge-prompt version under a stable
identifier (e.g. ``v0.6.0-prompt-1``, ``v0.8.0-prompt-2``) and lets
callers:

- ``get_prompt(version)`` → return the YAML template for a version.
- ``list_versions()`` → all registered versions, alphabetical.
- ``register_version(version, template)`` → add a new version at
  runtime (test fixture / A/B experiment).
- ``compare_prompts(version_a, version_b)`` → return a side-by-side
  dict suitable for ``alphaloop judge --calibrate-prompt``.

Resolution order at runtime (PRD Story 11):

1. Explicit ``--judge-prompt-version`` flag → ``ALPHALOOP_JUDGE_PROMPT_VERSION`` env var.
2. The "latest" sentinel → the lexicographically-last registered version.
3. ``"v0.8.0-prompt-2"`` (the v0.8 default).

Backward compatibility (PRD § 5.2): ``v0.6.0-prompt-1`` MUST remain
in the registry so v0.7 users can roll back via the env var.

The registry is a process-global dict; tests can call
``register_version(...)`` to inject new versions. The shipped versions
ship in this module as the source of truth.
"""
from __future__ import annotations

import os
from typing import Optional

# Default version used when nothing is specified.
DEFAULT_PROMPT_VERSION = "v0.8.0-prompt-2"

# Env var name (PRD Story 11 / § 5.2).
PROMPT_VERSION_ENV_VAR = "ALPHALOOP_JUDGE_PROMPT_VERSION"

# The "latest" sentinel → resolve to the lex-last registered version.
LATEST_SENTINEL = "latest"


# ---------------------------------------------------------------------------
# Bundled prompt templates (PRD § 5.7 — backward compat for v0.6)
# ---------------------------------------------------------------------------


# v0.6 prompt — verbatim copy of src/alphaloop/judge/prompts.py::PROMPT_TEMPLATE.
# We intentionally keep it here so the registry can resolve to it without
# importing judge.prompts (which would create a circular import during
# judge.prompts initialization).
_V0_6_0_PROMPT_1 = """\
system: |
  You are an honest, strict reviewer of quantitative trading backtest
  reports. Your job is to score the report on THREE independent
  dimensions, each on a 1-10 scale. You are not evaluating whether
  the strategy is good — other tools do that. You are evaluating the
  QUALITY OF THE REPORT ITSELF: is it clear, is the investment thesis
  sound, and are the risks honestly disclosed?

  You must respond with a single JSON object, nothing else. No
  prose, no markdown fences, no commentary. The JSON schema is:

  {
    "readability": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    },
    "decision_quality": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    },
    "risk_disclosure": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    }
  }

  Scoring rubric (apply per dimension):

  Readability (1-10):
    1-3: Incoherent, jargon-heavy, or missing sections.
    4-6: Understandable but unclear on either the setup, the results,
         or the implications.
    7-8: Clear, well-organized, a non-quant could follow the main thread.
    9-10: Excellent — figures, tables, and callouts make the report
          skim-readable in <5 minutes.

  Decision quality (1-10):
    1-3: The investment thesis is missing, contradicts itself, or
         describes a curve-fit.
    4-6: Thesis is present but only weakly supported by the data shown.
    7-8: Thesis is internally consistent and the data supports it
         (or honestly explains where it doesn't).
    9-10: Thesis is crisp, the alpha source is named, regime
          dependencies are explicit, and the report explains when
          the strategy SHOULD NOT be traded.

  Risk disclosure (1-10):
    1-3: No mention of max drawdown, tail risk, transaction costs,
         capacity, look-ahead bias, or survivorship bias.
    4-6: Mentions some risks but omits at least one critical category.
    7-8: Discloses drawdown, costs, and capacity; mentions
         look-ahead / survivorship as caveats.
    9-10: Comprehensive — includes regime fragility, parameter
          sensitivity, and an explicit "do not trade if X" list.

user: |
  Below is the backtest report to evaluate. Score it honestly on the
  three dimensions above. Cite specific text from the report in your
  evidence field — do not invent quotes.

  <report>
  {report_markdown}
  </report>
"""


# v0.8 prompt — a small calibration-driven refinement. For v0.8 the
# shipped v0.8.0-prompt-2 is identical to v0.6.0-prompt-1 (calibration
# did not reveal a rubric gap that required editing); the registry
# entry exists so future prompt iterations (A/B via
# ``--calibrate-prompt``) have a stable home, and so the
# ``compare_prompts`` side-by-side can be exercised even when the two
# prompts are equal.
_V0_8_0_PROMPT_2 = _V0_6_0_PROMPT_1


# ---------------------------------------------------------------------------
# Registry (process-global)
# ---------------------------------------------------------------------------


class PromptRegistry:
    """Process-global dict of version → YAML template."""

    def __init__(self) -> None:
        self._versions: dict[str, str] = {}

    # ---- core ops ---------------------------------------------------

    def register(self, version: str, template: str) -> None:
        """Add or replace a version. Empty/whitespace versions rejected."""
        v = (version or "").strip()
        if not v:
            raise ValueError("version must be a non-empty string")
        if not isinstance(template, str) or not template.strip():
            raise ValueError(f"template for {v!r} must be a non-empty string")
        self._versions[v] = template

    def unregister(self, version: str) -> None:
        """Remove a version. Silent if not present."""
        self._versions.pop(version, None)

    def get(self, version: str) -> str:
        """Return the template for ``version``. Raises KeyError if missing."""
        if version == LATEST_SENTINEL:
            if not self._versions:
                raise KeyError("prompt registry is empty")
            v = max(self._versions.keys())
            return self._versions[v]
        if version not in self._versions:
            raise KeyError(
                f"unknown prompt version {version!r}; "
                f"registered: {sorted(self._versions.keys())}"
            )
        return self._versions[version]

    def list_versions(self) -> list[str]:
        """Return all registered versions, sorted."""
        return sorted(self._versions.keys())

    def has(self, version: str) -> bool:
        return version in self._versions

    def clear(self) -> None:
        self._versions.clear()

    # ---- bulk -------------------------------------------------------

    def register_many(self, mapping: dict[str, str]) -> None:
        for v, t in mapping.items():
            self.register(v, t)


# Module-level singleton. Tests can mutate it freely; the shipped
# entries are re-applied by ``_install_defaults()`` at import time.
_REGISTRY = PromptRegistry()


def _install_defaults() -> None:
    """Register the shipped prompt versions."""
    _REGISTRY.register("v0.6.0-prompt-1", _V0_6_0_PROMPT_1)
    _REGISTRY.register("v0.8.0-prompt-2", _V0_8_0_PROMPT_2)


_install_defaults()


# ---------------------------------------------------------------------------
# Public helpers (Story 11 + Story 12)
# ---------------------------------------------------------------------------


def get_prompt(version: Optional[str] = None) -> str:
    """Resolve a prompt template by version.

    Resolution order:

    1. ``version`` arg (if non-empty).
    2. ``ALPHALOOP_JUDGE_PROMPT_VERSION`` env var.
    3. ``"latest"`` (lex-last registered version).

    Raises KeyError if the resolved version is not registered.
    """
    chosen = (version or "").strip() or os.environ.get(PROMPT_VERSION_ENV_VAR, "").strip()
    if not chosen:
        chosen = LATEST_SENTINEL
    return _REGISTRY.get(chosen)


def list_versions() -> list[str]:
    """Return all registered prompt versions, sorted."""
    return _REGISTRY.list_versions()


def register_version(version: str, template: str) -> None:
    """Add or replace a prompt version at runtime (test fixture, A/B)."""
    _REGISTRY.register(version, template)


def unregister_version(version: str) -> None:
    """Remove a registered prompt version (test cleanup)."""
    _REGISTRY.unregister(version)


def resolve_version(
    *,
    flag_version: Optional[str] = None,
    env_version: Optional[str] = None,
) -> str:
    """Resolve which version *name* to render — separate from get_prompt().

    Useful when the caller wants to record the version name in a
    calibration report without rendering the template. Same
    resolution order as ``get_prompt`` but returns the version
    identifier instead of the template.
    """
    chosen = (
        (flag_version or "").strip()
        or (env_version or "").strip()
        or os.environ.get(PROMPT_VERSION_ENV_VAR, "").strip()
    )
    if not chosen or chosen == LATEST_SENTINEL:
        # Default = lex-last registered version (v0.8.0-prompt-2 today).
        if not _REGISTRY._versions:
            return LATEST_SENTINEL
        return max(_REGISTRY._versions.keys())
    return chosen


# ---------------------------------------------------------------------------
# A/B comparison (Story 12)
# ---------------------------------------------------------------------------


def compare_prompts(
    version_a: str,
    version_b: str,
    *,
    metrics_a: Optional[dict] = None,
    metrics_b: Optional[dict] = None,
) -> dict:
    """Build a side-by-side comparison of two prompt versions.

    Returns a dict with:

    - ``version_a`` / ``version_b``: the version names.
    - ``template_diff_lines``: a list of line-level differences
      (``unified-diff``-style — for human eyeballs).
    - ``metrics_a`` / ``metrics_b``: optional dicts (e.g. from
      a calibration run).
    - ``winners``: per-dimension winner based on
      ``pearson_r`` (higher is better), if metrics provided.
    - ``length_a_chars`` / ``length_b_chars``: rough size proxy.
    """
    template_a = _REGISTRY.get(version_a)
    template_b = _REGISTRY.get(version_b)
    diff_lines = _simple_unified_diff(
        template_a.splitlines(),
        template_b.splitlines(),
        fromfile=version_a,
        tofile=version_b,
    )
    out = {
        "version_a": version_a,
        "version_b": version_b,
        "template_diff_lines": diff_lines,
        "length_a_chars": len(template_a),
        "length_b_chars": len(template_b),
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
    }
    if metrics_a and metrics_b:
        out["winners"] = _winner_per_dim(metrics_a, metrics_b)
    return out


def _simple_unified_diff(
    a: list[str],
    b: list[str],
    *,
    fromfile: str,
    tofile: str,
) -> list[str]:
    """Minimal unified diff (no third-party deps).

    Output is a list of ``"--- a"``, ``"+++ b"``, ``"@@ ..."``, ``" ..."``
    lines. Not a full Myers diff — just an informative side-by-side for
    reviewers.
    """
    out: list[str] = [f"--- {fromfile}", f"+++ {tofile}"]
    # Longest-common-prefix / suffix not computed (small prompts, eyeball
    # diff is fine). Walk both lists, mark changes inline.
    n = max(len(a), len(b))
    for i in range(n):
        a_line = a[i] if i < len(a) else None
        b_line = b[i] if i < len(b) else None
        if a_line == b_line:
            out.append(f"  {a_line}")
        else:
            if a_line is not None:
                out.append(f"- {a_line}")
            if b_line is not None:
                out.append(f"+ {b_line}")
    return out


def _winner_per_dim(
    metrics_a: dict[str, dict],
    metrics_b: dict[str, dict],
) -> dict[str, str]:
    """Pick a winner per dim based on pearson_r (higher is better)."""
    out: dict[str, str] = {}
    for dim, ma in metrics_a.items():
        mb = metrics_b.get(dim)
        if not mb:
            out[dim] = "A"
            continue
        a_r = float(ma.get("pearson_r", 0.0))
        b_r = float(mb.get("pearson_r", 0.0))
        if b_r > a_r:
            out[dim] = "B"
        elif a_r > b_r:
            out[dim] = "A"
        else:
            out[dim] = "tie"
    return out