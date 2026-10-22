from datetime import date
from decimal import Decimal

from app.modules.reconciliation.engine import reconcile
from app.modules.reconciliation.schemas import TransactionInput


def transaction(
    transaction_id: str,
    *,
    amount: str = "100.00",
    reference: str | None = None,
    name: str | None = "Acme",
    direction: str = "unknown",
) -> TransactionInput:
    return TransactionInput(
        id=transaction_id,
        transaction_date=date(2026, 10, 10),
        amount=Decimal(amount),
        references=[reference] if reference else [],
        entity_name=name,
        direction=direction,
    )


def test_exact_reference_and_amount_match_in_strict_round() -> None:
    outcome = reconcile(
        "run-1",
        [transaction("bank-1", reference="INV-100", direction="credit")],
        [
            transaction(
                "ledger-1",
                reference="INV-100",
                direction="credit",
            )
        ],
    )

    assert outcome.matched_count == 1
    assert outcome.candidates[0].matching_round == 1
    assert outcome.transactions[0].disposition == "matched"


def test_duplicate_exact_reference_blocks_strict_matching() -> None:
    outcome = reconcile(
        "run-duplicate-reference",
        [transaction("bank-1", reference="INV-100", direction="credit")],
        [
            transaction("ledger-1", reference="INV-100", direction="credit"),
            transaction(
                "ledger-2",
                amount="90.00",
                reference="INV-100",
                direction="credit",
            ),
        ],
    )

    assert outcome.matched_count == 1
    matched = next(candidate for candidate in outcome.candidates if candidate.disposition == "matched")
    assert matched.matching_round == 2
    assert outcome.exception_count == 1


def test_amount_mismatch_with_matching_reference_is_retained_as_exception() -> None:
    outcome = reconcile(
        "run-2",
        [transaction("bank-1", reference="INV-100")],
        [transaction("ledger-1", amount="90.00", reference="INV-100")],
    )

    assert outcome.exception_count == 1
    assert outcome.candidates[0].disposition == "exception"
    assert "amount_mismatch" in outcome.candidates[0].reason_codes


def test_missing_references_can_match_using_combined_evidence() -> None:
    outcome = reconcile(
        "run-3",
        [transaction("bank-1")],
        [transaction("ledger-1")],
    )

    assert outcome.matched_count == 1
    assert outcome.candidates[0].features.reference_agreement == "missing"
    assert outcome.candidates[0].scoring_policy == "reference-free"
    assert outcome.candidates[0].matching_round == 2


def test_direction_conflict_blocks_automatic_matching() -> None:
    outcome = reconcile(
        "run-4",
        [transaction("bank-1", reference="INV-100", direction="credit")],
        [transaction("ledger-1", reference="INV-100", direction="debit")],
    )

    assert outcome.matched_count == 0
    assert outcome.exception_count == 1
    assert "direction_conflict" in outcome.candidates[0].reason_codes


def test_equal_candidates_remain_pending_review_when_score_margin_is_tied() -> None:
    outcome = reconcile(
        "run-5",
        [transaction("bank-1")],
        [transaction("ledger-1"), transaction("ledger-2")],
    )

    assert outcome.matched_count == 0
    assert outcome.pending_review_count == 2
    assert all(item.disposition == "pending_review" for item in outcome.candidates)


def test_entity_candidate_generation_handles_common_name_abbreviations() -> None:
    outcome = reconcile(
        "run-6",
        [transaction("bank-1", amount="101.00", name="Acme Corporation")],
        [transaction("ledger-1", amount="100.00", name="Acme Corp")],
    )

    assert len(outcome.candidates) == 1
    assert "entity" in outcome.candidates[0].candidate_sources

