import { useMemo } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "../../components/ui/Button"
import { RunStatusIcon } from "../../components/ui/RunStatusIcon"
import { Status } from "../../components/ui/Status"

export type ReconciliationTransactionStatus = "matched" | "review" | "exception" | "unmatched"

export interface ReconciliationTransaction {
  id: string
  displayId: string
  reference?: string | null
  entity: string
  amountSummary: string
  explanation: string
  status: ReconciliationTransactionStatus
}

export interface ReconciliationDetailData {
  runId: string
  status: string
  statusTone: "success" | "info" | "warning" | "error" | "neutral"
  sourceSummary: string
  createdAt: string
  totalProcessed: number
  matchedCount: number
  needsReviewCount: number
  exceptionCount: number
  bankFileName: string
  ledgerFileName: string
  dateWindow: string
  processingTime: string
  transactions: ReconciliationTransaction[]
}

type TransactionFilter = "all" | "matched" | "review" | "exceptions"

const filters: { label: string; value: TransactionFilter }[] = [
  { label: "All transactions", value: "all" },
  { label: "Matched", value: "matched" },
  { label: "Review", value: "review" },
  { label: "Exceptions", value: "exceptions" },
]

function statusLabel(status: ReconciliationTransactionStatus): string {
  if (status === "review") return "Review"
  if (status === "matched") return "Matched"
  return "Exception"
}

function statusTone(
  status: ReconciliationTransactionStatus,
): "success" | "warning" | "error" | "neutral" {
  if (status === "matched") return "success"
  if (status === "review") return "warning"
  return "error"
}

