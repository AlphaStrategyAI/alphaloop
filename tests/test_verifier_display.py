from types import SimpleNamespace

from engine.research.data_window import _failed_gate_ids
from engine.research.methods import format_verifier_ids
from engine.verifiers import VerifierResult, VerificationReport


def test_format_verifier_ids_dedupes_and_labels() -> None:
    formatted = format_verifier_ids(
        ("scorecard.market", "pit.consistency", "scorecard.market")
    )
    assert formatted == (
        "市场计分卡 (scorecard.market)",
        "时点一致性 (pit.consistency)",
    )


def test_failed_gate_ids_deduped_in_late_pass_helper() -> None:
    verification = VerificationReport(
        (
            VerifierResult("scorecard.market", "v1", False, {}, "fail"),
            VerifierResult("scorecard.market", "v1", False, {}, "fail"),
        )
    )
    round_ = SimpleNamespace(
        accepted_attempt=SimpleNamespace(verification=verification),
    )
    assert _failed_gate_ids(round_) == ("市场计分卡 (scorecard.market)",)
