from datetime import date
from decimal import Decimal

from app.modules.reconciliation.engine import reconcile
from app.modules.reconciliation.schemas import TransactionInput


def _transaction(
    transaction_id: str,
    *,
    credit: str = "100.00",
    debit: str = "0",
) -> TransactionInput:
    return TransactionInput(
        id=transaction_id,
        transaction_date=date(2026, 10, 20),
        credit_amount=Decimal(credit),
        debit_amount=Decimal(debit),
        references=["INV-100"],
        entity_name="Example Customer",
    )


def test_same_credit_direction_can_be_matched() -> None:
    outcome = reconcile(
        "run-credit",
        [_transaction("bank-1", credit="100.00")],
        [_transaction("ledger-1", credit="100.00")],
    )

    assert outcome.matched_count == 1
    assert outcome.candidates[0].features.direction_agreement == "compatible"


def test_opposite_credit_debit_direction_is_reported_as_exception() -> None:
    outcome = reconcile(
        "run-direction-conflict",
        [_transaction("bank-1", credit="100.00")],
        [_transaction("ledger-1", credit="0", debit="100.00")],
    )

    assert outcome.exception_count == 1
    assert outcome.candidates[0].features.direction_agreement == "incompatible"
    assert "direction_conflict" in outcome.candidates[0].reason_codes
