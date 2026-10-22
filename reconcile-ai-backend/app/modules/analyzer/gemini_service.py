from __future__ import annotations

import json
import logging
from typing import Any
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-pro-latest",
]


def _build_prompt(
    bank_tx: dict[str, Any],
    candidate_ledger: dict[str, Any],
    competing_bank_txs: list[dict[str, Any]],
    other_candidates: list[dict[str, Any]],
    discrepancy_info: dict[str, Any],
) -> str:
    prompt = f"""You are ReconcileAI's expert financial discrepancy analyzer. Analyze the reconciliation exception between the following Bank Transaction and Candidate Ledger Entry.

### 1. Bank Transaction (Anchor Record):
- ID: {bank_tx.get('id', 'N/A')}
- Date: {bank_tx.get('date', 'N/A')}
- Payer Name: {bank_tx.get('payer_name', 'N/A')}
- Reference Number: {bank_tx.get('reference_number', 'N/A')}
- Description: {bank_tx.get('description', 'N/A')}

### 2. Candidate Ledger Entry Evaluated:
- ID: {candidate_ledger.get('id', 'N/A')}
- Date: {candidate_ledger.get('date', 'N/A')}
- Customer Name: {candidate_ledger.get('customer_name', 'N/A')}
- Payment Reference: {candidate_ledger.get('payment_reference', 'N/A')}
- Invoice ID: {candidate_ledger.get('invoice_id', 'N/A')}

### 3. Detected Discrepancies:
- Amount Difference: {discrepancy_info.get('amount_diff', '0.00')}
- Date Variance: {discrepancy_info.get('date_diff', '0 days')}
- Entity Match: {discrepancy_info.get('entity_diff', 'N/A')}
- Reference Match: {discrepancy_info.get('ref_diff', 'N/A')}
- Total Candidates for this Bank Transaction: {len(other_candidates) + 1}
"""

    if competing_bank_txs:
        prompt += f"""
### 4. ⚠️ CROSS-TRANSACTION COLLISION DETECTED:
This ledger entry ({candidate_ledger.get('id')}) is ALSO evaluated as a candidate for {len(competing_bank_txs)} other bank transaction(s) in this reconciliation run:
"""
        for i, ctx in enumerate(competing_bank_txs, 1):
            prompt += (
                f"- Competing Bank Tx #{i}: ID={ctx.get('id')}, Date={ctx.get('date')}, "
                f"Ref={ctx.get('reference_number')}\n"
            )
        prompt += (
            "IMPORTANT: If the reviewer approves this candidate for the current bank transaction, "
            "it will be bound exclusively and rendered unavailable for the competing bank transaction(s). "
            "Your explanation and suggested resolution MUST address this competition directly.\n"
        )
    else:
        prompt += """
### 4. Cross-Transaction Collision Check:
No competing bank transactions share this ledger entry in this reconciliation run.
"""

    prompt += """
### Output Requirements:
Return a JSON object with EXACTLY the following keys:
{
  "explanation": "A concise, professional explanation for 'Why was this flagged?' highlighting the specific amount/date/entity discrepancy and explaining root causes (e.g., bank processing fee, tax withholding TDS, discount, date timing variance, or competing candidate claims).",
  "suggestion": "A clear, actionable recommendation for 'Suggested resolution' guiding the reviewer on whether to approve, request supporting documents (e.g. fee deduction certificate, invoice), or verify competing transactions before deciding.",
  "has_collision": true or false,
  "collision_warning": "A short warning message if has_collision is true, or null if false.",
  "confidence": "high", "medium", or "low"
}
"""
    return prompt


def generate_fallback_analysis(
    bank_tx: dict[str, Any],
    candidate_ledger: dict[str, Any],
    competing_bank_txs: list[dict[str, Any]],
    discrepancy_info: dict[str, Any],
) -> dict[str, Any]:
    diff = discrepancy_info.get("amount_diff", "0.00")
    has_collision = len(competing_bank_txs) > 0

    if has_collision:
        comp_refs = ", ".join(str(tx.get("reference_number") or tx.get("id"))[:12] for tx in competing_bank_txs)
        warning = f"Competing Claim: This ledger entry is also matched to Bank Tx ({comp_refs}). Approving will unbind it from other transactions."
        explanation = (
            f"The source records differ by {diff}. Additionally, this ledger entry is shared as a candidate "
            f"across {len(competing_bank_txs)} other bank transaction(s) ({comp_refs})."
        )
        suggestion = (
            f"Verify whether this ledger entry corresponds to Bank Tx {bank_tx.get('reference_number', '')} "
            f"or the competing transaction(s) ({comp_refs}) before approving."
        )
    else:
        warning = None
        explanation = (
            f"The source records differ by {diff}. The reconciliation model evaluated candidates for this bank transaction "
            "and flagged it for reviewer verification."
        )
        suggestion = "Review the recorded candidate features and discrepancy before deciding."

    return {
        "explanation": explanation,
        "suggestion": suggestion,
        "has_collision": has_collision,
        "collision_warning": warning,
        "confidence": "medium",
    }


def analyze_discrepancy_with_gemini(
    bank_tx: dict[str, Any],
    candidate_ledger: dict[str, Any],
    competing_bank_txs: list[dict[str, Any]],
    other_candidates: list[dict[str, Any]],
    discrepancy_info: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured, using rule-based analysis fallback.")
        return generate_fallback_analysis(bank_tx, candidate_ledger, competing_bank_txs, discrepancy_info)

    prompt = _build_prompt(bank_tx, candidate_ledger, competing_bank_txs, other_candidates, discrepancy_info)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    last_error: Exception | None = None
    for model_name in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            parsed = json.loads(parts[0]["text"])
                            # Ensure collision flag consistency
                            if competing_bank_txs:
                                parsed["has_collision"] = True
                                if not parsed.get("collision_warning"):
                                    comp_refs = ", ".join(
                                        str(tx.get("reference_number") or tx.get("id"))[:12]
                                        for tx in competing_bank_txs
                                    )
                                    parsed["collision_warning"] = (
                                        f"Competing Claim: Also matched to Bank Tx ({comp_refs}). "
                                        "Approving will unbind it from other transactions."
                                    )
                            return parsed
                else:
                    logger.warning(
                        "Gemini model %s returned status %d: %s",
                        model_name,
                        response.status_code,
                        response.text[:200],
                    )
        except Exception as exc:
            logger.warning("Gemini model %s failed: %s", model_name, exc)
            last_error = exc

    logger.error("All Gemini models failed, falling back to rule-based analysis: %s", last_error)
    return generate_fallback_analysis(bank_tx, candidate_ledger, competing_bank_txs, discrepancy_info)
