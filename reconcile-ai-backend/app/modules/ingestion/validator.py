from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

BANK_REQUIRED_COLUMNS = {
    "transaction_reference",
    "transaction_date",
    "description",
    "amount",
}

BANK_ALLOWED_ALIASES = {
    "transaction_reference": {
        "transaction_reference",
        "txn_reference",
        "transaction_id",
        "txn_id",
        "id",
        "utr",
        "cheque_no",
    },
    "transaction_date": {
        "transaction_date",
        "date",
        "txn_date",
        "booking_date",
        "value_date",
        "posting_date",
    },
    "description": {
        "description",
        "narration",
        "details",
        "particulars",
        "remarks",
        "memo",
        "notes",
        "transaction_description",
    },
    "amount": {
        "amount",
        "credit_amount",
        "debit_amount",
        "credit",
        "debit",
        "net_amount",
        "total_amount",
        "total",
        "value",
    },
}

LEDGER_REQUIRED_COLUMNS = {
    "ledger_entry_id",
    "entry_date",
    "amount",
}

LEDGER_ALLOWED_ALIASES = {
    "ledger_entry_id": {
        "ledger_entry_id",
        "entry_id",
        "ledger_id",
        "transaction_id",
        "id",
        "entry_no",
        "entry_number",
        "voucher_no",
        "voucher_number",
        "voucher_id",
        "journal_id",
        "journal_entry_id",
        "ref_id",
        "reference_id",
        "trans_id",
        "doc_id",
        "document_id",
        "invoice_id",
        "invoice_no",
        "invoice_number",
        "bill_id",
        "bill_no",
        "reference",
        "reference_number",
        "ref_no",
        "ref",
    },
    "entry_date": {
        "entry_date",
        "transaction_date",
        "date",
        "posting_date",
        "value_date",
        "booking_date",
        "doc_date",
        "document_date",
        "invoice_date",
        "txn_date",
        "effective_date",
    },
    "amount": {
        "amount",
        "entry_amount",
        "total_amount",
        "net_amount",
        "gross_amount",
        "invoice_amount",
        "credit_amount",
        "debit_amount",
        "credit",
        "debit",
        "total",
        "value",
        "balance",
    },
}


def parse_decimal(raw_value: str | int | float | Decimal, field_name: str) -> Decimal:
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")

    raw = str(raw_value).strip()
    is_negative = False
    if raw.startswith("(") and raw.endswith(")"):
        is_negative = True
        raw = raw[1:-1].strip()
    elif raw.startswith("-"):
        is_negative = True
        raw = raw[1:].strip()
    elif raw.endswith("-"):
        is_negative = True
        raw = raw[:-1].strip()
    elif raw.startswith("+"):
        raw = raw[1:].strip()

    # Strip currency symbols ($, ₹, €, £, Rs., Rs, INR, USD, EUR, etc.), commas, and whitespace
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        raise ValueError(f"{field_name} is required.")

    try:
        val = Decimal(cleaned)
        return -val if is_negative else val
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a valid decimal number.") from exc


def normalize_date(value: str, field_name: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} is required.")

    date_part = raw
    if "T" in raw:
        date_part = raw.split("T")[0].strip()
    elif " " in raw:
        parts = raw.split()
        if ":" in parts[-1]:
            date_part = " ".join(parts[:-1]).strip()

    date_formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y.%m.%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d/%b/%Y",
        "%d/%B/%Y",
        "%Y%m%d",
    )
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_part, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue

    try:
        return date.fromisoformat(date_part).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid date.") from exc


def bank_columns_present(headers: set[str]) -> bool:
    normalized_headers = set(headers)
    return all(
        any(alias in normalized_headers for alias in aliases)
        for aliases in BANK_ALLOWED_ALIASES.values()
    )


def ledger_columns_present(headers: set[str]) -> bool:
    normalized_headers = set(headers)
    for col in LEDGER_REQUIRED_COLUMNS:
        aliases = LEDGER_ALLOWED_ALIASES[col]
        if col == "amount":
            if any(alias in normalized_headers for alias in aliases):
                continue
            if any(c in normalized_headers for c in ("credit", "credit_amount", "debit", "debit_amount")):
                continue
            return False
        if not any(alias in normalized_headers for alias in aliases):
            return False
    return True


