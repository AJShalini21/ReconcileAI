from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from decimal import Decimal
from itertools import product

from app.ml.inference import compute_entity_similarity
from app.modules.reconciliation.schemas import (
    CandidateDecision,
    CandidateFeatures,
    ReconciliationConfig,
    ReconciliationOutcome,
    TransactionInput,
    TransactionDecision,
)

_REFERENCE_NORMALIZER = re.compile(r"[^A-Z0-9]")
_NAME_NORMALIZER = re.compile(r"[^a-z0-9]+")


def _normalized_reference(value: str) -> str:
    print(f"Normalizing reference: {value}")
    return _REFERENCE_NORMALIZER.sub("", value.upper())


def _normalized_name(value: str | None) -> str:
    print(f"Normalizing name: {value}")
    if not value or value.strip().lower() in {"unknown", "n/a", "na"}:
        return ""
    return " ".join(_NAME_NORMALIZER.sub(" ", value.lower()).split())


def _references(transaction: TransactionInput) -> set[str]:
    print(f"Extracting references from transaction: {transaction.id}")
    return {
        normalized
        for value in transaction.references
        if (normalized := _normalized_reference(value))
    }


def _reference_agreement(
    bank_references: set[str], ledger_references: set[str]
) -> str:
    print(f"Comparing bank references {bank_references} with ledger references {ledger_references}")
    if not bank_references or not ledger_references:
        return "missing"
    if bank_references & ledger_references:
        return "exact"
    if any(
        left in right or right in left
        for left, right in product(bank_references, ledger_references)
    ):
        return "partial"
    return "conflicting"


def _name_similarity(left: str | None, right: str | None) -> float | None:
    print(f"Calculating name similarity between '{left}' and '{right}'")
    normalized_left = _normalized_name(left)
    normalized_right = _normalized_name(right)
    if not normalized_left or not normalized_right:
        return None
    left_tokens = normalized_left.split()
    right_tokens = normalized_right.split()
    token_similarity = sum(
        max(SequenceMatcher(None, left_token, right_token).ratio() for right_token in right_tokens)
        for left_token in left_tokens
    ) + sum(
        max(SequenceMatcher(None, right_token, left_token).ratio() for left_token in left_tokens)
        for right_token in right_tokens
    )
    token_similarity /= len(left_tokens) + len(right_tokens)
    return round(
        max(SequenceMatcher(None, normalized_left, normalized_right).ratio(), token_similarity),
        4,
    )


def _date_difference(left: date, right: date) -> int:
    print(f"Calculating date difference between {left} and {right}")
    return abs((left - right).days)


# def _transaction_direction(transaction: TransactionInput) -> str:
#     print(f"Determining transaction direction for transaction: {transaction.id}")
#     credit = transaction.credit_amount or Decimal("0")
#     debit = transaction.debit_amount or Decimal("0")
#     if credit > 0 and debit == 0:
#         return "credit"
#     if debit > 0 and credit == 0:
#         return "debit"
#     return "unknown"



