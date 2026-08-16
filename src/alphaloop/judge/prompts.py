"""
Prompt loader + template render for the LLM-as-judge evaluator.

The combined system + user prompt asks for 3 dimension scores in a
single call (cheaper, more consistent than 3 separate calls).

Resolution order (highest priority first):

1. Inline prompt template (parameter to `render_prompt`).
2. YAML fallback file from `LLM_JUDGE_CONFIG` env var.
3. Bundled default (a YAML-formatted string below, parsed once at
   import time).

The bundled default matches the system + user rubric described in
`docs/design/v06-llm-judge.md` § 3.2 verbatim. Tests can override any
of the three sources.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# v0.8 calibration integration (PRD § 2 Story 11): the bundled
# default PROMPT_TEMPLATE is still the v0.6 prompt, but the registry
# (alphaloop.calibration.prompt_registry) ships v0.8.0-prompt-2 as
# the default. The lazy import here avoids a circular import at
# module load time.

# Bundled default prompt template. This is the YAML the design doc
# describes; loaded at import time and re-parsed on every call (so the
# default can be patched by tests via `LLM_JUDGE_CONFIG`).
DEFAULT_PROMPT_PATH: Optional[Path] = None

PROMPT_TEMPLATE: str = """\
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


# ---------------------------------------------------------------------------
# Minimal YAML parser (no PyYAML dependency)
# ---------------------------------------------------------------------------


def _yaml_load(text: str) -> dict:
    """Parse a tiny YAML subset (top-level `system: |` and `user: |` blocks).

    We deliberately do NOT use PyYAML — alphaloop keeps its dependency
    footprint minimal, and the bundled prompt template is small enough
    to parse by hand. Supports:

    - Two top-level keys (`system`, `user`), each with a `|` literal-block
      scalar. The block continues on subsequent indented lines.
    - Whitespace and `#` comments are stripped from block content but
      blank lines are preserved.

    Raises ValueError on malformed YAML (missing colon, unknown key,
    unterminated block, etc.).
    """
    if not isinstance(text, str):
        raise ValueError("prompt YAML must be a string")

    result: dict = {}
    current_key: Optional[str] = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        # Strip trailing comments outside of literal blocks is hard;
        # literal blocks keep `#` verbatim (they could appear in prompts).
        line = raw_line.rstrip()

        if current_key is None:
            # Looking for the next top-level key.
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                raise ValueError(
                    f"malformed YAML in prompt template: expected 'key: |', "
                    f"got {line!r}"
                )
            key, _, marker = stripped.partition(":")
            key = key.strip()
            marker = marker.strip()
            if marker not in ("|",):
                raise ValueError(
                    f"only '|' literal blocks are supported for key {key!r}; "
                    f"got marker {marker!r}"
                )
            current_key = key
            current_lines = []
            continue

        # Inside a block: lines starting with whitespace are content;
        # blank lines are preserved; a line with no leading whitespace
        # that contains a `:` marks the start of the next key.
        if line.startswith(" ") or line.startswith("\t") or line == "":
            # Preserve the line as-is minus the leading indent.
            if line:
                current_lines.append(line.lstrip())
            else:
                current_lines.append("")
            continue

        # Un-indented non-empty line: end of current block.
        result[current_key] = "\n".join(current_lines).rstrip("\n")
        current_key = None
        current_lines = []

        # Now re-process this line as a new top-level key.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(
                f"malformed YAML in prompt template: expected 'key: |', "
                f"got {line!r}"
            )
        new_key, _, marker = stripped.partition(":")
        new_key = new_key.strip()
        marker = marker.strip()
        if marker not in ("|",):
            raise ValueError(
                f"only '|' literal blocks are supported for key {new_key!r}; "
                f"got marker {marker!r}"
            )
        current_key = new_key
        current_lines = []

    # Flush trailing block.
    if current_key is not None:
        result[current_key] = "\n".join(current_lines).rstrip("\n")

    if not result:
        raise ValueError("prompt YAML is empty")

    return result


def _resolve_template(
    inline: Optional[str],
    yaml_path: Optional[str],
    env_path_var: str = "LLM_JUDGE_CONFIG",
    *,
    prompt_version: Optional[str] = None,
) -> str:
    """Pick the prompt template per resolution order.

    Order (highest priority first):

    1. ``inline`` parameter (explicit template — used by tests).
    2. ``yaml_path`` / ``LLM_JUDGE_CONFIG`` env var (file on disk).
    3. v0.8 registry (alphaloop.calibration.prompt_registry), using
       ``prompt_version`` (default ``"latest"``) or
       ``ALPHALOOP_JUDGE_PROMPT_VERSION``.
    4. Bundled ``PROMPT_TEMPLATE`` (the v0.6 default).
    """
    if inline is not None:
        return inline
    path_str = yaml_path or os.environ.get(env_path_var)
    if path_str:
        path = Path(path_str)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            raise IOError(
                f"could not read LLM judge prompt YAML at {path}: {e}"
            ) from e
    # v0.8: registry lookup.
    try:
        from alphaloop.calibration.prompt_registry import get_prompt
        return get_prompt(version=prompt_version)
    except (KeyError, ImportError):
        return PROMPT_TEMPLATE


def load_prompt(version: str = "latest") -> str:
    """Return a registered prompt template by version (v0.8, Story 11).

    Resolution: ``"latest"`` → lex-last registered version
    (today ``v0.8.0-prompt-2``); explicit version name → that
    version. Raises KeyError if the version is unknown.

    Backward compatible with v0.6 — falls back to the bundled
    ``PROMPT_TEMPLATE`` (``v0.6.0-prompt-1``) if the registry is
    empty.
    """
    from alphaloop.calibration.prompt_registry import get_prompt
    try:
        return get_prompt(version=version)
    except (KeyError, ImportError):
        return PROMPT_TEMPLATE


def render_prompt(
    report_markdown: str,
    *,
    inline_template: Optional[str] = None,
    yaml_path: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> list[dict]:
    """Render the judge prompt as a chat-messages list.

    Args:
        report_markdown: The full backtest report to embed in the user
            message. Will be wrapped in `<report>...</report>` tags by
            the bundled template; pass verbatim text otherwise.
        inline_template: Optional inline YAML to use instead of the
            bundled default. Useful in tests.
        yaml_path: Optional path to a YAML file to load. If not given,
            uses `LLM_JUDGE_CONFIG` env var; falls back to the bundled
            default.

    Returns:
        A list of two dicts: `[{"role": "system", "content": ...},
        {"role": "user", "content": ...}]`. The user message has
        `{report_markdown}` substituted.

    Raises:
        ValueError: if the resolved YAML is missing required keys
            (`system`, `user`) or is malformed.
        IOError: if `yaml_path` is set but cannot be read.
    """
    template = _resolve_template(inline_template, yaml_path, prompt_version=prompt_version)
    parsed = _yaml_load(template)

    system = parsed.get("system")
    user_block = parsed.get("user")
    if system is None or user_block is None:
        raise ValueError(
            "prompt YAML must contain both 'system' and 'user' keys"
        )

    # Substitute the report into the user block. The bundled template
    # uses the placeholder `{report_markdown}`; custom templates must
    # use the same placeholder or no substitution happens.
    if "{report_markdown}" in user_block:
        user_content = user_block.replace("{report_markdown}", report_markdown)
    else:
        user_content = user_block

    return [
        {"role": "system", "content": str(system)},
        {"role": "user", "content": user_content},
    ]