export function ReconciliationDetails({
  data,
  loading = false,
  error,
  emptyMessage,
  notice,
  runId,
  onRetry,
  onBack,
}: {
  data: ReconciliationDetailData | null
  loading?: boolean
  error?: string | null
  emptyMessage?: string
  notice?: string
  runId?: string
  onRetry?: () => void
  onBack?: () => void
}) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = searchParams.get("filter")
  const filter: TransactionFilter =
    filterParam === "matched" ||
    filterParam === "review" ||
    filterParam === "exceptions"
      ? filterParam
      : "all"

  const setFilter = (nextFilter: TransactionFilter) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (nextFilter && nextFilter !== "all") {
        next.set("filter", nextFilter)
      } else {
        next.delete("filter")
      }
      return next
    })
  }

  const handleBack = () => {
    if (onBack) {
      onBack()
      return
    }
    if (window.history.length > 1 && window.history.state?.idx > 0) {
      navigate(-1)
    } else {
      navigate("/run-history", { replace: true })
    }
  }

  const transactions = data?.transactions ?? []
  const filteredTransactions = useMemo(
    () =>
      transactions.filter((transaction) => {
        if (filter === "all") return true
        if (filter === "matched") return transaction.status === "matched"
        if (filter === "review") return transaction.status === "review"
        return ["exception", "unmatched"].includes(transaction.status)
      }),
    [filter, transactions],
  )

  if (loading) {
    return (
      <section className="reconciliation-detail-state" aria-live="polite">
        <h1>Loading reconciliation details</h1>
        <p>Fetching run information and transaction results…</p>
      </section>
    )
  }

  if (error) {
    return (
      <section
        className="reconciliation-detail-state reconciliation-detail-state--error"
        role="alert"
      >
        <h1>Unable to load reconciliation</h1>
        <p>{error}</p>
        {onRetry && (
          <Button onClick={onRetry} variant="secondary">
            Try again
          </Button>
        )}
      </section>
    )
  }

  if (!data) {
    return (
      <section className="reconciliation-detail-state">
        <h1>Reconciliation details unavailable</h1>
        <p>{emptyMessage ?? "The selected run has no available details."}</p>
        {runId && (
          <p className="reconciliation-detail-state__run-id">{runId}</p>
        )}
        <Button onClick={handleBack} variant="secondary">
          Back to Run History
        </Button>
      </section>
    )
  }

  const processed = Math.max(data.totalProcessed, 0)
  const matchedPercent =
    processed > 0 ? (data.matchedCount / processed) * 100 : 0
  const reviewPercent =
    processed > 0 ? (data.needsReviewCount / processed) * 100 : 0
  const exceptionPercent =
    processed > 0 ? (data.exceptionCount / processed) * 100 : 0
  const countByFilter: Record<TransactionFilter, number> = {
    all: transactions.length,
    matched: transactions.filter((item) => item.status === "matched").length,
    review: transactions.filter((item) => item.status === "review").length,
    exceptions: transactions.filter((item) =>
      ["exception", "unmatched"].includes(item.status),
    ).length,
  }

  return (
    <main className="reconciliation-detail">
      <button
        className="reconciliation-detail__back"
        onClick={handleBack}
        type="button"
      >
        <span aria-hidden="true">←</span>
        Run History / Run Details
      </button>
      {notice && (
        <p className="reconciliation-detail__notice" role="note">
          {notice}
        </p>
      )}

      <header className="reconciliation-detail__heading">
        <div>
          <h1>{data.runId}</h1>
          <p>{data.sourceSummary}</p>
          <time dateTime={data.createdAt}>
            Created{" "}
            {new Date(data.createdAt).toLocaleString(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </time>
        </div>
        <RunStatusIcon status={data.status} />
      </header>

      <section
        className="reconciliation-detail__summary"
        aria-label="Reconciliation summary"
      >
        <article>
          <span>Total processed</span>
          <strong>{data.totalProcessed.toLocaleString()}</strong>
          <small>Transactions</small>
        </article>
        <article>
          <span>Matched</span>
          <strong className="reconciliation-detail__value--matched">
            {data.matchedCount.toLocaleString()}
          </strong>
          <small>{matchedPercent.toFixed(2)}%</small>
        </article>
        <article>
          <span>Needs review</span>
          <strong className="reconciliation-detail__value--review">
            {data.needsReviewCount.toLocaleString()}
          </strong>
          <small>Pending decisions</small>
        </article>
        <article>
          <span>Exceptions</span>
          <strong className="reconciliation-detail__value--exception">
            {data.exceptionCount.toLocaleString()}
          </strong>
          <small>Unresolved items</small>
        </article>
      </section>

      <section
        className="reconciliation-detail__breakdown"
        aria-label="Reconciliation breakdown"
      >
        <h2>Reconciliation breakdown</h2>
        <div
          className="reconciliation-detail__bar"
          role="img"
          aria-label={`${matchedPercent.toFixed(2)} percent matched, ${reviewPercent.toFixed(2)} percent needs review, ${exceptionPercent.toFixed(2)} percent exceptions`}
        >
          <span
            className="reconciliation-detail__bar-segment reconciliation-detail__bar-segment--matched"
            style={{ width: `${matchedPercent}%` }}
          />
          <span
            className="reconciliation-detail__bar-segment reconciliation-detail__bar-segment--review"
            style={{ width: `${reviewPercent}%` }}
          />
          <span
            className="reconciliation-detail__bar-segment reconciliation-detail__bar-segment--exception"
            style={{ width: `${exceptionPercent}%` }}
          />
        </div>
        <div className="reconciliation-detail__breakdown-labels">
          <span className="reconciliation-detail__value--matched">
            Matched {matchedPercent.toFixed(2)}%
          </span>
          <span className="reconciliation-detail__value--review">
            Review {reviewPercent.toFixed(2)}%
          </span>
          <span className="reconciliation-detail__value--exception">
            Exceptions {exceptionPercent.toFixed(2)}%
          </span>
        </div>
      </section>

      <section className="reconciliation-detail__information">
        <h2>Run information</h2>
        <dl>
          <div>
            <dt>Bank file</dt>
            <dd>{data.bankFileName}</dd>
          </div>
          <div>
            <dt>Ledger file</dt>
            <dd>{data.ledgerFileName}</dd>
          </div>
          <div>
            <dt>Date window</dt>
            <dd>{data.dateWindow}</dd>
          </div>
          <div>
            <dt>Processing time</dt>
            <dd>{data.processingTime}</dd>
          </div>
        </dl>
      </section>

      <section className="reconciliation-detail__results">
        <h2>Transaction results</h2>
        <div
          className="reconciliation-detail__filters"
          aria-label="Filter transaction results"
        >
          {filters.map((item) => (
            <button
              aria-pressed={filter === item.value}
              className={
                filter === item.value
                  ? "reconciliation-detail__filter reconciliation-detail__filter--active"
                  : "reconciliation-detail__filter"
              }
              key={item.value}
              onClick={() => setFilter(item.value)}
              type="button"
            >
              {item.label}
              <span>{countByFilter[item.value].toLocaleString()}</span>
            </button>
          ))}
        </div>

        {filteredTransactions.length > 0 ? (
          <ul className="reconciliation-detail__transactions">
            {filteredTransactions.map((transaction) => (
              <li key={transaction.id}>
                <div className="reconciliation-detail__transaction-heading">
                  <p>
                    <strong>{transaction.displayId}</strong>
                    {transaction.reference && (
                      <span> · {transaction.reference}</span>
                    )}
                  </p>
                  <Status tone={statusTone(transaction.status)}>
                    {statusLabel(transaction.status)}
                  </Status>
                </div>
                <p className="reconciliation-detail__transaction-entity">
                  {transaction.entity} · {transaction.amountSummary}
                </p>
                <p className="reconciliation-detail__transaction-explanation">
                  {transaction.explanation}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <div className="reconciliation-detail__empty" role="status">
            {transactions.length === 0
              ? "No transaction results are available for this run."
              : `No ${
                  filter === "exceptions" ? "exception" : filter
                } transactions in this run.`}
          </div>
        )}
      </section>
    </main>
  )
}