def _candidate_pairs(
    bank_transactions: list[TransactionInput],
    ledger_entries: list[TransactionInput],
    config: ReconciliationConfig,
) -> dict[tuple[str, str], set[str]]:
    candidates: dict[tuple[str, str], set[str]] = defaultdict(set)

    ledger_by_reference: dict[str, list[TransactionInput]] = defaultdict(list)
    ledger_by_amount_currency: dict[
        tuple[Decimal, Decimal], list[TransactionInput]
    ] = defaultdict(list)
    ledger_by_token: dict[str, list[TransactionInput]] = defaultdict(list)

    for ledger in ledger_entries:
        for reference in _references(ledger):
            ledger_by_reference[reference].append(ledger)

        amount_key = (
            ledger.credit_amount or Decimal("0"),
            ledger.debit_amount or Decimal("0"),
        )
        ledger_by_amount_currency[amount_key].append(ledger)

        for token in set(_normalized_name(ledger.entity_name).split()):
            ledger_by_token[token].append(ledger)

    for bank in bank_transactions:
        bank_references = _references(bank)

        # 1. Reference-based candidates
        for ledger_reference, entries in ledger_by_reference.items():
            reference_matches = any(
                bank_reference == ledger_reference
                or bank_reference in ledger_reference
                or ledger_reference in bank_reference
                for bank_reference in bank_references
            )

            if not reference_matches:
                continue

            for ledger in entries:
                if (_date_difference(
                        bank.transaction_date,
                        ledger.transaction_date,
                    ) > config.date_window_days
                ):
                    continue

                candidates[(bank.id, ledger.id)].add("reference")

        # 2. Exact credit/debit amount and date candidates
        amount_key = (
            bank.credit_amount or Decimal("0"),
            bank.debit_amount or Decimal("0"),
        )

        for ledger in ledger_by_amount_currency.get(amount_key, []):
            if _date_difference(
                bank.transaction_date,
                ledger.transaction_date,
            ) <= config.date_window_days:
                candidates[(bank.id, ledger.id)].add("amount_date")

        # 3. Entity-based candidates
        bank_name = _normalized_name(bank.entity_name)

        if not bank_name:
            continue

        possible_entries: dict[str, TransactionInput] = {}

        for token in set(bank_name.split()):
            for ledger in ledger_by_token.get(token, []):
                if (_date_difference(
                        bank.transaction_date,
                        ledger.transaction_date,
                    ) <= config.date_window_days
                ):
                    possible_entries[ledger.id] = ledger

        for ledger in possible_entries.values():
            similarity = _name_similarity(
                bank.entity_name,
                ledger.entity_name,
            )

            if (
                similarity is not None
                and similarity >= config.entity_candidate_threshold
            ):
                candidates[(bank.id, ledger.id)].add("entity")

    return candidates



def _features(
    bank: TransactionInput,
    ledger: TransactionInput,
) -> CandidateFeatures:
    print(f"Calculating features for bank transaction {bank.id} and ledger entry {ledger.id}")
    reference_agreement = _reference_agreement(_references(bank), _references(ledger))
    bank_credit = bank.credit_amount or Decimal("0")
    bank_debit = bank.debit_amount or Decimal("0")
    ledger_credit = ledger.credit_amount or Decimal("0")
    ledger_debit = ledger.debit_amount or Decimal("0")

    amount_agreement = (
        "exact"
        if bank_credit == ledger_credit and bank_debit == ledger_debit
        else "different"
    )
    

    return CandidateFeatures(
        reference_agreement=reference_agreement,
        amount_agreement=amount_agreement,
        date_difference_days=_date_difference(bank.transaction_date, ledger.transaction_date),
        entity_similarity=compute_entity_similarity(bank.entity_name, ledger.entity_name),
    )



def _score(
    features: CandidateFeatures,
    config: ReconciliationConfig,
) -> tuple[float, float, str]:
    date_diff = features.date_difference_days
    date_window = config.date_window_days

    if date_diff > date_window:
        return 0.0, (
            config.reference_threshold
            if features.reference_agreement in {"exact", "partial"}
            else config.reference_free_threshold
        ), (
            "reference-supported"
            if features.reference_agreement in {"exact", "partial"}
            else "reference-free"
        )

    date_weight_reference = (
        0.10
        if date_window == 0 and date_diff == 0
        else (
            max(0.0, 0.10 * (1 - date_diff / date_window))
            if date_window > 0 else 0.0
        )
    )

    date_weight_free = (
        0.25
        if date_window == 0 and date_diff == 0
        else (
            max(0.0, 0.25 * (1 - date_diff / date_window))
            if date_window > 0 else 0.0
        )
    )

    similarity = features.entity_similarity or 0.0

    if features.reference_agreement in {"exact", "partial"}:
        score = (
            (0.55 if features.reference_agreement == "exact" else 0.30)
            + (0.30 if features.amount_agreement == "exact" else 0.0)
            + date_weight_reference
            + 0.10 * similarity
        )

        return (
            min(score, 1.0),
            config.reference_threshold,
            "reference-supported",
        )

    score = (
        (0.50 if features.amount_agreement == "exact" else 0.0)
        + date_weight_free
        + 0.30 * similarity
    )

    return (
        min(score, 1.0),
        config.reference_free_threshold,
        "reference-free",
    )


