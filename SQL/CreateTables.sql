
-- =========================================================
-- Reconcile AI: PostgreSQL Initial Schema
-- Run in Neon SQL Editor
-- =========================================================

BEGIN;

-- 1. USERS
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- 2. RECONCILIATION_RUNS
CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by UUID NOT NULL REFERENCES users(id),
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'processing', 'completed', 'failed', 'cancelled'
        )),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    )
);

-- 3. IMPORT_FILES
CREATE TABLE import_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    file_type VARCHAR(20) NOT NULL
        CHECK (file_type IN ('bank', 'ledger')),
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'uploaded'
        CHECK (status IN (
            'uploaded', 'processing', 'processed', 'failed'
        )),
    total_rows INTEGER NOT NULL DEFAULT 0
        CHECK (total_rows >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. BANK_TRANSACTIONS
CREATE TABLE bank_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    import_file_id UUID NOT NULL REFERENCES import_files(id),
    transaction_reference VARCHAR(255),
    transaction_date DATE NOT NULL,
    payer_name VARCHAR(255),
    credit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0
        CHECK (credit_amount >= 0),
    debit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0
        CHECK (debit_amount >= 0),
    description TEXT,
    reference_number VARCHAR(255),
    CHECK (NOT (
        credit_amount > 0 AND debit_amount > 0
    ))
);

-- 5. LEDGER_ENTRIES
CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    import_file_id UUID NOT NULL REFERENCES import_files(id),
    ledger_entry_id VARCHAR(255),
    invoice_id VARCHAR(255),
    customer_id INTEGER,
    customer_name VARCHAR(255),
    entry_date DATE NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    payment_reference VARCHAR(255)
);

-- 6. MATCH_CANDIDATES
CREATE TABLE match_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    bank_transaction_id UUID NOT NULL
        REFERENCES bank_transactions(id) ON DELETE CASCADE,
    ledger_entry_id UUID NOT NULL
        REFERENCES ledger_entries(id) ON DELETE CASCADE,
    rule_score NUMERIC(8, 4),
    ml_score NUMERIC(8, 4),
    status VARCHAR(30) NOT NULL DEFAULT 'candidate'
        CHECK (status IN (
            'candidate', 'accepted', 'rejected'
        )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, bank_transaction_id, ledger_entry_id)
);

-- 7. RECONCILIATION_RESULTS
CREATE TABLE reconciliation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    bank_transaction_id UUID REFERENCES bank_transactions(id),
    ledger_entry_id UUID REFERENCES ledger_entries(id),
    transaction_count INTEGER NOT NULL DEFAULT 2
        CHECK (transaction_count >= 0),
    status VARCHAR(30) NOT NULL
        CHECK (status IN (
            'matched', 'unmatched', 'partial', 'manual_review'
        )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        status <> 'matched'
        OR (
            bank_transaction_id IS NOT NULL
            AND ledger_entry_id IS NOT NULL
        )
    )
);

-- 8. ENTITY_MAPPINGS
CREATE TABLE entity_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approved_by UUID REFERENCES users(id),
    source_name VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (owner_user_id, source_name)
);

-- 9. EXCEPTIONS
CREATE TABLE exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES reconciliation_runs(id)
        ON DELETE CASCADE,
    bank_transaction_id UUID REFERENCES bank_transactions(id),
    ledger_entry_id UUID REFERENCES ledger_entries(id),
    result_id UUID REFERENCES reconciliation_results(id),
    entity_mapping_id UUID REFERENCES entity_mappings(id),
    reviewed_by UUID REFERENCES users(id),
    exception_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open'
        CHECK (status IN (
            'open', 'in_review', 'resolved', 'ignored'
        )),
    suggestion TEXT,
    review_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. AUDIT_HISTORY
CREATE TABLE audit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES reconciliation_runs(id),
    actor_user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- INDEXES: speed up dashboard, run history and review queries
-- =========================================================

CREATE INDEX idx_runs_created_at
    ON reconciliation_runs(created_at DESC);

CREATE INDEX idx_runs_status
    ON reconciliation_runs(status);

CREATE INDEX idx_import_files_run
    ON import_files(run_id);

CREATE INDEX idx_bank_transactions_run
    ON bank_transactions(run_id);

CREATE INDEX idx_bank_transactions_reference
    ON bank_transactions(transaction_reference);

CREATE INDEX idx_ledger_entries_run
    ON ledger_entries(run_id);

CREATE INDEX idx_ledger_entries_invoice
    ON ledger_entries(invoice_id);

CREATE INDEX idx_match_candidates_run_status
    ON match_candidates(run_id, status);

CREATE INDEX idx_match_candidates_bank
    ON match_candidates(bank_transaction_id);

CREATE INDEX idx_match_candidates_ledger
    ON match_candidates(ledger_entry_id);

CREATE INDEX idx_results_run_status
    ON reconciliation_results(run_id, status);

CREATE INDEX idx_exceptions_run_status
    ON exceptions(run_id, status);

CREATE INDEX idx_exceptions_reviewed_by
    ON exceptions(reviewed_by);

CREATE INDEX idx_audit_history_run_created
    ON audit_history(run_id, created_at DESC);

COMMIT;
