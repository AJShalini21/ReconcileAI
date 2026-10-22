from decimal import Decimal

from app.modules.ingestion.validator import normalize_bank_row, normalize_ledger_row


def test_generated_bank_display_reference_is_not_matching_evidence() -> None:
    bank = normalize_bank_row(
        {
            "transaction_date": "2026-10-10",
            "description": "Payment received",
            "amount": "100.00",
        },
        row_index=4,
    )

    assert bank["transaction_reference"] is None
    assert bank["description"] == "Payment received"


def test_ledger_description_is_not_treated_as_payment_reference() -> None:
    ledger = normalize_ledger_row(
        {
            "ledger_entry_id": "LED-100",
            "entry_date": "2026-10-10",
            "description": "Monthly subscription",
            "amount": "100.00",
        }
    )

    assert ledger["description"] == "Monthly subscription"
    assert ledger["payment_reference"] is None
    assert ledger["credit_amount"] == Decimal("100.00")
    assert ledger["debit_amount"] == Decimal("0")


def test_ledger_payment_reference_and_debit_direction_are_preserved() -> None:
    ledger = normalize_ledger_row(
        {
            "ledger_entry_id": "LED-101",
            "payment_reference": "PAY-101",
            "entry_date": "2026-10-10",
            "amount": "-100.00",
        }
    )

    assert ledger["payment_reference"] == "PAY-101"
    assert ledger["credit_amount"] == Decimal("0")
    assert ledger["debit_amount"] == Decimal("100.00")


def test_ledger_credit_and_debit_columns_are_normalized() -> None:
    credit = normalize_ledger_row(
        {
            "ledger_entry_id": "LED-102",
            "entry_date": "2026-10-10",
            "credit_amount": "75.00",
        }
    )
    debit = normalize_ledger_row(
        {
            "ledger_entry_id": "LED-103",
            "entry_date": "2026-10-10",
            "debit_amount": "25.00",
        }
    )

    assert credit["credit_amount"] == Decimal("75.00")
    assert credit["debit_amount"] == Decimal("0")
    assert debit["credit_amount"] == Decimal("0")
    assert debit["debit_amount"] == Decimal("25.00")