def reconcile(
    run_id: str,
    bank_transactions: list[TransactionInput],
    ledger_entries: list[TransactionInput],
    config: ReconciliationConfig | None = None,
) -> ReconciliationOutcome:
    print(f"Starting reconciliation for run_id: {run_id} with {len(bank_transactions)} bank transactions and {len(ledger_entries)} ledger entries")
    config = config or ReconciliationConfig()
    valid_bank = bank_transactions
    valid_ledger = ledger_entries
    bank_by_id = {transaction.id: transaction for transaction in valid_bank}
    ledger_by_id = {transaction.id: transaction for transaction in valid_ledger}
    generated = _candidate_pairs(valid_bank, valid_ledger, config)

    decisions: list[CandidateDecision] = []
    for (bank_id, ledger_id), sources in generated.items():
        features = _features(bank_by_id[bank_id], ledger_by_id[ledger_id])
        score, threshold, policy = _score(features, config)
        outcomes: list[str] = []
        reasons: list[str] = []
        if features.amount_agreement == "different":
            outcomes.append("blocked:amount_mismatch")
            reasons.append("amount_mismatch")

        blocked = bool(reasons)
        if not blocked:
            outcomes.append("eligible")
        decisions.append(
            CandidateDecision(
                bank_transaction_id=bank_id,
                ledger_entry_id=ledger_id,
                candidate_sources=sorted(sources),
                features=features,
                rule_outcomes=outcomes,
                score=round(score, 4),
                score_threshold=threshold,
                scoring_policy=policy,
                disposition="exception" if blocked else "pending_review",
                reason_codes=reasons,
            )
        )

    unmatched_bank = set(bank_by_id)
    unmatched_ledger = set(ledger_by_id)
    
    # Round 1: Reference-based matching
    _select_round(
        decisions,
        unmatched_bank,
        unmatched_ledger,
        config,
        bank_by_id,
        ledger_by_id,
        round_number=1,
    )

    # Round 2: Strict exact-name matching with uniqueness
    _select_round(
        decisions,
        unmatched_bank,
        unmatched_ledger,
        config,
        bank_by_id,
        ledger_by_id,
        round_number=2,
    )

    # Round 3: Score-based matching
    _select_round(
        decisions,
        unmatched_bank,
        unmatched_ledger,
        config,
        bank_by_id,
        ledger_by_id,
        round_number=3,
    )


    candidate_by_bank: dict[str, list[CandidateDecision]] = defaultdict(list)
    candidate_by_ledger: dict[str, list[CandidateDecision]] = defaultdict(list)
    for candidate in decisions:
        candidate_by_bank[candidate.bank_transaction_id].append(candidate)
        candidate_by_ledger[candidate.ledger_entry_id].append(candidate)

    transaction_decisions: list[TransactionDecision] = []

    for transaction_type, transactions, related in (
        ("bank", valid_bank, candidate_by_bank),
        ("ledger", valid_ledger, candidate_by_ledger),
    ):
        for transaction in transactions:
            candidates = related.get(transaction.id, [])

            if any(c.disposition == "matched" for c in candidates):
                disposition = "matched"

            elif any(
                c.disposition == "pending_review"
                for c in candidates
            ):
                disposition = "pending_review"

            elif any(c.disposition == "exception" for c in candidates):
                disposition = "exception"

            else:
                disposition = "unmatched"

            reason_codes = sorted({
                reason
                for candidate in candidates
                for reason in candidate.reason_codes
            })

            transaction_decisions.append(
                TransactionDecision(
                    transaction_id=transaction.id,
                    transaction_type=transaction_type,
                    disposition=disposition,
                    reason_codes=reason_codes,
                )
            )
    from collections import Counter

    print(
        "Candidate dispositions:",
        Counter(c.disposition for c in decisions),
    )

    print(
        "Candidate reasons:",
        Counter(
            reason
            for candidate in decisions
            for reason in candidate.reason_codes
        ),
    )

    print(
        "Transaction dispositions:",
        Counter(t.disposition for t in transaction_decisions),
    )

    return ReconciliationOutcome(
        run_id=run_id,
        policy_version=config.policy_version,
        model_version=config.model_version,
        config=config,
        candidates=decisions,
        transactions=transaction_decisions,
        matched_count=sum(item.disposition == "matched" for item in decisions),
        pending_review_count=sum(item.disposition == "pending_review" for item in decisions),
        exception_count=sum(item.disposition == "exception" for item in decisions),
        unmatched_count=sum(item.disposition == "unmatched" for item in transaction_decisions),
    )


