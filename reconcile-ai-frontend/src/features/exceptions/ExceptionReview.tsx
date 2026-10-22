import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Button } from "../../components/ui/Button"
import { PageHeader } from "../../components/ui/PageHeader"
import { SelectField } from "../../components/ui/SelectField"
import {
  ExceptionDetail,
  ExceptionStatusBadge,
  type CandidateMatch,
  type ExceptionItem,
  type ExceptionStatus,
} from "./ExceptionDetail"
import { reviewCandidate, type WorkspaceData } from "../../services/apiClient"

const initialExceptions: ExceptionItem[] = [
  {
    id: "EX-001",
    entity: "Cedar Retail Group",
    customer: "Cedar Retail Group",
    reason: "Ambiguous match • 3 candidates",
    reasonType: "Ambiguous match",
    run: "REC-2026-001",
    status: "Pending Review" as ExceptionStatus,
    bankLabel: "Bank amount",
    bankValue: "₹14,105.18",
    ledgerLabel: "Ledger amount",
    ledgerValue: "₹14,105.18",
    difference: "₹0.00",
    bankDate: "2026-05-23",
    ledgerDate: "2026-05-23",
    bankReference: "PAY-1150-0045",
    ledgerReference: "PAY-1150-0045",
    invoiceReference: "INV-1150-0045",
    bankDescription: "Payment PAY-1150-0045 invoice INV-1150-0045",
    suggestion: "Approve match with Candidate #1 (Cedar Retail Group). Exact reference and amount alignment.",
    image: "/exception-bank.svg",
    candidates: [
      {
        id: "cand-1",
        title: "Ledger entry • Cedar Retail Group",
        customer: "Cedar Retail Group",
        ledgerValue: "₹14,105.18",
        ledgerDate: "2026-05-23",
        ledgerReference: "PAY-1150-0045",
        invoiceReference: "INV-1150-0045",
        difference: "₹0.00",
        confidence: 96,
        matchStatus: "High Match",
        amountDiffText: "✓ Exact amount",
        dateDiffText: "✓ Same day",
        entityDiffText: "✓ Exact name",
        refDiffText: "✓ Match",
        suggestion: "Approve match with Candidate #1 (Cedar Retail Group). Exact amount, date, and invoice references align.",
        evidence: "Multiple potential ledger entries matched attributes of bank transaction PAY-1150-0045. Candidate #1 (Cedar Retail Group) shares exact amount, date, and invoice reference."
      },
      {
        id: "cand-2",
        title: "Ledger entry • Cedar Retail Stores",
        customer: "Cedar Retail Stores",
        ledgerValue: "₹14,000.00",
        ledgerDate: "2026-05-21",
        ledgerReference: "PAY-1142-PO9",
        invoiceReference: "INV-1142-0012",
        difference: "-₹105.18",
        confidence: 74,
        matchStatus: "Medium Match",
        amountDiffText: "Diff: -₹105.18",
        dateDiffText: "2 days earlier",
        entityDiffText: "91% entity sim",
        refDiffText: "Different ref",
        suggestion: "Verify if ₹105.18 difference is attributable to transaction charges before approving.",
        evidence: "Candidate #2 differs in amount by ₹105.18 and date by 2 days. The model flagged this due to high entity name similarity (91%)."
      },
      {
        id: "cand-3",
        title: "Ledger entry • Cedar Logistics Hub",
        customer: "Cedar Logistics Hub",
        ledgerValue: "₹14,105.18",
        ledgerDate: "2026-05-18",
        ledgerReference: "PAY-1090-LOG",
        invoiceReference: "INV-1090-0081",
        difference: "₹0.00",
        confidence: 48,
        matchStatus: "Low Match",
        amountDiffText: "✓ Exact amount",
        dateDiffText: "5 days earlier",
        entityDiffText: "62% entity sim",
        refDiffText: "Different ref",
        suggestion: "Only approve if this transaction was incorrectly attributed to the logistics entity.",
        evidence: "Candidate #3 has the identical amount of ₹14,105.18, but the date is 5 days earlier and payment reference is different."
      }
    ]
  },
  {
    id: "EX-002",
    entity: "Global Tech Ltd",
    customer: "Global Technologies Ltd",
    reason: "Name mismatch",
    reasonType: "Name mismatch",
    run: "REC-2026-001",
    status: "Pending Review" as ExceptionStatus,
    bankLabel: "Bank name",
    bankValue: "Global Tech Solutions",
    ledgerLabel: "Ledger name",
    ledgerValue: "Global Technologies Ltd",
    difference: "Name",
    bankDate: "2026-10-14",
    ledgerDate: "2026-10-14",
    bankReference: "REF-GT-991",
    ledgerReference: "REF-GT-991",
    invoiceReference: "INV-GT-991",
    image: "/exception-ledger.svg",
  },
  {
    id: "EX-003",
    entity: "Northstar Services",
    customer: "Northstar Services",
    reason: "Date mismatch",
    reasonType: "Date mismatch",
    run: "REC-2026-002",
    status: "Pending Review" as ExceptionStatus,
    bankLabel: "Bank date",
    bankValue: "12 Oct 2026",
    ledgerLabel: "Ledger date",
    ledgerValue: "11 Oct 2026",
    difference: "1 day",
    bankDate: "2026-10-12",
    ledgerDate: "2026-10-11",
    bankReference: "NS-4011",
    ledgerReference: "NS-4011",
    image: "/exception-bank.svg",
  },
]

