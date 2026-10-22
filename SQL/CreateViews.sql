
CREATE OR REPLACE VIEW v_dashboard_summary AS
SELECT
    COUNT(DISTINCT r.id) AS total_runs,

    COUNT(DISTINCT r.id) FILTER (
        WHERE r.created_at >= date_trunc('month', CURRENT_TIMESTAMP)
          AND r.created_at < date_trunc(
              'month', CURRENT_TIMESTAMP
          ) + INTERVAL '1 month'
    ) AS runs_this_month,

    (
        SELECT COUNT(*)
        FROM reconciliation_results rr
        WHERE rr.status = 'matched'
    ) AS matched_transactions,

    (
        SELECT COUNT(*)
        FROM exceptions e
        WHERE e.status IN ('open', 'in_review')
    ) AS open_exceptions

FROM reconciliation_runs r;


CREATE OR REPLACE VIEW v_reconciliation_run_summary AS
SELECT
    r.id AS run_id,
    r.status,
    r.created_by,
    r.created_at,
    r.started_at,
    r.completed_at,

    COALESCE(f.file_count, 0) AS file_count,
    COALESCE(b.bank_transaction_count, 0)
        AS bank_transaction_count,
    COALESCE(l.ledger_entry_count, 0)
        AS ledger_entry_count,
    COALESCE(m.match_count, 0) AS match_count,
    COALESCE(e.exception_count, 0) AS exception_count

FROM reconciliation_runs r

LEFT JOIN (
    SELECT run_id, COUNT(*) AS file_count
    FROM import_files
    GROUP BY run_id
) f ON f.run_id = r.id

LEFT JOIN (
    SELECT run_id, COUNT(*) AS bank_transaction_count
    FROM bank_transactions
    GROUP BY run_id
) b ON b.run_id = r.id

LEFT JOIN (
    SELECT run_id, COUNT(*) AS ledger_entry_count
    FROM ledger_entries
    GROUP BY run_id
) l ON l.run_id = r.id

LEFT JOIN (
    SELECT run_id, COUNT(*) AS match_count
    FROM reconciliation_results
    WHERE status = 'matched'
    GROUP BY run_id
) m ON m.run_id = r.id

LEFT JOIN (
    SELECT run_id, COUNT(*) AS exception_count
    FROM exceptions
    WHERE status IN ('open', 'in_review')
    GROUP BY run_id
) e ON e.run_id = r.id;



CREATE OR REPLACE VIEW v_exception_review AS
SELECT
    e.id AS exception_id,
    e.run_id,
    e.exception_type,
    e.status,
    e.suggestion,
    e.review_comment,
    e.created_at,
    e.updated_at,

    b.transaction_reference,
    b.transaction_date,
    b.payer_name,
    b.credit_amount,
    b.debit_amount,

    l.ledger_entry_id,
    l.invoice_id,
    l.customer_name,
    l.entry_date,
    l.amount AS ledger_amount,

    em.source_name,
    em.canonical_name AS suggested_canonical_name,

    u.display_name AS reviewer_name

FROM exceptions e

LEFT JOIN bank_transactions b
    ON b.id = e.bank_transaction_id

LEFT JOIN ledger_entries l
    ON l.id = e.ledger_entry_id

LEFT JOIN entity_mappings em
    ON em.id = e.entity_mapping_id

LEFT JOIN users u
    ON u.id = e.reviewed_by;