def _select_round(
    candidates: list[CandidateDecision],
    unmatched_bank: set[str],
    unmatched_ledger: set[str],
    config: ReconciliationConfig,
    bank_by_id: dict[str, TransactionInput],
    ledger_by_id: dict[str, TransactionInput],
    *,
    round_number: int,
) -> None:
    print(f"Selecting candidates for round {round_number} with {len(unmatched_bank)} unmatched bank transactions and {len(unmatched_ledger)} unmatched ledger entries")
    eligible = [
        candidate
        for candidate in candidates
        if candidate.disposition == "pending_review"
        and candidate.bank_transaction_id in unmatched_bank
        and candidate.ledger_entry_id in unmatched_ledger
        and candidate.features.date_difference_days <= config.date_window_days
    ]
    if round_number == 1:
        # Round 1 uses exact normalized entity name + both amounts + exact date.
        # References are deliberately not required and conflicting references
        # do not prevent an otherwise valid match.
        strict_matches = [
            candidate
            for candidate in eligible
            if candidate.features.amount_agreement == "exact"
            and candidate.features.date_difference_days == 0
            and _normalized_name(
                bank_by_id[candidate.bank_transaction_id].entity_name
            )
            and _normalized_name(
                bank_by_id[candidate.bank_transaction_id].entity_name
            )
            == _normalized_name(
                ledger_by_id[candidate.ledger_entry_id].entity_name
            )
            and not candidate.reason_codes
        ]
        strict_counts_by_bank: dict[str, int] = defaultdict(int)
        strict_counts_by_ledger: dict[str, int] = defaultdict(int)
        for candidate in strict_matches:
            strict_counts_by_bank[candidate.bank_transaction_id] += 1
            strict_counts_by_ledger[candidate.ledger_entry_id] += 1
        eligible = [
            candidate
            for candidate in strict_matches
            if strict_counts_by_bank[candidate.bank_transaction_id] == 1
            and strict_counts_by_ledger[candidate.ledger_entry_id] == 1
        ]
    else:
        eligible = [
            candidate
            for candidate in eligible
            if candidate.score >= candidate.score_threshold
        ]

    bank_choices: dict[str, list[CandidateDecision]] = defaultdict(list)
    ledger_choices: dict[str, list[CandidateDecision]] = defaultdict(list)
    for candidate in eligible:
        bank_choices[candidate.bank_transaction_id].append(candidate)
        ledger_choices[candidate.ledger_entry_id].append(candidate)

    def unique_best(choices: list[CandidateDecision]) -> CandidateDecision | None:
        print(f"Selecting unique best candidate from {len(choices)} choices")
        ranked = sorted(choices, key=lambda candidate: (-candidate.score, candidate.ledger_entry_id, candidate.bank_transaction_id))
        if not ranked:
            return None
        margin = ranked[0].score - ranked[1].score if len(ranked) > 1 else 1.0
        ranked[0].score_margin = round(margin, 4)
        if margin < config.minimum_score_margin:
            return None
        return ranked[0]

    best_by_bank = {key: unique_best(value) for key, value in bank_choices.items()}
    best_by_ledger = {key: unique_best(value) for key, value in ledger_choices.items()}
    assignments = sorted(
        (
            candidate
            for candidate in best_by_bank.values()
            if candidate is not None
            and best_by_ledger.get(candidate.ledger_entry_id) is candidate
        ),
        key=lambda candidate: (-candidate.score, candidate.bank_transaction_id, candidate.ledger_entry_id),
    )
    for candidate in assignments:
        if candidate.bank_transaction_id not in unmatched_bank or candidate.ledger_entry_id not in unmatched_ledger:
            continue
        candidate.disposition = "matched"
        candidate.matching_round = round_number
        candidate.rule_outcomes.append(f"confirmed:round_{round_number}")
        unmatched_bank.remove(candidate.bank_transaction_id)
        unmatched_ledger.remove(candidate.ledger_entry_id)
