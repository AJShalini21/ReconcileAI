import { useSearchParams } from "react-router-dom"
import { Icon } from "../../components/ui/Icon"
import type { IconName } from "../../types/icons"
import { PageHeader } from "../../components/ui/PageHeader"
import { SelectField } from "../../components/ui/SelectField"
import { Status } from "../../components/ui/Status"
import { auditRows } from "../dashboard/dashboardData"
import type { WorkspaceData } from "../../services/apiClient"

export function AuditHistory({ workspace }: { workspace?: WorkspaceData }) {
  const [searchParams, setSearchParams] = useSearchParams()

  const action = searchParams.get("action") ?? "All actions"
  const run = searchParams.get("run") ?? "All runs"

  const setAction = (newAction: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newAction && newAction !== "All actions") {
        next.set("action", newAction)
      } else {
        next.delete("action")
      }
      return next
    })
  }

  const setRun = (newRun: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newRun && newRun !== "All runs") {
        next.set("run", newRun)
      } else {
        next.delete("run")
      }
      return next
    })
  }
  const userActionKeywords = [
    "validat",
    "upload",
    "reconciliation",
    "exception",
    "candidate",
    "mapping",
    "entity",
  ]

  const sourceRows = (
    workspace
      ? workspace.audit_events.map((event) => ({
          ...event,
          date: new Date(event.date).toLocaleString(),
        }))
      : auditRows
  ).filter((row) => {
    const act = (row.action || "").toLowerCase()
    const title = (row.title || "").toLowerCase()
    // Exclude internal candidate evaluations
    if (act.includes("candidate_evaluated") || title.includes("candidate evaluated")) {
      return false
    }
    return userActionKeywords.some(
      (kw) => act.includes(kw) || title.includes(kw),
    )
  })
  const rows = sourceRows.filter(
    (row) =>
      (action === "All actions" || row.action === action) &&
      (run === "All runs" || row.run === run),
  )

  return (
    <>
      <PageHeader
        description="Track actions and decisions across reconciliation runs."
        title="Audit history"
      />
      <section className="panel">
        <div className="audit-filters">
          <div className="filter-field">
            <span>Action</span>
            <SelectField
              label="Filter by action"
              onChange={setAction}
              value={action}
            >
              <option>All actions</option>
              {[...new Set(sourceRows.map((row) => row.action))].map(
                (value) => (
                  <option key={value}>{value}</option>
                ),
              )}
            </SelectField>
          </div>
          <div className="filter-field">
            <span>Run</span>
            <SelectField label="Filter by run" onChange={setRun} value={run}>
              <option>All runs</option>
              {[
                ...new Set(sourceRows.map((row)  => row.run).filter(Boolean)),
              ].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </SelectField>
          </div>
        </div>
        <div className="audit-feed">
          {rows.map((row) => (
            <article className="audit-event" key={`${row.title}-${row.date}`}>
              <span className="audit-event__icon">
                <Icon name={row.icon} />
              </span>
              <div className="audit-event__content">
                <div className="audit-event__title">
                  <h2>{row.title}</h2>
                  <Status tone={row.tone}>Success</Status>
                </div>
                <strong>{row.resource}</strong>
                <p>{row.description}</p>
                <time>{row.date}</time>
              </div>
            </article>
          ))}
          {rows.length === 0 && (
            <p className="empty-message">
              {workspace
                ? "No audit activity yet. Your workspace actions will appear here."
                : "No audit records match the selected filters."}
            </p>
          )}
        </div>
      </section>
    </>
  )
}
