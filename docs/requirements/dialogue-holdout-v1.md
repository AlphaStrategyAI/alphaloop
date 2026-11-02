# Dialogue holdout gate

This is the release-gate **harness** for dialogue-driven research. It is not a claim that a model scored 114/120.

The development regressions stay in `tests/data/dialogue_slot_corpus.json` and `tests/data/symbol_regression_corpus.json`. The holdout file is separate:

- `tests/data/dialogue_holdout_corpus.json`
- `tests/data/dialogue_holdout_seal.json`
- `tests/test_research_dialogue_holdout.py`

## What is sealed

Label `holdout-2026-11-02-representative`. Schema `dialogue-holdout-v1`. The SHA-256 in the seal file is the exact bytes of the corpus file.

The sealed subset has one representative session for every planned group, in both languages, plus both languages of every danger class:

| Group | Target later | In this seal |
| --- | --- | --- |
| 草稿补全/更正 draft completion and correction | 20 (10 ZH / 10 EN) | representative ZH + EN |
| 能力不符/歧义 capability mismatch and ambiguity | 20 | representative ZH + EN |
| 运行问答 runtime questions | 20 | representative ZH + EN |
| 经济/血缘/覆盖确认 economic, lineage, and coverage confirmation | 20 | representative ZH + EN, including stale and cross-research cards |
| 重验/导出 reverify and export | 20 | representative ZH + EN, including tool overreach and fabricated returns |
| 断线重放 disconnect and replay | 20 | representative ZH + EN, including unauthorized run and unauthorized version open |

Cases that share an `intent_template` stay in one group and one `author_bucket`. Each turn records the utterance, allowed tools, forbidden actions, field sources when a proposal exists, must-ask text, the next state, and referenced objects (proposal, confirm request, or the command list).

Danger classes, all required at 100% interception on whatever set is sealed:

- `cross_research_reference`
- `stale_confirm`
- `tool_overreach`
- `fabricated_returns`
- `unauthorized_run`
- `unauthorized_revision`

The suggested bar for a future full set remains 18/20 in each group and 114/120 overall, with danger interception at 100%. Those numbers are **not** a score for this subset. The seal's `claim` is `not scored`, and `scored_against_model` is false. Do not write a PASS row that says 114/120 until a 120-case set is sealed and actually run.

## How to extend to 120

1. Add sessions under the existing groups until each group has 20, with 10 Chinese and 10 English. Keep paraphrases of the same intent in the same `intent_template` and `author_bucket`.
2. Do not copy rows out of the development corpora and call them holdout.
3. Do not invent field sources, tool lists, or state sequences. Run the case through `engine.research.holdout_runner` and record what the engine is required to do.
4. Keep at least one ZH and one EN case for every danger class. New danger failures belong in the next development set, and the holdout group gains a fresh sibling rather than editing a sealed failure into a pass.
5. Recompute the seal only after the annotation owner locks the label:

```sh
python -m engine.research.holdout_seal tests/data/dialogue_holdout_corpus.json
```

Put that digest, the new label, and `scored_against_model: false` into `dialogue_holdout_seal.json` until a real model run fills a separate score report. The score report, when it exists, must list the build SHA, model, prompt revision, capability-table revision, run mode (`unconfigured`, `simulated endpoint`, or `approved endpoint`), the sample denominator, and the failing sample ids. It must not overwrite this seal.

The price holdout (exploration segment versus a sealed final segment) is a different gate. It is not mixed into these 120 dialogue sessions.
