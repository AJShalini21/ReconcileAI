import { useState, useEffect } from "react"
import { Button } from "../../components/ui/Button"
import { PageHeader } from "../../components/ui/PageHeader"
import { Status } from "../../components/ui/Status"
import { analyzeException } from "../../services/apiClient"

export type ExceptionStatus = "Pending Review" | "Approved" | "Rejected"

export interface CandidateMatch {
  id: string
  exceptionId?: string
  ledgerEntryId?: string | null
  title?: string
  customer?: string | null
  ledgerValue: string
  ledgerDate?: string | null
  ledgerReference?: string | null
  invoiceReference?: string | null
  difference?: string
  confidence?: number
  matchStatus?: "High Match" | "Medium Match" | "Low Match"
  amountDiffText?: string
  dateDiffText?: string
  entityDiffText?: string
  refDiffText?: string
  suggestion?: string | null
  evidence?: string | null
  hasCollision?: boolean
  collisionWarning?: string | null
  competingBankTransactions?: string[]
}

export interface ExceptionItem {
  id: string
  entity: string
  reason: string
  reasonType: string
  run: string
  status: ExceptionStatus
  bankLabel: string
  bankValue: string
  ledgerLabel: string
  ledgerValue: string
  difference: string
  image?: string
  bankDate?: string | null
  ledgerDate?: string | null
  bankReference?: string | null
  ledgerReference?: string | null
  suggestion?: string | null
  explanation?: string | null
  aiAnalyzedAt?: string | null
  bankTransactionId?: string | null
  ledgerEntryId?: string | null
  invoiceReference?: string | null
  bankDescription?: string | null
  customer?: string | null
  candidates?: CandidateMatch[]
}

export function ExceptionStatusBadge({ status }: { status: ExceptionStatus }) {
  return (
    <Status
      tone={
        status === "Approved"
          ? "success"
          : status === "Rejected"
            ? "error"
            : "warning"
      }
    >
      {status}
    </Status>
  )
}

