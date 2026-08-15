"""
alphaloop.judge — infrastructure package for the LLM-as-judge evaluator (v0.6).

This package is an *implementation detail* of the public diagnostic
`alphaloop.diagnostic.llm_judge()`. It holds:

- `client.py` — thin OpenAI-compatible HTTP client (env-var aware, with
  retries on 429/5xx and exponential backoff).
- `prompts.py` — YAML prompt loader + template render (`{report_markdown}`
  substitution). Backward-compatible with the bundled YAML; also accepts
  a flat-format override for tests.
- `types.py` — dataclasses for I/O (`DimensionScore`, `LLMJudgeResult`,
  `RawCompletion`, `LLMConfig`).

Resolution order for LLM connection settings (highest priority first):

1. CLI flag (`--judge-model`, `--judge-api-key`, `--judge-base-url`) on
   `alphaloop report`.
2. Environment variables (`LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`).
3. YAML fallback file (opt-in, path from `LLM_JUDGE_CONFIG` env var).

If none of the above provide a usable configuration, the judge is
SKIPPED (no exception is raised at the diagnostic layer).

The package is not re-exported from the top-level `alphaloop` package;
callers should use `alphaloop.diagnostic.llm_judge`.
"""
from .client import LLMClient, LLMJudgeClient, LLMConfig
from .prompts import render_prompt, PROMPT_TEMPLATE, DEFAULT_PROMPT_PATH
from .types import DimensionScore, LLMJudgeResult, RawCompletion

__all__ = [
    # types
    "DimensionScore",
    "LLMJudgeResult",
    "RawCompletion",
    "LLMConfig",
    # prompts
    "render_prompt",
    "PROMPT_TEMPLATE",
    "DEFAULT_PROMPT_PATH",
    # client
    "LLMClient",
    "LLMJudgeClient",
]