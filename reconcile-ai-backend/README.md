# ReconcileAI Backend

This is the FastAPI backend for the ReconcileAI financial reconciliation system.

## Tech stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Uvicorn

## Getting started

1. Create and activate a virtual environment
2. Install dependencies
3. Run the app

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- Health check: `GET /health`
- API base: `/api/v1`

## Reconciliation

`POST /api/v1/reconciliations` imports the bank and ledger CSVs, runs matching,
and returns the run ID and summary counts. The run can also be executed or
retrieved by repeating `POST /api/v1/reconciliations/{run_id}/execute`; an
already completed reconciliation returns its persisted outcome.
Multipart fields `dateWindowDays`, `referenceThreshold`,
`referenceFreeThreshold`, `minimumScoreMargin`, and
`entityCandidateThreshold` configure the initial run.

The initial deterministic engine generates candidates from references,
equal-amount/date-window matches (three days by default), and entity-name
similarity. It records candidate features, rule outcomes, scores, policy/model
versions, classifications, and discrepancies in the audit tables. Exact
reference/amount/direction pairs are considered in strict round 1; remaining
eligible candidates use configurable thresholds and a best-versus-runner-up
margin in round 2. Direction mismatches, amount mismatches, conflicting
references, and currency mismatches are never automatically accepted.
Invalid CSV rows are excluded from matching and retained with their validation
reason and source row in the run audit history.

Pending candidates can be reviewed with
`POST /api/v1/reconciliations/{run_id}/candidates/{candidate_id}/review`.
Supply `action` (`approve` or `reject`), an active `reviewer_user_id`, and an
optional comment. Reviewer actions are audited. Run the Alembic migration
(`alembic upgrade head`) before using reconciliation on an existing database;
it adds persisted ledger transaction direction.