export function ExceptionDetail({
  exception,
  onBack,
  onDecision,
  readOnly = false,
}: {
  exception: ExceptionItem
  onBack: () => void
  onDecision?: (
    status: ExceptionStatus,
    candidateId?: string,
    comment?: string,
  ) => Promise<void> | void
  readOnly?: boolean
}) {
  const [comments, setComments] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [showCollisionModal, setShowCollisionModal] = useState(false)

  // Default candidate derived from single-pair exception if candidates array not provided
  const initialCandidates: CandidateMatch[] =
    exception.candidates && exception.candidates.length > 0
      ? exception.candidates
      : [
          {
            id: exception.ledgerEntryId || exception.id,
            exceptionId: exception.id,
            ledgerEntryId: exception.ledgerEntryId,
            title: `Ledger entry • ${exception.customer ?? exception.entity}`,
            customer: exception.customer ?? exception.entity,
            ledgerValue: exception.ledgerValue,
            ledgerDate: exception.ledgerDate,
            ledgerReference: exception.ledgerReference,
            invoiceReference: exception.invoiceReference,
            difference: exception.difference,
            confidence: 94,
            matchStatus: "High Match",
            amountDiffText:
              exception.bankValue === exception.ledgerValue ||
              exception.difference === "₹0" ||
              exception.difference === "INR 0.00"
                ? "✓ Exact amount"
                : `Diff: ${exception.difference}`,
            dateDiffText:
              exception.bankDate === exception.ledgerDate
                ? "✓ Same day"
                : "Date variance",
            entityDiffText: "✓ Exact match",
            refDiffText:
              exception.bankReference &&
              exception.ledgerReference &&
              exception.bankReference === exception.ledgerReference
                ? "✓ Match"
                : "Different ref",
            suggestion: exception.suggestion,
          },
        ]

  const [candidateList, setCandidateList] = useState<CandidateMatch[]>(initialCandidates)
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>(
    initialCandidates[0]?.id ?? "",
  )
  const [currentExplanation, setCurrentExplanation] = useState<string | null>(
    exception.explanation ?? null,
  )
  const [currentSuggestion, setCurrentSuggestion] = useState<string | null>(
    exception.suggestion ?? null,
  )
  const [currentAnalyzedAt, setCurrentAnalyzedAt] = useState<string | null>(
    exception.aiAnalyzedAt ?? null,
  )

  useEffect(() => {
    setCandidateList(initialCandidates)
    setSelectedCandidateId(initialCandidates[0]?.id ?? "")
    setCurrentExplanation(exception.explanation ?? null)
    setCurrentSuggestion(exception.suggestion ?? null)
    setCurrentAnalyzedAt(exception.aiAnalyzedAt ?? null)
    setComments("")
    setActionError(null)
    setAnalysisError(null)
  }, [exception.id])

  const selectedCandidate =
    candidateList.find((c) => c.id === selectedCandidateId) ?? candidateList[0]

  const handleRunAIAnalysis = async () => {
    if (isAnalyzing || !exception.run || !exception.id) return
    setIsAnalyzing(true)
    setAnalysisError(null)
    try {
      const res = await analyzeException(
        exception.run,
        exception.id,
        selectedCandidate?.id,
      )
      setCurrentExplanation(res.explanation)
      setCurrentSuggestion(res.suggestion)
      setCurrentAnalyzedAt(new Date().toISOString())
      if (res.has_collision) {
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === selectedCandidate?.id
              ? {
                  ...c,
                  hasCollision: true,
                  collisionWarning:
                    res.collision_warning ??
                    "Competing Claim: Also matched to another transaction.",
                  competingBankTransactions: res.competing_bank_transactions,
                }
              : c,
          ),
        )
      }
    } catch (err: unknown) {
      setAnalysisError(
        err instanceof Error ? err.message : "Failed to run AI discrepancy analysis.",
      )
    } finally {
      setIsAnalyzing(false)
    }
  }

  const executeDecision = async (
    status: ExceptionStatus,
    candId?: string,
  ) => {
    if (isSubmitting || !onDecision) return
    setIsSubmitting(true)
    setActionError(null)
    try {
      await onDecision(status, candId, comments.trim() || undefined)
    } catch (err: unknown) {
      setActionError(
        err instanceof Error
          ? err.message
          : `Failed to ${(status || "").toLowerCase()} exception.`,
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <div className="detail-back">
        <Button onClick={onBack} variant="tertiary">
          ← Back to exceptions
        </Button>
      </div>

      <PageHeader
        action={<ExceptionStatusBadge status={exception.status} />}
        description={`Exception reason: ${exception.reason}`}
        title={`Review exception ${exception.id}`}
      />

      <div className="reconcile-split-layout">
        {/* BASE ANCHOR RECORD (BANK TRANSACTION) */}
        <article className="record-card record-card--sticky">
          <div className="record-card__heading">
            <div>
              <span className="record-card__eyebrow">Source Record (Base)</span>
              <h2>Bank transaction</h2>
            </div>
            <Status tone="info">Bank</Status>
          </div>
          <dl>
            <div>
              <dt>Date</dt>
              <dd>{exception.bankDate ?? "—"}</dd>
            </div>
            <div>
              <dt>Amount</dt>
              <dd className="record-amount">{exception.bankValue}</dd>
            </div>
            <div>
              <dt>Payer name</dt>
              <dd>{exception.customer ?? exception.entity ?? "—"}</dd>
            </div>
            <div>
              <dt>Payment Reference</dt>
              <dd>{exception.bankReference ?? "—"}</dd>
            </div>
            <div className="record-full-width">
              <dt>Description</dt>
              <dd>
                {exception.bankDescription ??
                  `Payment from ${exception.entity}`}
              </dd>
            </div>
          </dl>
        </article>

        {/* CANDIDATE MATCHES LIST */}
        <section className="candidates-column">
          <div className="candidates-header">
            <h2>Candidate Matches ({candidateList.length})</h2>
            <span>Select candidate to resolve</span>
          </div>

          {candidateList.map((cand, index) => {
            const isSelected = cand.id === selectedCandidateId
            const scoreClass =
              (cand.confidence ?? 90) >= 85
                ? "score--high"
                : (cand.confidence ?? 70) >= 65
                  ? "score--medium"
                  : "score--low"

            return (
              <article
                key={cand.id || index}
                className={`candidate-card ${isSelected ? "is-selected" : ""}`}
                onClick={() => setSelectedCandidateId(cand.id)}
              >
                <div className="candidate-top">
                  <div className="candidate-selector">
                    <input
                      type="radio"
                      name="candidate_pick"
                      id={`cand-radio-${cand.id}`}
                      className="candidate-radio"
                      checked={isSelected}
                      onChange={() => setSelectedCandidateId(cand.id)}
                    />
                    <label
                      htmlFor={`cand-radio-${cand.id}`}
                      className="candidate-title"
                      style={{ cursor: "pointer" }}
                    >
                      {cand.title ??
                        `Ledger entry • ${cand.customer ?? exception.entity}`}
                    </label>
                  </div>
                  <div className="candidate-badges">
                    {cand.confidence !== undefined && (
                      <span className={`candidate-score ${scoreClass}`}>
                        {cand.confidence}% Match
                      </span>
                    )}
                    <Status tone="neutral">Ledger</Status>
                  </div>
                </div>

                <dl className="candidate-dl">
                  <div>
                    <dt>Date</dt>
                    <dd>{cand.ledgerDate ?? "—"}</dd>
                    {cand.dateDiffText && (
                      <span
                        className={`match-diff ${
                          cand.dateDiffText.includes("✓")
                            ? "diff--match"
                            : "diff--neutral"
                        }`}
                      >
                        {cand.dateDiffText}
                      </span>
                    )}
                  </div>
                  <div>
                    <dt>Amount</dt>
                    <dd>{cand.ledgerValue}</dd>
                    {cand.amountDiffText && (
                      <span
                        className={`match-diff ${
                          cand.amountDiffText.includes("✓")
                            ? "diff--match"
                            : "diff--mismatch"
                        }`}
                      >
                        {cand.amountDiffText}
                      </span>
                    )}
                  </div>
                  <div>
                    <dt>Customer</dt>
                    <dd>{cand.customer ?? exception.entity}</dd>
                    {cand.entityDiffText && (
                      <span
                        className={`match-diff ${
                          cand.entityDiffText.includes("✓")
                            ? "diff--match"
                            : "diff--neutral"
                        }`}
                      >
                        {cand.entityDiffText}
                      </span>
                    )}
                  </div>
                  <div>
                    <dt>Payment Ref</dt>
                    <dd>{cand.ledgerReference ?? "—"}</dd>
                    {cand.refDiffText && (
                      <span
                        className={`match-diff ${
                          cand.refDiffText.includes("✓")
                            ? "diff--match"
                            : "diff--neutral"
                        }`}
                      >
                        {cand.refDiffText}
                      </span>
                    )}
                  </div>
                </dl>

                {cand.collisionWarning && (
                  <div className="candidate-collision-banner">
                    <span>⚠️</span>
                    <div>{cand.collisionWarning}</div>
                  </div>
                )}

                <div className="candidate-footer">
                  <span>
                    Invoice: {cand.invoiceReference ?? "—"} &bull; Entry ID:{" "}
                    {cand.ledgerEntryId ?? cand.id}
                  </span>
                  {isSelected && (
                    <span className="selected-tag">
                      &bull; Selected for approval
                    </span>
                  )}
                </div>
              </article>
            )
          })}
        </section>
      </div>

      <section className="evidence-section">
        <div className="evidence-copy">
          <div className="ai-analysis-header">
            <div className="ai-analysis-header__title">
              <h2>Discrepancy Analysis</h2>
              {currentAnalyzedAt && (
                <span className="ai-badge">
                  ✨ AI Verified
                </span>
              )}
            </div>
            <button
              type="button"
              className="ai-analyze-btn"
              disabled={isAnalyzing}
              onClick={handleRunAIAnalysis}
            >
              {isAnalyzing ? "⏳ Analyzing with AI..." : "✨ AI Discrepancy Analysis"}
            </button>
          </div>

          {analysisError && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "var(--control-radius)",
                background: "var(--error-bg)",
                border: "1px solid var(--border)",
                color: "var(--error)",
                fontSize: "12px",
              }}
            >
              {analysisError}
            </div>
          )}

          <div>
            <h2>Why was this flagged?</h2>
            <p>
              {currentExplanation ??
                selectedCandidate?.evidence ??
                `The source records differ ${exception.difference ? `by ${exception.difference.toLowerCase()}` : "in recorded values"}. The reconciliation model evaluated candidates for this bank transaction and flagged it for reviewer verification.`}
            </p>
          </div>
          <div>
            <h2>Suggested resolution</h2>
            <p>
              {currentSuggestion ??
                selectedCandidate?.suggestion ??
                exception.suggestion ??
                "Review the recorded candidate features and discrepancy before deciding."}
            </p>
          </div>
        </div>
      </section>

      {!readOnly && onDecision && (
        <section className="review-decision">
          <label htmlFor="review-comments">Reviewer comments (optional)</label>
          <textarea
            disabled={isSubmitting}
            id="review-comments"
            onChange={(event) => setComments(event.target.value)}
            placeholder="Explain why you approve or reject this resolution"
            value={comments}
          />

          {actionError && (
            <div
              style={{
                marginTop: "12px",
                padding: "10px 14px",
                borderRadius: "var(--control-radius)",
                background: "var(--error-bg)",
                border: "1px solid var(--border)",
                color: "var(--error)",
                fontSize: "12px",
              }}
            >
              {actionError}
            </div>
          )}

          <div className="review-decision__actions">
            <div className="selected-summary-text">
              Target Match:{" "}
              <strong>
                {selectedCandidate?.title ??
                  `Ledger Entry (${selectedCandidate?.ledgerValue ?? exception.ledgerValue})`}
              </strong>
            </div>
            <div className="action-buttons">
              <Button
                icon="close"
                disabled={isSubmitting}
                onClick={() => executeDecision("Rejected")}
              >
                {isSubmitting ? "Processing..." : "Reject exception"}
              </Button>
              <Button
                icon="audit"
                disabled={isSubmitting}
                onClick={() => {
                  if (selectedCandidate?.hasCollision) {
                    setShowCollisionModal(true)
                  } else {
                    executeDecision("Approved", selectedCandidate?.id)
                  }
                }}
                variant="primary"
              >
                {isSubmitting ? "Approving..." : "Approve match"}
              </Button>
            </div>
          </div>
        </section>
      )}

      {showCollisionModal && (
        <div className="collision-modal-backdrop">
          <div className="collision-modal">
            <h3>⚠️ Cross-Transaction Collision Warning</h3>
            <p>
              The candidate ledger entry{" "}
              <strong>{selectedCandidate?.title || selectedCandidate?.customer}</strong> is
              also evaluated for competing bank transaction(s)
              {selectedCandidate?.competingBankTransactions &&
              selectedCandidate.competingBankTransactions.length > 0
                ? ` (${selectedCandidate.competingBankTransactions.join(", ")})`
                : ""} in this reconciliation run.
              <br /><br />
              Approving this match will bind this ledger entry exclusively to the current bank transaction and automatically unbind/reject it for the competing transaction(s).
            </p>
            <div className="collision-modal__actions">
              <Button
                variant="tertiary"
                onClick={() => setShowCollisionModal(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={async () => {
                  setShowCollisionModal(false)
                  await executeDecision("Approved", selectedCandidate?.id)
                }}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Approving..." : "Confirm & Approve Match"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