export function ExceptionReview({
  workspace,
  onRefresh,
}: {
  workspace?: WorkspaceData
  onRefresh?: () => void
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [exceptions, setExceptions] = useState<ExceptionItem[]>(() => {
    try {
      const saved = localStorage.getItem("reconcile_demo_exceptions")
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
          const unapproved = parsed.filter(
            (p: ExceptionItem) => p.status !== "Approved",
          )
          if (unapproved.length > 0) return parsed
        }
      }
    } catch {
      // ignore
    }
    return initialExceptions
  })

  const handleResetDemo = () => {
    try {
      localStorage.removeItem("reconcile_demo_exceptions")
    } catch {
      // ignore
    }
    setExceptions(initialExceptions)
    setSelectedId(undefined)
  }

  const [approvedCountState, setApprovedCountState] = useState<number>(() => {
    try {
      const stored = localStorage.getItem("reconcile_approved_count")
      return stored ? parseInt(stored, 10) : 0
    } catch {
      return 0
    }
  })

  const reason = searchParams.get("reason") ?? "All exception types"
  const status = searchParams.get("status") ?? "All statuses"
  const selectedId = searchParams.get("id") ?? undefined

  const setReason = (newReason: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newReason && newReason !== "All exception types") {
        next.set("reason", newReason)
      } else {
        next.delete("reason")
      }
      return next
    })
  }

  const setStatus = (newStatus: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newStatus && newStatus !== "All statuses") {
        next.set("status", newStatus)
      } else {
        next.delete("status")
      }
      return next
    })
  }

  const setSelectedId = (id?: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (id) {
        next.set("id", id)
      } else {
        next.delete("id")
      }
      return next
    })
  }

  const displayedExceptions: ExceptionItem[] = useMemo(() => {
    if (workspace) {
      const wsExceptions = workspace.exceptions ?? []
      if (wsExceptions.length === 0) {
        return []
      }

      // Group workspace exceptions by bank_transaction_id to anchor on bank transaction
      const grouped = new Map<string, typeof workspace.exceptions>()
      for (const item of wsExceptions) {
        // Exclude approved exceptions
        if (item.status === "Approved") continue

        const key = item.bank_transaction_id || item.id
        if (!grouped.has(key)) {
          grouped.set(key, [])
        }
        grouped.get(key)!.push(item)
      }

      const items: ExceptionItem[] = []
      for (const [, group] of grouped.entries()) {
        const primary = group[0]

        let candidates: CandidateMatch[] = []
        if (primary.candidates && primary.candidates.length > 0) {
          candidates = primary.candidates.map((cand) => ({
            id: cand.id,
            exceptionId: primary.id,
            ledgerEntryId: cand.ledger_entry_id,
            title: cand.title ?? `Ledger entry • ${cand.customer ?? primary.entity}`,
            customer: cand.customer ?? primary.customer ?? primary.entity,
            ledgerValue: cand.ledger_value,
            ledgerDate: cand.ledger_date,
            ledgerReference: cand.ledger_reference,
            invoiceReference: cand.invoice_reference,
            difference: cand.difference,
            confidence: cand.confidence ?? 90,
            matchStatus: (cand.match_status as "High Match" | "Medium Match" | "Low Match") ?? "High Match",
            amountDiffText: cand.amount_diff_text ?? undefined,
            dateDiffText: cand.date_diff_text ?? undefined,
            entityDiffText: cand.entity_diff_text ?? undefined,
            refDiffText: cand.ref_diff_text ?? undefined,
            suggestion: cand.suggestion,
            hasCollision: cand.has_collision,
            collisionWarning: cand.collision_warning,
            competingBankTransactions: cand.competing_bank_transactions,
          }))
        } else {
          candidates = group.map((cand, idx) => ({
            id: cand.id,
            exceptionId: cand.id,
            ledgerEntryId: cand.ledger_entry_id,
            title: `Ledger entry • ${cand.customer ?? cand.entity}`,
            customer: cand.customer ?? cand.entity,
            ledgerValue: cand.ledger_value,
            ledgerDate: cand.ledger_date,
            ledgerReference: cand.ledger_reference,
            invoiceReference: cand.invoice_reference,
            difference: cand.difference,
            confidence: idx === 0 ? 94 : Math.max(48, 94 - idx * 22),
            matchStatus: idx === 0 ? "High Match" : idx === 1 ? "Medium Match" : "Low Match",
            amountDiffText:
              cand.bank_value === cand.ledger_value ||
              (cand.difference && cand.difference.includes("0.00")) ||
              cand.difference === "₹0"
                ? "✓ Exact amount"
                : `Diff: ${cand.difference}`,
            dateDiffText:
              cand.bank_date === cand.ledger_date ? "✓ Same day" : "Date variance",
            entityDiffText: "Entity similarity",
            refDiffText:
              cand.bank_reference &&
              cand.ledger_reference &&
              cand.bank_reference === cand.ledger_reference
                ? "✓ Match"
                : "Different ref",
            suggestion: cand.suggestion,
          }))
        }

        items.push({
          id: primary.id,
          entity: primary.entity,
          customer: primary.customer,
          reason:
            candidates.length > 1
              ? `Ambiguous match • ${candidates.length} candidate matches`
              : primary.reason,
          reasonType: primary.reason_type,
          run: primary.run,
          status: primary.status,
          bankLabel: primary.bank_label,
          bankValue: primary.bank_value,
          ledgerLabel: primary.ledger_label,
          ledgerValue: primary.ledger_value,
          difference: primary.difference,
          bankDate: primary.bank_date,
          ledgerDate: primary.ledger_date,
          bankReference: primary.bank_reference,
          ledgerReference: primary.ledger_reference,
          bankTransactionId: primary.bank_transaction_id,
          ledgerEntryId: primary.ledger_entry_id,
          invoiceReference: primary.invoice_reference,
          bankDescription: primary.bank_description,
          suggestion: primary.suggestion,
          explanation: primary.explanation,
          aiAnalyzedAt: primary.ai_analyzed_at,
          candidates,
        })
      }
      return items.filter((item) => item.status !== "Approved")
    }

    // Only when NOT logged in (!workspace), show demo exceptions
    return exceptions.filter((item) => item.status !== "Approved")
  }, [workspace, exceptions])

  const selected = workspace
    ? displayedExceptions.find((item) => item.id === selectedId)
    : (displayedExceptions.find((item) => item.id === selectedId) ||
       exceptions.find((item) => item.id === selectedId) ||
       initialExceptions.find((item) => item.id === selectedId))

  const handleDecision = async (
    exceptionItem: ExceptionItem,
    nextStatus: ExceptionStatus,
    candidateId?: string,
    comment?: string,
  ) => {
    // Determine candidate ID to review
    const targetCandidateId =
      candidateId ||
      exceptionItem.candidates?.[0]?.id ||
      exceptionItem.ledgerEntryId

    if (workspace && exceptionItem.run && targetCandidateId) {
      const action = nextStatus === "Approved" ? "approve" : "reject"
      await reviewCandidate(exceptionItem.run, targetCandidateId, action, comment)
    }

    if (nextStatus === "Approved") {
      setApprovedCountState((prev) => {
        const next = prev + 1
        try {
          localStorage.setItem("reconcile_approved_count", String(next))
        } catch {
          // ignore
        }
        return next
      })
    }

    setExceptions((current) => {
      // Once approved, remove it from the exception review queue completely
      const updated =
        nextStatus === "Approved"
          ? current.filter((item) => item.id !== exceptionItem.id)
          : current.map((item) =>
              item.id === exceptionItem.id ? { ...item, status: nextStatus } : item,
            )
      try {
        localStorage.setItem(
          "reconcile_demo_exceptions",
          JSON.stringify(updated),
        )
      } catch {
        // ignore
      }
      return updated
    })

    if (onRefresh) {
      onRefresh()
    }

    setSelectedId(undefined)
  }

  const auditedCount = useMemo(() => {
    if (workspace) {
      let count = 0
      if (workspace.metrics?.audited_approved_exceptions !== undefined) {
        count = Math.max(count, workspace.metrics.audited_approved_exceptions)
      }
      if (workspace.audit_events) {
        const auditApproved = workspace.audit_events.filter(
          (e) =>
            e.action === "exception_approved" ||
            e.action === "candidate_approved" ||
            e.action === "Exception review approve" ||
            e.title?.toLowerCase().includes("approved") ||
            e.action?.toLowerCase().includes("approved"),
        ).length
        count = Math.max(count, auditApproved)
      }
      return count
    }
    return approvedCountState
  }, [workspace, approvedCountState])

  const handleBack = () => {
    setSelectedId(undefined)
  }

  if (selected) {
    return (
      <ExceptionDetail
        exception={selected}
        onBack={handleBack}
        onDecision={(nextStatus, candidateId, comment) =>
          handleDecision(selected, nextStatus, candidateId, comment)
        }
        readOnly={false}
      />
    )
  }

  const rows = displayedExceptions.filter(
    (item) =>
      item.status !== "Approved" &&
      (reason === "All exception types" || item.reasonType === reason) &&
      (status === "All statuses" || item.status === status),
  )
  const reasonTypes = [
    ...new Set(displayedExceptions.map((item) => item.reasonType)),
  ]

  return (
    <>
      <PageHeader
        action={
          !workspace ? (
            <Button onClick={handleResetDemo} variant="secondary">
              Reload demo data
            </Button>
          ) : undefined
        }
        description="Review unresolved transactions and suggested matches."
        title="Exception review"
      />
      <section className="exception-summary">
        <div>
          <span>Exceptions to review</span>
          <strong>{displayedExceptions.length}</strong>
        </div>
        <div>
          <span>Pending review</span>
          <strong>
            {
              displayedExceptions.filter(
                (item) => item.status === "Pending Review",
              ).length
            }
          </strong>
        </div>
        <div>
          <span>Audited / Approved</span>
          <strong>{auditedCount}</strong>
        </div>
      </section>

      <section className="exception-filters">
        <div className="filter-field">
          <span>Filter by reason</span>
          <SelectField
            label="Filter by reason"
            onChange={setReason}
            value={reason}
          >
            <option>All exception types</option>
            {reasonTypes.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </SelectField>
        </div>
        <div className="filter-field">
          <span>Status</span>
          <SelectField
            label="Filter by status"
            onChange={setStatus}
            value={status}
          >
            <option>All statuses</option>
            <option>Pending Review</option>
            <option>Rejected</option>
          </SelectField>
        </div>
      </section>

      <div className="list-label">Exception records</div>
      <section className="exception-list">
        {rows.length === 0 ? (
          <div
            className="panel"
            style={{
              padding: "40px 24px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
              No exceptions to review
            </h3>
            <p
              style={{
                margin: 0,
                color: "var(--text-muted)",
                fontSize: "14px",
                maxWidth: "460px",
              }}
            >
              {workspace
                ? "No exceptions pending review in your workspace. Unresolved transactions from your reconciliation runs will appear here."
                : "All demo exceptions have been reviewed or approved. You can reload the demo records to test the review process again."}
            </p>
            {!workspace && (
              <Button onClick={handleResetDemo} variant="secondary">
                Reload demo exceptions
              </Button>
            )}
          </div>
        ) : (
          rows.map((exception, index) => {
            const image =
              exception.image ||
              ["/exception-bank.svg", "/exception-ledger.svg"][index % 2]

            return (
              <article
                className={`exception-card ${
                  image ? "" : "exception-card--no-image"
                }`}
                key={exception.id}
              >
                <img
                  alt={`Source document thumbnail for ${exception.id}`}
                  className="exception-card__image"
                  src={image}
                />

                <div className="exception-card__content">
                  <div className="exception-card__title">
                    <div>
                      <h2>
                        {exception.bankReference} · {exception.entity}
                      </h2>
                      <p>{exception.reason}</p>
                    </div>
                    <ExceptionStatusBadge status={exception.status} />
                  </div>
                  <div className="exception-values">
                    <div>
                      <span>{exception.bankLabel}</span>
                      <strong>{exception.bankValue}</strong>
                    </div>
                    <div>
                      <span>{exception.ledgerLabel}</span>
                      <strong>{exception.ledgerValue}</strong>
                    </div>
                    <div>
                      <span>Difference</span>
                      <strong className="difference-value">
                        {exception.difference}
                      </strong>
                    </div>
                  </div>
                  <div className="exception-card__footer">
                    <span>Payment-Reference: {exception.ledgerReference}</span>
                    <Button
                      onClick={() => setSelectedId(exception.id)}
                      variant="tertiary"
                    >
                      View details →
                    </Button>
                  </div>
                  <div className="exception-card__actions">
                    <Button
                      onClick={() => handleDecision(exception, "Rejected")}
                    >
                      Reject
                    </Button>
                    <Button
                      onClick={() => handleDecision(exception, "Approved")}
                      variant="primary"
                    >
                      Approve
                    </Button>
                  </div>
                </div>
              </article>
            )
          })
        )}
      </section>
    </>
  )
}