def normalize_bank_row(row: dict[str, str], row_index: int = 1) -> dict[str, object]:
    reference = ""
    for alias in (
        "transaction_reference",
        "reference_number",
        "reference",
        "txn_reference",
        "transaction_id",
        "txn_id",
        "ref_no",
        "ref",
        "id",
        "utr",
        "cheque_no",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            reference = str(val).strip()
            break
    transaction_reference = reference or None
    if not reference:
        reference = f"TXN-{row_index:05d}"

    description = ""
    for alias in (
        "description",
        "narration",
        "details",
        "particulars",
        "remarks",
        "memo",
        "notes",
        "transaction_description",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            description = str(val).strip()
            break
    if not description:
        description = reference or "Bank Transaction"

    raw_date = ""
    for alias in (
        "transaction_date",
        "date",
        "txn_date",
        "booking_date",
        "value_date",
        "posting_date",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            raw_date = str(val).strip()
            break
    if not raw_date:
        raise ValueError("transaction_date is required.")
    transaction_date = normalize_date(raw_date, "transaction_date")

    raw_amount = ""
    for alias in ("amount", "entry_amount", "net_amount", "total_amount", "total", "value"):
        val = row.get(alias)
        if val is not None and str(val).strip():
            raw_amount = str(val).strip()
            break

    credit_val = row.get("credit_amount") or row.get("credit") or ""
    debit_val = row.get("debit_amount") or row.get("debit") or ""

    credit = parse_decimal(credit_val, "credit_amount") if str(credit_val).strip() else Decimal("0")
    debit = parse_decimal(debit_val, "debit_amount") if str(debit_val).strip() else Decimal("0")

    if credit and debit:
        raise ValueError("A bank transaction cannot have both credit and debit amounts populated.")

    if not credit and not debit:
        if not raw_amount:
            raise ValueError("amount is required.")
        amount = parse_decimal(raw_amount, "amount")
        credit = amount if amount > 0 else Decimal("0")
        debit = abs(amount) if amount < 0 else Decimal("0")

    counterparty_name = ""
    for alias in (
        "counterparty_name",
        "payer_name",
        "payee_name",
        "party_name",
        "customer_name",
        "beneficiary_name",
        "entity_name",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            counterparty_name = str(val).strip()
            break
    if not counterparty_name:
        counterparty_name = "Unknown"

    payment_reference = ""
    for alias in (
        "payment_reference",
        "payment_ref",
        "reference",
        "reference_number",
        "ref_no",
        "ref",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            payment_reference = str(val).strip()
            break
    
    normalized = {
        "transaction_reference": transaction_reference,
        "transaction_date": transaction_date,
        "description": description,
        "credit_amount": credit,
        "debit_amount": debit,
        "counterparty_name": counterparty_name,
        "payment_reference": payment_reference or None,
    }
    return normalized


def normalize_ledger_row(row: dict[str, str], row_index: int = 1) -> dict[str, object]:
    invoice_id = ""
    for alias in (
        "invoice_id",
        "invoice_no",
        "invoice_number",
        "inv_id",
        "inv_no",
        "bill_id",
        "bill_no",
        "bill_number",
        "document_id",
        "doc_id",
        "doc_no",
        "voucher_no",
        "voucher_id",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            invoice_id = str(val).strip()
            break

    ledger_id = ""
    for alias in (
        "ledger_entry_id",
        "entry_id",
        "ledger_id",
        "transaction_id",
        "id",
        "entry_no",
        "entry_number",
        "voucher_no",
        "voucher_number",
        "voucher_id",
        "journal_id",
        "journal_entry_id",
        "ref_id",
        "reference_id",
        "trans_id",
        "doc_id",
        "document_id",
        "invoice_id",
        "invoice_no",
        "invoice_number",
        "reference",
        "reference_number",
        "ref_no",
        "ref",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            ledger_id = str(val).strip()
            break

    if not ledger_id:
        ledger_id = invoice_id if invoice_id else f"LED-{row_index:05d}"

    raw_date = ""
    for alias in (
        "entry_date",
        "transaction_date",
        "date",
        "posting_date",
        "value_date",
        "booking_date",
        "doc_date",
        "document_date",
        "invoice_date",
        "txn_date",
        "effective_date",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            raw_date = str(val).strip()
            break
    if not raw_date:
        raise ValueError("entry_date is required.")
    entry_date = normalize_date(raw_date, "entry_date")

    raw_amount = ""
    for alias in (
        "amount",
        "entry_amount",
        "total_amount",
        "net_amount",
        "gross_amount",
        "invoice_amount",
        "total",
        "value",
        "balance",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            raw_amount = str(val).strip()
            break

    credit_dec = Decimal("0")
    debit_dec = Decimal("0")
    if not raw_amount:
        credit_val = row.get("credit_amount") or row.get("credit") or ""
        debit_val = row.get("debit_amount") or row.get("debit") or ""
        credit_dec = parse_decimal(credit_val, "credit") if str(credit_val).strip() else Decimal("0")
        debit_dec = parse_decimal(debit_val, "debit") if str(debit_val).strip() else Decimal("0")
        if credit_dec and debit_dec:
            raise ValueError("A ledger entry cannot have both credit and debit amounts populated.")
        if credit_dec != 0 or debit_dec != 0:
            credit_dec = abs(credit_dec)
            debit_dec = abs(debit_dec)
        else:
            raise ValueError("amount is required.")
    else:
        amount = parse_decimal(raw_amount, "amount")
        if amount > 0:
            credit_dec = amount
        elif amount < 0:
            debit_dec = abs(amount)

    payment_reference = ""
    for alias in (
        "payment_reference",
        "payment_ref",
        "reference",
        "reference_number",
        "ref_no",
        "ref",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            payment_reference = str(val).strip()
            break

    description = ""
    for alias in (
        "description",
        "narration",
        "details",
        "particulars",
        "remarks",
        "memo",
        "notes",
        "transaction_description",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            description = str(val).strip()
            break

    if not description:
        description = invoice_id or ledger_id or "Ledger Entry"

    customer_name = ""
    for alias in (
        "customer_name",
        "customer",
        "party_name",
        "party",
        "account_name",
        "account",
        "client_name",
        "client",
        "entity_name",
        "entity",
        "payer_name",
        "payee_name",
        "vendor_name",
        "name",
    ):
        val = row.get(alias)
        if val is not None and str(val).strip():
            customer_name = str(val).strip()
            break
    if not customer_name:
        customer_name = "Unknown"

    customer_id = None
    for alias in ("customer_id", "client_id", "account_id", "party_id"):
        val = row.get(alias)
        if val is not None and str(val).strip():
            try:
                customer_id = int(str(val).strip())
                break
            except ValueError:
                pass

    normalized = {
        "ledger_entry_id": ledger_id,
        "invoice_id": invoice_id or None,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "entry_date": entry_date,
        "description": description,
        "payment_reference": payment_reference or None,
        "credit_amount": credit_dec,
        "debit_amount": debit_dec,
    }
    return normalized
