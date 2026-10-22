import { useNavigate, useSearchParams } from "react-router-dom"
import { Button } from "../../components/ui/Button"
import { PageHeader } from "../../components/ui/PageHeader"
import { SearchField } from "../../components/ui/SearchField"
import { SelectField } from "../../components/ui/SelectField"
import { RunStatusIcon } from "../../components/ui/RunStatusIcon"
import { recentRuns } from "../dashboard/dashboardData"
import type { WorkspaceData } from "../../services/apiClient"

export function RunHistory({
  workspace,
  onViewDetails,
}: {
  workspace?: WorkspaceData
  onViewDetails?: (runId: string) => void
}) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const query = searchParams.get("q") ?? ""
  const status = searchParams.get("status") ?? "All statuses"

  const setQuery = (newQuery: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (newQuery) {
          next.set("q", newQuery)
        } else {
          next.delete("q")
        }
        return next
      },
      { replace: true },
    )
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

  const handleViewDetails = (runId: string) => {
    if (onViewDetails) {
      onViewDetails(runId)
    } else {
      navigate(`/reconciliations/${encodeURIComponent(runId)}`)
    }
  }

  const sourceRuns = workspace?.runs ?? recentRuns
  const rows = sourceRuns.filter(
    (run) =>
      (run.id || "").toLowerCase().includes(query.toLowerCase()) &&
      (status === "All statuses" || run.status === status),
  )
  const statuses = [...new Set(sourceRuns.map((run) => run.status))]

  return (
    <>
      <PageHeader
        description="Review every reconciliation run and its processing results."
        title="Run history"
      />
      <section className="panel">
        <div className="table-toolbar">
          <SearchField
            onChange={setQuery}
            placeholder="Search runs..."
            value={query}
          />
          <SelectField
            label="Filter by status"
            onChange={setStatus}
            value={status}
          >
            <option>All statuses</option>
            {statuses.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </SelectField>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Validated</th>
                <th>Bank File</th>
                <th>Ledger File</th>
                <th className="numeric">Transactions</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.id}>     
                  <td>
                    {workspace
                      ? new Date(run.date).toLocaleString()
                      : run.date}
                  </td>
                   <td>
                    {run.bank_file || "—"}
                  </td>
                  <td>
                    {run.ledger_file || "—"}
                  </td>
                  <td className="numeric tabular">
                    {typeof run.transactions === "number"
                      ? run.transactions.toLocaleString()
                      : run.transactions}
                  </td>
                  <td>
                    <RunStatusIcon status={run.status} />
                  </td>
                  <td>
                    <Button
                      onClick={() => handleViewDetails(run.id)}
                      variant="tertiary"
                    >
                      View details
                    </Button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td className="empty-table" colSpan={5}>
                    {workspace && sourceRuns.length === 0
                      ? "No reconciliation runs yet. Upload your first files to get started."
                      : "No runs match your search."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>
            Showing {rows.length} of {workspace ? sourceRuns.length : 24} runs
          </span>
          <div>
            <Button disabled>Previous</Button>
            <Button>Next</Button>
          </div>
        </div>
      </section>
    </>
  )
}
